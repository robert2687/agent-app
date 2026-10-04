"""CoderAgent: emits concrete file edits (full-file contents) and applies them."""

from __future__ import annotations

import json
from typing import Any

from app.swarm.agents.architect import ArchitectAgent  # noqa: F401 (re-export clarity)
from app.swarm.agents.base import BaseAgent
from app.swarm.agents.planner import summarize_plan
from app.swarm.context import FileEdit, SwarmContext, parse_json_block

_SYSTEM = """You are CoderAgent inside the Nexus AI Swarm — a meticulous \
senior engineer. You implement the planned changes by emitting complete file \
contents.

Respond with ONLY a JSON object (no prose, no markdown fences):
{
  "summary": "one-paragraph description of what you changed",
  "edits": [
    {"path": "relative/file.py", "action": "create|modify|delete", "content": "<FULL file content>"}
  ]
}
Hard rules:
- For create/modify, "content" MUST be the COMPLETE final file content — \
never diffs, never placeholders like "... rest of code", never truncation.
- Reuse the repository's existing style, imports and conventions.
- Keep changes minimal and focused on the plan.
- Escape nothing manually: JSON string escaping only."""


class CoderAgent(BaseAgent):
    """Implements the architecture as complete-file edits, applied to the worktree."""

    role = "coder"
    description = "Writes and applies complete file edits"

    async def run(self, ctx: SwarmContext) -> list[FileEdit]:
        architecture = ctx.architecture or {}
        modules = "\n".join(
            f"- {module.get('path')}: {module.get('responsibility')}"
            for module in architecture.get("modules", [])
        )
        user_prompt = (
            f"# Task\n{ctx.task}\n\n"
            f"# Plan\n{summarize_plan(ctx.plan or {})}\n\n"
            f"# Architecture approach\n{architecture.get('approach', '')}\n"
            f"# Modules\n{modules or '(derived from plan)'}\n\n"
            f"# Repository: {ctx.repository_name}\n"
            f"# Current code\n{self._window_content(ctx, max_chars=90_000)}\n\n"
            "Emit the edits JSON now."
        )
        raw = await self._complete(
            ctx,
            system=_SYSTEM,
            user=user_prompt,
            purpose=f"{self.role}",
            max_tokens=8192,
            temperature=0.2,
        )
        payload = parse_json_block(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("edits"), list):
            raise ValueError("CoderAgent output missing required 'edits' array.")
        edits = [self._coerce_edit(item) for item in payload["edits"]]
        applied = await apply_edits(ctx, edits)
        self._last_summary = str(payload.get("summary", ""))[:2000]
        return applied

    @staticmethod
    def _coerce_edit(item: Any) -> FileEdit:
        if not isinstance(item, dict):
            raise ValueError(f"Edit entry is not an object: {item!r}")
        path = str(item.get("path", "")).strip().lstrip("./")
        action = str(item.get("action", "modify")).strip().lower()
        if not path:
            raise ValueError("Edit entry missing 'path'.")
        if action not in ("create", "modify", "delete"):
            raise ValueError(f"Edit action must be create|modify|delete, got {action!r}.")
        content = str(item.get("content", "") or "")
        if action in ("create", "modify") and not content.strip():
            raise ValueError(f"Edit for {path} has empty content.")
        return FileEdit(path=path, action=action, content=content)


async def apply_edits(ctx: SwarmContext, edits: list[FileEdit]) -> list[FileEdit]:
    """Validate paths stay inside the workdir and apply edits atomically."""
    import asyncio

    applied: list[FileEdit] = []

    def _apply_all() -> None:
        root = ctx.workdir.resolve()
        for edit in edits:
            target = (root / edit.path).resolve()
            if not target.is_relative_to(root):
                raise ValueError(f"Refusing to edit outside repository: {edit.path}")
            if edit.action == "delete":
                if target.exists():
                    target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = target.with_suffix(target.suffix + ".nexus-tmp")
                tmp.write_text(edit.content, encoding="utf-8")
                tmp.replace(target)
            applied.append(edit)

    await asyncio.to_thread(_apply_all)
    return applied


def render_edits(edits: list[FileEdit]) -> str:
    """Compact textual digest of an edit list (for prompts/telemetry)."""
    return json.dumps(
        [{"path": e.path, "action": e.action, "bytes": len(e.content)} for e in edits],
        indent=2,
    )


def existing_file_excerpt(ctx: SwarmContext, path: str, max_chars: int = 8_000) -> str:
    """Read back a (possibly just-written) file for reviewer/patcher prompts."""
    try:
        target = (ctx.workdir / path).resolve()
        if not target.is_relative_to(ctx.workdir.resolve()):
            return "(path outside repository)"
        return target.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except OSError:
        return "(file not found)"
