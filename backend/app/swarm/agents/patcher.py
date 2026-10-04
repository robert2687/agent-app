"""PatcherAgent: self-healing repair driven by test/lint exceptions."""

from __future__ import annotations


from app.swarm.agents.base import BaseAgent
from app.swarm.agents.coder import existing_file_excerpt
from app.swarm.context import FileEdit, SwarmContext, parse_json_block
from app.swarm.agents.coder import apply_edits  # re-use the safe applier

_SYSTEM = """You are PatcherAgent inside the Nexus AI Swarm's self-healing \
loop. A previous implementation attempt failed lint checks or tests. You \
receive the exact failure output and the relevant current file contents. \
Repair the code.

Respond with ONLY a JSON object (no prose, no markdown fences):
{
  "rationale": "root cause in 1-3 sentences",
  "edits": [
    {"path": "relative/file.py", "action": "create|modify|delete", "content": "<FULL file content>"}
  ]
}
Hard rules:
- "content" MUST be the COMPLETE final file content (no diffs, no ellipses, \
no placeholder comments).
- Fix the actual root cause, not the symptom; keep the original task intent.
- If a test itself is wrong, you may fix the test — explain why in \
"rationale"."""


class PatcherAgent(BaseAgent):
    """Consumes validator exceptions and emits corrective edits."""

    role = "patcher"
    description = "Repairs code from test/lint failure output"

    async def run(self, ctx: SwarmContext) -> list[FileEdit]:
        validation = ctx.validation or {}
        touched = {edit.path for edit in ctx.edits}
        excerpts: list[str] = []
        for path in sorted(touched):
            content = existing_file_excerpt(ctx, path, max_chars=10_000)
            excerpts.append(f"# ── file: {path} ──\n{content}")
        # Also pull in files named by the failure output, if any.
        for path in validation.get("failing_files", [])[:5]:  # type: ignore[union-attr]
            if path not in touched and isinstance(path, str):
                excerpts.append(
                    f"# ── file: {path} ──\n{existing_file_excerpt(ctx, path, max_chars=6_000)}"
                )

        user_prompt = (
            f"# Original task\n{ctx.task}\n\n"
            f"# Repair iteration {ctx.repair_iteration} of {ctx.max_repair_iterations}\n\n"
            f"# Lint output\n```\n{str(validation.get('lint', {}).get('output', ''))[:8_000]}\n```\n\n"
            f"# Test output\n```\n{str(validation.get('tests', {}).get('output', ''))[:16_000]}\n```\n\n"
            f"# Current code\n{chr(10).join(excerpts) or '(no files)'}\n\n"
            "Emit the repair edits JSON now."
        )
        raw = await self._complete(
            ctx,
            system=_SYSTEM,
            user=user_prompt,
            purpose=f"{self.role}",
            max_tokens=8192,
            temperature=0.15,
        )
        payload = parse_json_block(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("edits"), list):
            raise ValueError("PatcherAgent output missing required 'edits' array.")
        from app.swarm.agents.coder import CoderAgent  # local import avoids cycle at module load

        edits = [CoderAgent._coerce_edit(item) for item in payload["edits"]]
        applied = await apply_edits(ctx, edits)
        self._last_summary = str(payload.get("rationale", ""))[:2000]
        return applied
