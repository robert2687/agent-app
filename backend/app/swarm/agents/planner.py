"""PlannerAgent: decomposes the task into an ordered, file-scoped plan."""

from __future__ import annotations

import json
from typing import Any

from app.swarm.agents.base import BaseAgent
from app.swarm.context import SwarmContext, parse_json_block

_SYSTEM = """You are PlannerAgent inside the Nexus AI Swarm, an elite autonomous \
software engineering system. Your job is to decompose a user task about a real \
repository into a minimal, ordered execution plan.

Respond with ONLY a JSON object (no prose, no markdown fences) shaped exactly:
{
  "objective": "one-sentence restatement of the goal",
  "steps": [
    {"id": 1, "title": "short imperative title",
     "detail": "2-3 sentences of precise instructions",
     "files": ["relative/path/to/file.py"]}
  ],
  "risks": ["short risk notes"],
  "success_criteria": ["verifiable criteria"]
}
Rules: reference only files that exist in the provided repository listing; \
prefer 3-7 steps; keep scope tight and concrete."""


class PlannerAgent(BaseAgent):
    """Produces the canonical task plan consumed by downstream agents."""

    role = "planner"
    description = "Decomposes the task into an ordered, file-scoped plan"

    async def run(self, ctx: SwarmContext) -> dict[str, Any]:
        user_prompt = (
            f"# Task\n{ctx.task}\n\n"
            f"# Repository: {ctx.repository_name}\n"
            f"# Files (context-window selection)\n{self._file_listing(ctx)}\n\n"
            "Produce the plan JSON now."
        )
        raw = await self._complete(
            ctx,
            system=_SYSTEM,
            user=user_prompt,
            purpose=f"{self.role}",
            max_tokens=2048,
            temperature=0.1,
        )
        plan = parse_json_block(raw)
        if not isinstance(plan, dict) or "steps" not in plan:
            raise ValueError("PlannerAgent output missing required 'steps' array.")
        plan.setdefault("objective", ctx.task)
        plan.setdefault("risks", [])
        plan.setdefault("success_criteria", [])
        return plan


def summarize_plan(plan: dict[str, Any]) -> str:
    """Human/LLM-readable one-paragraph plan digest."""
    steps = plan.get("steps") or []
    rendered = "; ".join(
        f"{step.get('id', i + 1)}. {step.get('title', 'untitled')}" for i, step in enumerate(steps)
    )
    return f"Objective: {plan.get('objective', 'n/a')}\nSteps: {rendered or 'n/a'}"


def referenced_files(plan: dict[str, Any]) -> list[str]:
    """All file paths mentioned across plan steps (ordering preserved)."""
    collected: list[str] = []
    for step in plan.get("steps") or []:
        for path in step.get("files") or []:
            normalized = str(path).strip().lstrip("./")
            if normalized and normalized not in collected:
                collected.append(normalized)
    return collected


def dumps(plan: dict[str, Any]) -> str:  # pragma: no cover - trivial helper
    return json.dumps(plan, indent=2)
