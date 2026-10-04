"""Tests for token-aware context windowing."""

from __future__ import annotations

from pathlib import Path

from app.services.context_window import build_context_windows, estimate_tokens


def test_estimate_tokens_heuristic() -> None:
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2
    assert estimate_tokens("") == 1


class TestWindowing:
    def test_budget_respected(self, tmp_path: Path) -> None:
        for index in range(20):
            (tmp_path / f"mod_{index:02d}.py").write_text("x = 1\n" * 400)  # ~2000 chars each
        plan = build_context_windows(
            tmp_path,
            [f"mod_{i:02d}.py" for i in range(20)],
            max_tokens_per_window=1000,
            max_windows=10,
        )
        assert plan.windows, "expected at least one window"
        for window in plan.windows:
            assert window.tokens <= 1000

    def test_blocked_files_excluded(self, tmp_path: Path) -> None:
        (tmp_path / "clean.py").write_text("print('hi')\n")
        (tmp_path / "secret.py").write_text("password = 'hunter2hunter2'\n")
        plan = build_context_windows(
            tmp_path, ["clean.py", "secret.py"], blocked_files={"secret.py"}
        )
        assert all("secret.py" not in window.files for window in plan.windows)
        assert "secret.py" in plan.skipped_files

    def test_referenced_files_prioritized(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("import a\n")
        (tmp_path / "a.py").write_text("a = 1\n")
        (tmp_path / "z.py").write_text("z = 1\n")
        plan = build_context_windows(
            tmp_path, ["main.py", "a.py", "z.py"], referenced_files=["main.py"], max_tokens_per_window=64
        )
        first_window = plan.windows[0]
        assert first_window.files[0] == "main.py"

    def test_oversized_file_gets_own_truncated_window(self, tmp_path: Path) -> None:
        (tmp_path / "huge.py").write_text("data = '" + "y" * 200_000 + "'\n")
        plan = build_context_windows(tmp_path, ["huge.py"], max_tokens_per_window=500)
        assert len(plan.windows) == 1
        assert plan.windows[0].tokens <= 520
        assert "truncated" in plan.windows[0].content

    def test_content_wrapped_with_file_headers(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("value = 42\n")
        plan = build_context_windows(tmp_path, ["a.py"])
        assert "# ── file: a.py ──" in plan.windows[0].content
        assert "value = 42" in plan.windows[0].content
