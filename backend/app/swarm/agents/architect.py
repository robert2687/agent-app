"""ArchitectAgent: maps the plan onto concrete modules and interfaces."""

from __future__ import annotations

from typing import Any

from app.swarm.agents.base import BaseAgent
from app.swarm.agents.planner import summarize_plan
from app.swarm.context import SwarmContext, parse_json_block

_SYSTEM = """You are ArchitectAgent inside the Nexus AI Swarm. You transform a \
plan into a concrete implementation architecture for the target repository.

Respond with ONLY a JSON object (no prose, no markdown fences):
{
  "approach": "2-4 sentence implementation strategy",
  "modules": [
    {"name": "module name", "path": "relative/file.py",
     "responsibility": "what this module does",
     "interfaces": ["def function_name(...): description"]}
  ],
  "data_flow": "how data moves between modules",
  "constraints": ["style/compatibility constraints to respect"],
  "edit_order": ["file A before file B rationale"]
}
Rules: paths must be relative to the repository root; reuse existing \
conventions visible in the provided code; never invent external dependencies \
that are not already implied by the plan."""


class ArchitectAgent(BaseAgent):
    """Produces the module/interface architecture for the CoderAgent."""

    role = "architect"
    description = "Maps the plan onto concrete modules and interfaces"

    async def run(self, ctx: SwarmContext) -> dict[str, Any]:
        user_prompt = (
            f"# Task\n{ctx.task}\n\n"
            f"# Plan\n{summarize_plan(ctx.plan or {})}\n\n"
            f"# Repository: {ctx.repository_name}\n"
            f"# Files\n{self._file_listing(ctx)}\n\n"
            f"# Code excerpts\n{self._window_content(ctx, max_chars=40_000)}\n\n"
            "Produce the architecture JSON now."
        )
        raw = await self._complete(
            ctx,
            system=_SYSTEM,
            user=user_prompt,
            purpose=f"{self.role}",
            max_tokens=3072,
            temperature=0.2,
        )
        architecture = parse_json_block(raw)
        if not isinstance(architecture, dict):
            raise ValueError("ArchitectAgent output is not a JSON object.")
        architecture.setdefault("modules", [])
        architecture.setdefault("approach", "")
        architecture.setdefault("data_flow", "")
        architecture.setdefault("constraints", [])
        architecture.setdefault("edit_order", [])
        return architecture
