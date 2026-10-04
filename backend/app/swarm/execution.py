"""Sandboxed command execution for the self-healing validation loop.

Runs the configured lint/test commands inside the repository workdir with:
* a hard wall-clock timeout,
* a scrubbed environment (no vault material, no NEXUS_* secrets),
* captured stdout/stderr with size caps,
* output truncation to keep prompts token-bounded.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from pathlib import Path

_MAX_OUTPUT_CHARS = 60_000
_FILE_HINT_RE = re.compile(r"^\s*(?:[A-Za-z]:)?[\w./\\-]+\.(?:py|js|ts|tsx|jsx|go|rs|rb|java)\b", re.MULTILINE)


@dataclass(slots=True)
class CommandResult:
    """Outcome of one executed command."""

    command: str
    exit_code: int
    output: str
    duration_ms: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class CommandRunner:
    """Executes allowlisted shell commands inside the repository workdir."""

    def __init__(self, *, timeout_seconds: int = 180) -> None:
        self._timeout = timeout_seconds

    async def run(self, workdir: Path, command: str) -> CommandResult:
        """Run ``command`` in ``workdir``; never raises, always returns a result."""
        if not command.strip():
            return CommandResult(command=command, exit_code=0, output="", duration_ms=0.0)

        env = self._scrubbed_env()
        started = asyncio.get_running_loop().time()
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=str(workdir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
                start_new_session=True,
            )
        except OSError as exc:
            return CommandResult(
                command=command, exit_code=127, output=f"Failed to spawn: {exc}",
                duration_ms=0.0,
            )

        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=self._timeout)
            timed_out = False
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
            stdout, timed_out = b"", True

        duration_ms = (asyncio.get_running_loop().time() - started) * 1000.0
        output = stdout.decode("utf-8", errors="replace")
        if timed_out:
            output += f"\n… command exceeded {self._timeout}s and was terminated"
        return CommandResult(
            command=command,
            exit_code=process.returncode if not timed_out else 124,
            output=_truncate(output),
            duration_ms=round(duration_ms, 1),
            timed_out=timed_out,
        )

    @staticmethod
    def _scrubbed_env() -> dict[str, str]:
        """Minimal, secret-free environment for child processes."""
        keep = ("PATH", "HOME", "LANG", "LC_ALL", "PYTHONDONTWRITEBYTECODE", "SYSTEMROOT", "TEMP", "TMP")
        env = {key: value for key, value in os.environ.items() if key in keep}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["CI"] = "1"
        env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        return env


def extract_failing_files(output: str, known_files: set[str]) -> list[str]:
    """Best-effort extraction of failing file paths from validator output."""
    found: list[str] = []
    for match in _FILE_HINT_RE.finditer(output):
        candidate = match.group(0).strip().replace("\\", "/")
        normalized = candidate.lstrip("./")
        if normalized in known_files and normalized not in found:
            found.append(normalized)
    return found[:20]


def summarize_results(lint: CommandResult, tests: CommandResult) -> dict[str, object]:
    """Normalize command results into the validation artifact."""
    passed = lint.ok and tests.ok
    return {
        "passed": passed,
        "lint": {
            "command": lint.command,
            "exit_code": lint.exit_code,
            "output": lint.output,
            "duration_ms": lint.duration_ms,
        },
        "tests": {
            "command": tests.command,
            "exit_code": tests.exit_code,
            "output": tests.output,
            "duration_ms": tests.duration_ms,
        },
    }


def _truncate(text: str) -> str:
    text = text.strip()
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text
    half = _MAX_OUTPUT_CHARS // 2
    return (
        text[:half]
        + "\n… [output truncated] …\n"
        + text[-half:]
    )
