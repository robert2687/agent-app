"""Tests for the secret scanner and redaction behaviour."""

from __future__ import annotations

from app.services.secret_scanner import redact, scan_files, scan_text


class TestScanText:
    def test_detects_aws_access_key(self) -> None:
        findings = scan_text("aws_key = 'AKIAIOSFODNN7EXAMPLE'\n", file_label="config.py")
        assert any(f.rule_id == "aws_access_key_id" for f in findings)

    def test_detects_github_token(self) -> None:
        findings = scan_text(
            "token = 'ghp_" + "A" * 36 + "'\n", file_label="settings.py"
        )
        assert any(f.rule_id == "github_pat" for f in findings)

    def test_detects_nvidia_key(self) -> None:
        findings = scan_text("NVIDIA_KEY=nvapi-" + "z" * 40 + "\n", file_label=".env")
        assert any(f.rule_id == "nvidia_api_key" for f in findings)

    def test_detects_private_key_block(self) -> None:
        findings = scan_text(
            "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n",
            file_label="id_rsa",
        )
        assert any(f.rule_id == "private_key_block" for f in findings)

    def test_detects_generic_assignment(self) -> None:
        findings = scan_text('password = "hunter2hunter2"\n', file_label="app.py")
        assert any(f.rule_id == "generic_assignment" for f in findings)

    def test_clean_code_has_no_findings(self) -> None:
        findings = scan_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n", file_label="math.py"
        )
        assert findings == []

    def test_findings_are_redacted(self) -> None:
        secret = "AKIA" + "B" * 16
        findings = scan_text(f"key = '{secret}'\n", file_label="cfg.py")
        for finding in findings:
            assert secret not in finding.preview


class TestScanFiles:
    def test_aggregates_and_sorts_by_severity(self) -> None:
        files = [
            ("low.py", 'password = "123456789abc"\n'),
            ("crit.py", "-----BEGIN PRIVATE KEY-----\n"),
        ]
        findings = scan_files(files)
        assert findings[0].severity == "critical"
        assert {f.file for f in findings} == {"low.py", "crit.py"}


class TestRedact:
    def test_long_secrets_masked(self) -> None:
        masked = redact("nvapi-" + "a" * 50)
        assert "a" * 50 not in masked
        assert masked.startswith("nvapi-")

    def test_short_secrets_fully_masked(self) -> None:
        assert set(redact("short")) == {"•"}
