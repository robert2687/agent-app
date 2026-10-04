"""Tests for the diff engine (unified diff parsing)."""

from __future__ import annotations

from pathlib import Path

from app.swarm.diff_engine import compute_diff, parse_unified_diff, to_payload


SAMPLE_DIFF = """diff --git a/app.py b/app.py
index 1111111..2222222 100644
--- a/app.py
+++ b/app.py
@@ -1,3 +1,4 @@
 import os
+import sys
 
 def main():
diff --git a/new_file.py b/new_file.py
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,2 @@
+def hello():
+    return "world"
"""


class TestParseUnifiedDiff:
    def test_counts(self) -> None:
        parsed = parse_unified_diff(SAMPLE_DIFF)
        assert len(parsed.files) == 2
        assert parsed.additions == 3
        assert parsed.deletions == 0

    def test_file_flags(self) -> None:
        parsed = parse_unified_diff(SAMPLE_DIFF)
        by_path = {f.path: f for f in parsed.files}
        assert by_path["app.py"].is_new is False
        assert by_path["new_file.py"].is_new is True

    def test_hunk_lines(self) -> None:
        parsed = parse_unified_diff(SAMPLE_DIFF)
        app_py = next(f for f in parsed.files if f.path == "app.py")
        hunk = app_py.hunks[0]
        new_text = [line for _, line in hunk.new_lines]
        assert "import sys" in new_text
        assert "import os" in new_text

    def test_empty_diff(self) -> None:
        parsed = parse_unified_diff("")
        assert parsed.files == []
        assert parsed.additions == 0

    def test_payload_shape(self) -> None:
        parsed = parse_unified_diff(SAMPLE_DIFF)
        payload = to_payload("job-1", parsed)
        assert payload["job_id"] == "job-1"
        assert len(payload["files"]) == 2  # type: ignore[arg-type]


class TestComputeDiff:
    async def test_real_git_diff(self, tmp_path: Path) -> None:
        import subprocess

        def run(*args: str) -> None:
            subprocess.run(
                ["git", *args], cwd=str(tmp_path), check=True,
                capture_output=True, env={
                    "PATH": "/usr/bin:/bin:/usr/local/bin",
                    "HOME": str(tmp_path),
                    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                },
            )

        run("init", "-q", "-b", "main")
        (tmp_path / "a.txt").write_text("one\n")
        run("add", "-A")
        run("commit", "-q", "-m", "init")
        (tmp_path / "a.txt").write_text("one\ntwo\n")
        (tmp_path / "b.txt").write_text("new\n")

        diff = await compute_diff(tmp_path)
        assert "b.txt" in diff
        assert "+two" in diff
