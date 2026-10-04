"""Shared, mutable execution context threaded through every agent."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.context_window import ContextWindow


def parse_json_block(text: str) -> Any:
    """Extract and parse the first JSON object/array embedded in model output.

    Models occasionally wrap JSON in prose or markdown fences; this parser
    scans for the first ``{`` or ``[`` and decodes the longest valid prefix.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char not in "{[":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[index:])
            return value
        except json.JSONDecodeError:
            continue
    raise ValueError("No parseable JSON block found in model output.")


@dataclass
class FileEdit:
    """A single file mutation produced by CoderAgent / PatcherAgent."""

    path: str
    action: str  # create | modify | delete
    content: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "action": self.action, "content": self.content}


@dataclass
class SwarmContext:
    """Everything the agents share during one job run."""

    job_id: str
    repository_id: str
    repository_name: str
    task: str
    workdir: Path
    # Inputs
    context_windows: list[ContextWindow] = field(default_factory=list)
    blocked_files: set[str] = field(default_factory=set)
    # Artifacts (JSON payloads produced by each agent)
    plan: dict[str, Any] | None = None
    architecture: dict[str, Any] | None = None
    edits: list[FileEdit] = field(default_factory=list)
    review: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    # Self-healing loop state
    repair_iteration: int = 0
    max_repair_iterations: int = 3
    # Routing preferences
    preferred_model: str | None = None
    preferred_provider_id: str | None = None
    # Cumulative token usage
    token_usage: dict[str, int] = field(
        default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "requests": 0}
    )

    def add_tokens(self, prompt: int, completion: int) -> None:
        self.token_usage["prompt_tokens"] += prompt
        self.token_usage["completion_tokens"] += completion
        self.token_usage["requests"] += 1
