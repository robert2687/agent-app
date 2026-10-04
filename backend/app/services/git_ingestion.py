"""Async GitHub ingestion engine: depth-aware clone/pull + enrichment.

Clone/pull operations run GitPython (sync) inside a worker thread so the
event loop is never blocked. After checkout we:

1. Filter binaries and vendored/heavy directories,
2. Count files / LOC / language histogram,
3. Run the secret scanner,
4. Build the tree-sitter/regex AST dependency graph.
"""

from __future__ import annotations

import hashlib
import mimetypes
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import anyio
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError, NoSuchPathError

from app.services.ast_parser import build_dependency_graph, detect_languages
from app.services.secret_scanner import SecretFinding, scan_repository

_IGNORED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
    "target", ".next", ".nuxt", ".turbo", ".gradle", "vendor", ".idea",
    ".vscode", "site-packages", ".eggs", "coverage", ".coverage",
}
_TEXT_SUFFIXES_OVERRIDE = {
    ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg",
    ".env", ".sh", ".bash", ".zsh", ".gitignore", ".dockerignore",
    ".lock", ".mod", ".sum", ".rst", ".csv", ".tsv",
}
_GIT_URL_RE = re.compile(
    r"^(?:https?://|git@)[\w.-]+[:/](?P<owner>[\w.-]+)/(?P<name>[\w.-]+?)(?:\.git)?/?$"
)


@dataclass(slots=True)
class RepositorySnapshot:
    """Everything learned about a repository during ingestion."""

    url: str
    name: str
    branch: str | None
    default_branch: str | None
    head_commit: str | None
    clone_path: str
    depth: int
    files: list[str] = field(default_factory=list)
    file_count: int = 0
    total_loc: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    secret_findings: list[SecretFinding] = field(default_factory=list)
    dep_graph: dict[str, object] | None = None
    error: str | None = None


def parse_repo_name(url: str) -> str:
    """Extract ``owner/name`` (or the last path segment) from a git URL."""
    match = _GIT_URL_RE.match(url.strip())
    if match:
        return f"{match.group('owner')}/{match.group('name')}"
    tail = url.strip().rstrip("/").rsplit("/", 1)[-1]
    return tail.removesuffix(".git") or "unknown-repository"


def clone_dir_for_url(clone_root: Path, url: str) -> Path:
    """Deterministic, collision-free clone directory per URL."""
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    return clone_root / f"{parse_repo_name(url).replace('/', '__')}-{digest}"


def is_probably_binary(path: Path) -> bool:
    """Cheap binary detection: suffix → mimetype → null-byte sniff."""
    if path.suffix.lower() in _TEXT_SUFFIXES_OVERRIDE:
        return False
    mimetype, _ = mimetypes.guess_type(path.name)
    if mimetype is None:
        # Unknown suffix: sniff the first 1024 bytes for NULs.
        try:
            with path.open("rb") as handle:
                return b"\x00" in handle.read(1024)
        except OSError:
            return True
    return not mimetype.startswith("text/")


def list_source_files(root: Path, *, max_files: int = 20_000) -> list[str]:
    """Relative paths of text files, skipping vendored/binary paths."""
    collected: list[str] = []
    stack = [root]
    while stack and len(collected) < max_files:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for entry in entries:
            name = entry.name
            if entry.is_dir():
                if name in _IGNORED_DIRS or name.startswith(".git"):
                    continue
                stack.append(entry)
            elif entry.is_file():
                if name.startswith(".git") or name.endswith((".pyc", ".so", ".o", ".woff", ".woff2", ".ttf", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".gz", ".tar", ".whl")):
                    continue
                if is_probably_binary(entry):
                    continue
                collected.append(entry.relative_to(root).as_posix())
    return sorted(collected)


def _do_clone(clone_root: Path, url: str, branch: str | None, depth: int, force: bool) -> tuple[Path, str | None, str]:
    """Synchronous (threadpool) clone-or-pull. Returns (path, branch, head)."""
    target = clone_dir_for_url(clone_root, url)
    if target.exists() and (target / ".git").exists() and not force:
        repo = Repo(str(target))
        repo.remote("origin").fetch(depth=depth, prune=True)
        checkout = branch or repo.active_branch.name
        try:
            repo.git.checkout(checkout)
        except GitCommandError:
            repo.git.checkout(f"origin/{checkout}")
            repo.git.reset("--hard", f"origin/{checkout}")
        repo.git.reset("--hard", f"origin/{checkout}")
        repo.git.clean("-fdx")
        head = repo.head.commit.hexsha
        return target, checkout, head

    if target.exists():
        Repo(str(target)).close() if (target / ".git").exists() else None
        import shutil

        shutil.rmtree(target, ignore_errors=True)

    kwargs: dict[str, object] = {"depth": depth, "no_single_branch": False}
    if branch:
        kwargs["branch"] = branch
    repo = Repo.clone_from(url, str(target), **kwargs)  # type: ignore[arg-type]
    head = repo.head.commit.hexsha
    default_branch = branch
    if not branch:
        try:
            default_branch = repo.active_branch.name
        except TypeError:  # detached HEAD in ancient git versions
            default_branch = "main"
    return target, default_branch, head


def _do_enrich(clone_path: Path) -> tuple[list[str], int, dict[str, int], list[SecretFinding], dict[str, object]]:
    """Synchronous (threadpool) enrichment: files, LOC, secrets, dep graph."""
    files = list_source_files(clone_path)
    total_loc = 0
    read_cap = 4_000
    for relative in files[:read_cap]:
        try:
            total_loc += len((clone_path / relative).read_text(encoding="utf-8", errors="ignore").splitlines())
        except OSError:
            continue
    languages = detect_languages(files)
    findings = scan_repository(clone_path, files)
    graph = build_dependency_graph(clone_path, files)
    return files, total_loc, languages, findings, graph.to_payload()


class GitIngestionService:
    """Async facade over clone/pull + enrichment."""

    def __init__(self, clone_root: Path, max_repo_size_mb: int = 500) -> None:
        self._clone_root = clone_root
        self._max_bytes = max_repo_size_mb * 1024 * 1024

    @property
    def clone_root(self) -> Path:
        return self._clone_root

    async def ingest(
        self,
        url: str,
        *,
        branch: str | None = None,
        depth: int = 1,
        force: bool = False,
        on_status: Callable[[str, str], None] | None = None,
    ) -> RepositorySnapshot:
        """Clone or pull ``url`` and return a fully enriched snapshot."""
        def notify(status: str, detail: str) -> None:
            if on_status is not None:
                on_status(status, detail)

        try:
            notify("cloning", f"Cloning {url} (depth={depth})")
            clone_path, resolved_branch, head = await anyio.to_thread.run_sync(
                lambda: _do_clone(self._clone_root, url, branch, depth, force)
            )
            _enforce_size_limit(clone_path, self._max_bytes)

            notify("scanning", "Scanning for secrets")
            files, total_loc, languages, findings, graph = await anyio.to_thread.run_sync(
                lambda: _do_enrich(clone_path)
            )

            notify("parsing", "Building AST dependency graph")
            snapshot = RepositorySnapshot(
                url=url,
                name=parse_repo_name(url),
                branch=branch,
                default_branch=resolved_branch,
                head_commit=head,
                clone_path=str(clone_path),
                depth=depth,
                files=files,
                file_count=len(files),
                total_loc=total_loc,
                languages=languages,
                secret_findings=findings,
                dep_graph=graph,
            )
            return snapshot
        except GitCommandError as exc:
            message = _sanitize_git_error(str(exc))
            raise IngestionFailure(url, message) from exc
        except (InvalidGitRepositoryError, NoSuchPathError) as exc:
            raise IngestionFailure(url, f"Repository is not a valid git repository: {exc}") from exc


def _enforce_size_limit(clone_path: Path, max_bytes: int) -> None:
    """Reject repositories that exceed the configured on-disk budget."""
    total = 0
    for path in clone_path.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                continue
            if total > max_bytes:
                raise IngestionFailure(
                    str(clone_path),
                    f"Repository exceeds the configured size limit ({max_bytes // (1024 * 1024)} MB).",
                )


def _sanitize_git_error(message: str) -> str:
    """Strip credential-ish query strings from git error output."""
    message = re.sub(r"https://[^@\s]+@", "https://", message)
    return message[:512]


class IngestionFailure(Exception):
    """Raised when clone/pull/enrichment fails (message is user-safe)."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(reason)
        self.url = url
        self.reason = reason
