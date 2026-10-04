"""Unified git diff generation over the swarm's working tree."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path

from git import Repo


@dataclass(slots=True)
class DiffHunk:
    """One hunk with side-by-side line arrays for the UI."""

    old_start: int
    new_start: int
    old_lines: list[tuple[int, str]] = field(default_factory=list)  # (lineno, text)
    new_lines: list[tuple[int, str]] = field(default_factory=list)


@dataclass(slots=True)
class FileDiff:
    """Parsed diff of a single file."""

    path: str
    additions: int = 0
    deletions: int = 0
    is_new: bool = False
    is_deleted: bool = False
    is_binary: bool = False
    hunks: list[DiffHunk] = field(default_factory=list)


@dataclass(slots=True)
class ParsedDiff:
    """Structured, renderable representation of a unified diff."""

    files: list[FileDiff] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    raw: str = ""


def _do_diff(workdir: Path) -> str:
    """Compute ``git diff HEAD`` including untracked files (intent-to-add)."""
    repo = Repo(str(workdir))
    try:
        repo.git.add("-A", "-N", "--", ":!*.nexus-tmp")
    except Exception:  # noqa: BLE001 - intent-to-add best effort
        pass
    try:
        text = repo.git.diff("HEAD", "--no-color", "-M")
    finally:
        try:
            repo.git.reset()
        except Exception:  # noqa: BLE001
            pass
    return text or ""


async def compute_diff(workdir: Path) -> str:
    """Async wrapper around the synchronous git diff."""
    return await asyncio.to_thread(_do_diff, workdir)


def parse_unified_diff(text: str) -> ParsedDiff:
    """Parse a unified diff into per-file, per-hunk structures."""
    parsed = ParsedDiff(raw=text)
    if not text:
        return parsed

    current: FileDiff | None = None
    hunk: DiffHunk | None = None
    old_lineno = new_lineno = 0

    for line in text.splitlines():
        if line.startswith("diff --git "):
            match = re.search(r"diff --git a/(.+?) b/(.+)$", line)
            path = (match.group(2) if match else line.split()[-1]).strip()
            current = FileDiff(path=path)
            parsed.files.append(current)
            hunk = None
            continue
        if current is None:
            continue
        if line.startswith("new file mode"):
            current.is_new = True
        elif line.startswith("deleted file mode"):
            current.is_deleted = True
        elif line.startswith("Binary files"):
            current.is_binary = True
        elif line.startswith("@@"):
            match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            new_start = int(match.group(1)) if match else 1
            old_match = re.match(r"@@ -(\d+)(?:,\d+)? \+", line)
            old_start = int(old_match.group(1)) if old_match else 1
            hunk = DiffHunk(old_start=old_start, new_start=new_start)
            current.hunks.append(hunk)
            old_lineno, new_lineno = old_start, new_start
        elif hunk is not None:
            if line.startswith("+++") or line.startswith("---"):
                continue
            if line.startswith("+"):
                hunk.new_lines.append((new_lineno, line[1:]))
                new_lineno += 1
                current.additions += 1
                parsed.additions += 1
            elif line.startswith("-"):
                hunk.old_lines.append((old_lineno, line[1:]))
                old_lineno += 1
                current.deletions += 1
                parsed.deletions += 1
            else:
                hunk.old_lines.append((old_lineno, line[1:] if line.startswith(" ") else line))
                hunk.new_lines.append((new_lineno, line[1:] if line.startswith(" ") else line))
                old_lineno += 1
                new_lineno += 1

    return parsed


def to_payload(job_id: str, parsed: ParsedDiff) -> dict[str, object]:
    """Serialize a ParsedDiff into the API schema shape."""
    return {
        "job_id": job_id,
        "additions": parsed.additions,
        "deletions": parsed.deletions,
        "raw": parsed.raw,
        "files": [
            {
                "path": f.path,
                "additions": f.additions,
                "deletions": f.deletions,
                "is_new": f.is_new,
                "is_deleted": f.is_deleted,
                "is_binary": f.is_binary,
                "hunks": [
                    {
                        "old_start": h.old_start,
                        "new_start": h.new_start,
                        "old_lines": h.old_lines,
                        "new_lines": h.new_lines,
                    }
                    for h in f.hunks
                ],
            }
            for f in parsed.files
        ],
    }
