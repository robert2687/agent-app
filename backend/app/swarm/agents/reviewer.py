"""ReviewerAgent: static review of the produced diff before validation."""

from __future__ import annotations

from typing import Any

from app.swarm.agents.base import BaseAgent
from app.swarm.context import SwarmContext, parse_json_block

_SYSTEM = """You are ReviewerAgent inside the Nexus AI Swarm — a rigorous, \
pragmatic code reviewer. You review the diff of changes produced by \
CoderAgent against the task.

Respond with ONLY a JSON object (no prose, no markdown fences):
{
  "verdict": "approve" | "revise",
  "summary": "2-3 sentence overall assessment",
  "findings": [
    {"severity": "blocker|major|minor|nit",
     "file": "relative/path.py",
     "message": "what is wrong",
     "suggestion": "concrete fix"}
  ]
}
Rules: verdict "revise" only when at least one blocker/major finding exists; \
do not demand stylistic rewrites; verify the diff actually fulfils the task."""


class ReviewerAgent(BaseAgent):
    """Reviews the working diff; verdict gates the validation stage."""

    role = "reviewer"
    description = "Reviews the produced diff and issues a verdict"

    async def run(self, ctx: SwarmContext, diff: str) -> dict[str, Any]:
        diff_excerpt = diff[:40_000]
        edited_files = "\n".join(edit.path for edit in ctx.edits) or "(none)"
        user_prompt = (
            f"# Task\n{ctx.task}\n\n"
            f"# Files changed\n{edited_files}\n\n"
            f"# Unified diff\n```diff\n{diff_excerpt or '(no textual diff produced)'}\n```\n\n"
            "Produce the review JSON now."
        )
        raw = await self._complete(
            ctx,
            system=_SYSTEM,
            user=user_prompt,
            purpose=f"{self.role}",
            max_tokens=2048,
            temperature=0.1,
        )
        review = parse_json_block(raw)
        if not isinstance(review, dict) or review.get("verdict") not in ("approve", "revise"):
            raise ValueError("ReviewerAgent output missing valid 'verdict'.")
        review.setdefault("summary", "")
        review.setdefault("findings", [])
        return review


def blocking_findings(review: dict[str, Any]) -> list[dict[str, Any]]:
    """Findings severe enough to force a revision pass."""
    return [
        finding
        for finding in review.get("findings", [])
        if isinstance(finding, dict) and finding.get("severity") in ("blocker", "major")
    ]
