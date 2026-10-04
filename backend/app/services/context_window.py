"""Token-aware context windowing for repository code.

Packs file contents into bounded context windows ordered by importance:

1. Entry-point files (main / app / index / setup),
2. Files referenced by the plan (BFS across the dependency graph),
3. Everything else, largest-relevance first.

Secret-bearing files (flagged by the scanner) are excluded from any window
that would be sent to a model provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ENTRY_POINT_MARKERS = ("main", "app", "index", "setup", "server", "cli", "__init__")

_CHARS_PER_TOKEN = 4  # conservative heuristic, no tokenizer dependency


def estimate_tokens(text: str) -> int:
    """Heuristic token estimate (~4 chars/token across mainstream models)."""
    return max(1, (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN)


@dataclass(slots=True)
class ContextWindow:
    """One packed, model-ready context window."""

    index: int
    files: list[str] = field(default_factory=list)
    content: str = ""
    tokens: int = 0


@dataclass(slots=True)
class WindowPlan:
    """All windows plus the files that had to be skipped."""

    windows: list[ContextWindow] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)
    total_tokens: int = 0


def _file_priority(path: str, referenced: dict[str, int]) -> tuple[int, int]:
    stem = Path(path).stem.lower()
    entry_bonus = 0 if any(marker in stem for marker in ENTRY_POINT_MARKERS) else 1
    reference_rank = referenced.get(path, 10_000)
    return (entry_bonus, reference_rank)


def build_context_windows(
    root: Path,
    files: list[str],
    *,
    graph: dict[str, object] | None = None,
    referenced_files: list[str] | None = None,
    blocked_files: set[str] | None = None,
    max_tokens_per_window: int = 24_000,
    max_windows: int = 8,
    max_files: int = 400,
) -> WindowPlan:
    """Build token-bounded context windows over the repository."""
    blocked = blocked_files or set()
    referenced: dict[str, int] = {path: rank for rank, path in enumerate(referenced_files or [])}

    # Expand referenced set one hop across the dependency graph (BFS depth 1).
    adjacency = _build_adjacency(graph)
    frontier = list(referenced.keys())
    rank = len(frontier)
    seen = set(frontier)
    while frontier:
        current = frontier.pop(0)
        for neighbor in adjacency.get(current, ()):  # type: ignore[union-attr]
            if neighbor not in seen and neighbor in set(files):
                seen.add(neighbor)
                referenced[neighbor] = rank
                rank += 1

    ordered = sorted(files[:max_files], key=lambda p: _file_priority(p, referenced))

    windows: list[ContextWindow] = []
    skipped: list[str] = []
    current_files: list[str] = []
    current_parts: list[str] = []
    current_tokens = 0
    header_overhead = 16

    def flush() -> None:
        nonlocal current_files, current_parts, current_tokens
        if current_files:
            windows.append(
                ContextWindow(
                    index=len(windows),
                    files=list(current_files),
                    content="\n\n".join(current_parts),
                    tokens=current_tokens,
                )
            )
        current_files, current_parts, current_tokens = [], [], 0

    for relative in ordered:
        if relative in blocked:
            skipped.append(relative)
            continue
        if len(windows) >= max_windows:
            skipped.append(relative)
            continue
        target = root / relative
        try:
            text = target.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            skipped.append(relative)
            continue
        if not text.strip():
            continue
        chunk = f"# ── file: {relative} ──\n{text}"
        chunk_tokens = estimate_tokens(chunk) + header_overhead
        if chunk_tokens > max_tokens_per_window:
            # Oversized single file: truncate to fit its own window.
            if current_files:
                flush()
            keep_chars = (max_tokens_per_window - header_overhead) * _CHARS_PER_TOKEN
            truncated = text[:keep_chars]
            chunk = (
                f"# ── file: {relative} (truncated) ──\n{truncated}"
            )
            windows.append(
                ContextWindow(
                    index=len(windows),
                    files=[relative],
                    content=chunk,
                    tokens=estimate_tokens(chunk) + header_overhead,
                )
            )
            continue
        if current_tokens + chunk_tokens > max_tokens_per_window:
            flush()
        current_files.append(relative)
        current_parts.append(chunk)
        current_tokens += chunk_tokens

    flush()
    return WindowPlan(
        windows=windows,
        skipped_files=skipped,
        total_tokens=sum(w.tokens for w in windows),
    )


def _build_adjacency(graph: dict[str, object] | None) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {}
    if not graph:
        return adjacency
    edges = graph.get("edges")  # type: ignore[union-attr]
    if isinstance(edges, list):
        for edge in edges:
            if isinstance(edge, dict) and "source" in edge and "target" in edge:
                adjacency.setdefault(str(edge["source"]), []).append(str(edge["target"]))
    return adjacency
