"""Tests for swarm context helpers (JSON extraction, edit application)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.swarm.context import FileEdit, SwarmContext, parse_json_block
from app.swarm.agents.coder import apply_edits, existing_file_excerpt


class TestParseJsonBlock:
    def test_plain_json(self) -> None:
        assert parse_json_block('{"a": 1}') == {"a": 1}

    def test_fenced_json(self) -> None:
        assert parse_json_block('```json\n{"a": [1, 2]}\n```') == {"a": [1, 2]}

    def test_json_with_prose(self) -> None:
        text = 'Here is the plan:\n{"objective": "x", "steps": []}\nDone.'
        assert parse_json_block(text) == {"objective": "x", "steps": []}

    def test_nested_braces_in_strings(self) -> None:
        assert parse_json_block('{"code": "def f(): return {}"}')["code"] == "def f(): return {}"

    def test_array_first(self) -> None:
        assert parse_json_block('[{"id": 1}]') == [{"id": 1}]

    def test_no_json_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_json_block("no json here at all")


class TestApplyEdits:
    def _ctx(self, tmp_path: Path) -> SwarmContext:
        return SwarmContext(
            job_id="job-1",
            repository_id="repo-1",
            repository_name="owner/repo",
            task="test task",
            workdir=tmp_path,
        )

    async def test_create_modify_delete(self, tmp_path: Path) -> None:
        ctx = self._ctx(tmp_path)
        edits = [
            FileEdit(path="pkg/new.py", action="create", content="value = 1\n"),
            FileEdit(path="pkg/new.py", action="modify", content="value = 2\n"),
        ]
        applied = await apply_edits(ctx, edits)
        assert len(applied) == 2
        assert (tmp_path / "pkg" / "new.py").read_text() == "value = 2\n"

        await apply_edits(ctx, [FileEdit(path="pkg/new.py", action="delete")])
        assert not (tmp_path / "pkg" / "new.py").exists()

    async def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        ctx = self._ctx(tmp_path)
        with pytest.raises(ValueError):
            await apply_edits(
                ctx, [FileEdit(path="../outside.py", action="create", content="nope")]
            )

    async def test_absolute_path_blocked(self, tmp_path: Path) -> None:
        ctx = self._ctx(tmp_path)
        with pytest.raises(ValueError):
            await apply_edits(
                ctx, [FileEdit(path="/etc/evil", action="create", content="nope")]
            )

    def test_existing_file_excerpt(self, tmp_path: Path) -> None:
        ctx = self._ctx(tmp_path)
        (tmp_path / "a.py").write_text("hello\n")
        assert existing_file_excerpt(ctx, "a.py") == "hello\n"
        assert existing_file_excerpt(ctx, "missing.py") == "(file not found)"
        assert "(path outside repository)" in existing_file_excerpt(ctx, "../../etc/passwd")
