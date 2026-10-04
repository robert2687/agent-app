"""Regex-driven secret scanning for ingested repositories.

Runs over all text files after binary filtration. Findings are always
redacted before storage / display — only a short masked preview is kept.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Literal

Severity = Literal["critical", "high", "medium", "low"]

_MAX_PREVIEW = 48
_PREVIEW_KEEP = 6


@dataclass(frozen=True, slots=True)
class SecretRule:
    """One detector rule."""

    rule_id: str
    pattern: re.Pattern[str]
    severity: Severity
    description: str


def _rule(rule_id: str, pattern: str, severity: Severity, description: str) -> SecretRule:
    return SecretRule(rule_id=rule_id, pattern=re.compile(pattern), severity=severity, description=description)


RULES: list[SecretRule] = [
    _rule(
        "aws_access_key_id",
        r"\b(AKIA|ASIA)[0-9A-Z]{16}\b",
        "critical",
        "AWS access key ID",
    ),
    _rule(
        "aws_secret_access_key",
        r"(?i)aws.{0,30}?(?P<v>[\"'][0-9a-zA-Z/+]{40}[\"'])",
        "critical",
        "AWS secret access key assignment",
    ),
    _rule(
        "github_pat",
        r"\b(ghp_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{22,255}|gho_[A-Za-z0-9]{36,255}|ghs_[A-Za-z0-9]{36,255})\b",
        "critical",
        "GitHub personal access / OAuth token",
    ),
    _rule(
        "nvidia_api_key",
        r"\bnvapi-[A-Za-z0-9_-]{20,255}\b",
        "critical",
        "NVIDIA NIM API key",
    ),
    _rule(
        "private_key_block",
        r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----",
        "critical",
        "Embedded private key material",
    ),
    _rule(
        "google_api_key",
        r"\bAIza[0-9A-Za-z_-]{35}\b",
        "high",
        "Google API key",
    ),
    _rule(
        "slack_token",
        r"\bxox[baprs]-[A-Za-z0-9-]{10,250}\b",
        "high",
        "Slack token",
    ),
    _rule(
        "stripe_key",
        r"\b(sk|pk)_(live|test)_[0-9a-zA-Z]{16,247}\b",
        "high",
        "Stripe secret/publishable key",
    ),
    _rule(
        "openai_style_key",
        r"\bsk-(proj-)?[A-Za-z0-9_-]{16,255}\b",
        "high",
        "OpenAI-style API key",
    ),
    _rule(
        "jwt",
        r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\b",
        "medium",
        "Hardcoded JSON Web Token",
    ),
    _rule(
        "generic_assignment",
        r"(?i)\b(password|passwd|secret|api[_-]?key|auth[_-]?token|access[_-]?token)\b\s*[:=]\s*[\"'][^\"'\\\s]{8,}[\"']",
        "medium",
        "Generic credential assignment",
    ),
]

_SEVERITY_ORDER: dict[Severity, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@dataclass(slots=True)
class SecretFinding:
    """A single detection, safe for storage and display."""

    rule_id: str
    severity: Severity
    file: str
    line: int
    preview: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def redact(match_text: str) -> str:
    """Produce a masked preview like ``nvapi-••••••a3f2``."""
    text = match_text.strip().strip("\"'")
    if len(text) <= _PREVIEW_KEEP * 2:
        return "•" * len(text)
    head, tail = text[:_PREVIEW_KEEP], text[-4:]
    return f"{head}{'•' * 6}{tail}"


def scan_text(text: str, *, file_label: str = "<memory>") -> list[SecretFinding]:
    """Scan one file's text content; returns redacted findings."""
    findings: list[SecretFinding] = []
    lines = text.splitlines()
    for rule in RULES:
        for match in rule.pattern.finditer(text):
            line_number = text.count("\n", 0, match.start()) + 1
            line_content = lines[line_number - 1] if line_number <= len(lines) else ""
            # Redact *any* secret-shaped token on the offending line.
            preview = redact(line_content.strip()[:_MAX_PREVIEW * 2])
            findings.append(
                SecretFinding(
                    rule_id=rule.rule_id,
                    severity=rule.severity,
                    file=file_label,
                    line=line_number,
                    preview=preview[:_MAX_PREVIEW] if preview.startswith("•") else preview[:_MAX_PREVIEW],
                )
            )
    return findings


def scan_files(files: Iterable[tuple[str, str]]) -> list[SecretFinding]:
    """Scan ``(relative_path, content)`` pairs and return sorted findings."""
    findings: list[SecretFinding] = []
    for path, content in files:
        findings.extend(scan_text(content, file_label=path))
    findings.sort(key=lambda f: (_SEVERITY_ORDER[f.severity], f.file, f.line))
    return findings


def scan_repository(root: Path, relative_paths: Iterable[str]) -> list[SecretFinding]:
    """Scan the given relative paths under ``root`` (text files only)."""
    pairs: list[tuple[str, str]] = []
    for relative in relative_paths:
        target = (root / relative)
        try:
            if target.is_file() and target.stat().st_size <= 2_000_000:
                pairs.append((relative, target.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return scan_files(pairs)
