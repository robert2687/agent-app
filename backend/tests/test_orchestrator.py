"""End-to-end orchestrator test: full swarm pipeline with a scripted fake LLM.

Covers: context building, Planner→Architect→Coder→Reviewer, edit application,
diff computation, validation (real pytest subprocess), the self-healing
PatcherAgent loop, event persistence and final job state.
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from git import Repo

from app.core.config import Settings
from app.db import dao
from app.db.session import create_engine, create_session_factory
from app.services.event_bus import EventBus
from app.swarm.orchestrator import SwarmOrchestrator


# ── Fake provider router (scripted, deterministic) ──────────────────────────
@dataclass
class FakeStream:
    tokens: list[str]
    prompt_tokens: int = 50
    completion_tokens: int = 20
    provider_id: str = "fake"
    model: str = "fake-model"
    latency_ms: float = 5.0

    def __aiter__(self):
        self._iter = iter(self.tokens)
        return self

    async def __anext__(self) -> str:
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration from None


@dataclass
class FakeRouter:
    scripts: dict[str, list[str]]
    calls: list[str] = field(default_factory=list)
    patcher_runs: int = 0

    async def stream_chat(self, *, messages, purpose, **kwargs):
        self.calls.append(purpose)
        payload = self.scripts[purpose]
        if not isinstance(payload, dict):  # pragma: no cover - guard
            raise TypeError("script payloads must be dicts")
        if purpose == "patcher":
            self.patcher_runs += 1
        text = json.dumps(payload)
        # Yield in token-sized chunks like a real stream.
        chunks = [text[i : i + 64] for i in range(0, len(text), 64)]
        return FakeStream(tokens=chunks)

    async def chat(self, *, messages, purpose, **kwargs):  # pragma: no cover
        raise AssertionError("streaming path expected")

    def release_ledger(self, job_id: str) -> None:  # noqa: ARG002
        return None

    def candidates(self, **kwargs):  # pragma: no cover - route guard only
        return ["fake"]


def _initial_repo(tmp_path: Path) -> Path:
    """A tiny python project whose `add` is (deliberately) broken."""
    workdir = tmp_path / "demo-repo"
    workdir.mkdir()
    (workdir / "calc.py").write_text(
        "def add(a: int, b: int) -> int:\n"
        "    return a - b  # bug: should be a + b\n",
        encoding="utf-8",
    )
    (workdir / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_add():\n"
        "    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    repo = Repo.init(str(workdir), initial_branch="main")
    repo.index.add(["calc.py", "test_calc.py"])
    with repo.config_writer() as config:
        config.set_value("user", "name", "Nexus Test")
        config.set_value("user", "email", "test@nexus.local")
    repo.index.commit("initial broken state")
    return workdir


def _scripts() -> dict[str, dict]:
    coder_edit = {
        "path": "feature.py",
        "action": "create",
        "content": 'def describe() -> str:\n    return "nexus"\n',
    }
    return {
        "planner": {
            "objective": "Add a feature module",
            "steps": [
                {"id": 1, "title": "Create feature module", "detail": "New file.", "files": ["feature.py"]}
            ],
            "risks": [],
            "success_criteria": ["tests pass"],
        },
        "architect": {
            "approach": "Single new module",
            "modules": [{"name": "feature", "path": "feature.py", "responsibility": "Describe", "interfaces": []}],
            "data_flow": "n/a",
            "constraints": [],
            "edit_order": [],
        },
        "coder": {
            "summary": "Adds feature module",
            "edits": [coder_edit],
        },
        "reviewer": {
            "verdict": "approve",
            "summary": "Diff matches the plan.",
            "findings": [],
        },
        "patcher": {
            "rationale": "calc.add subtracts instead of adding.",
            "edits": [
                {
                    "path": "calc.py",
                    "action": "modify",
                    "content": "def add(a: int, b: int) -> int:\n    return a + b\n",
                }
            ],
        },
    }


@pytest.fixture()
def e2e_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'e2e.db'}",
        clone_root=str(tmp_path / "repos"),
        execution_enabled=True,
        execution_timeout_seconds=60,
        lint_command=f"{sys.executable} -m compileall -q .",
        test_command=f"{sys.executable} -m pytest -x -q",
        max_repair_iterations=3,
    )


async def test_full_swarm_pipeline_with_self_healing(tmp_path: Path, e2e_settings: Settings) -> None:
    workdir = _initial_repo(tmp_path)

    engine = create_engine(e2e_settings)
    session_factory = create_session_factory(engine)
    await dao.create_all(engine)

    repo_record = await dao.create_repository(
        session_factory, url="https://github.com/demo/repo", name="demo/repo", depth=1
    )
    await dao.save_snapshot(
        session_factory,
        repo_record.id,
        _snapshot_stub(workdir),
    )

    job = await dao.create_swarm_job(
        session_factory,
        repository_id=repo_record.id,
        task="Add a feature module and make sure the tests pass",
        config={"validation_enabled": True},
        max_repair_iterations=3,
    )

    fake_router = FakeRouter(scripts=_scripts())  # type: ignore[arg-type]
    orchestrator = SwarmOrchestrator(
        settings=e2e_settings,
        session_factory=session_factory,
        bus=EventBus(),
        router=fake_router,  # type: ignore[arg-type]
    )
    orchestrator.launch(job.id)
    for _ in range(120):
        await asyncio.sleep(0.25)
        current = await dao.get_swarm_job(session_factory, job.id)
        assert current is not None
        if current.status in ("completed", "failed", "cancelled"):
            break
    else:
        pytest.fail("Swarm job did not finish in time")

    assert current is not None
    assert current.status == "completed", f"job failed: {current.error}"

    # Self-healing loop ran exactly once and fixed the failing test.
    assert fake_router.patcher_runs == 1
    assert current.repair_iteration == 1
    assert current.validation is not None
    assert current.validation["passed"] is True
    assert (workdir / "calc.py").read_text(encoding="utf-8") == "def add(a: int, b: int) -> int:\n    return a + b\n"
    assert (workdir / "feature.py").exists()

    # Artifacts persisted.
    assert current.plan is not None and current.plan["objective"]
    assert current.architecture is not None
    assert current.review is not None and current.review["verdict"] == "approve"
    assert current.diff and "feature.py" in current.diff

    # Agent call order honoured the pipeline.
    assert fake_router.calls == ["planner", "architect", "coder", "reviewer", "patcher"]

    # Event log persisted the major milestones.
    events = await dao.list_swarm_events(session_factory, job.id)
    event_types = [event.type for event in events]
    for expected in (
        "job.update",
        "context.built",
        "agent.start",
        "agent.complete",
        "edits.applied",
        "validation.result",
        "repair.loop",
        "job.diff",
        "job.completed",
    ):
        assert expected in event_types, f"missing {expected} in {event_types}"

    await engine.dispose()


async def test_validation_failure_exhausts_repair_budget(tmp_path: Path, e2e_settings: Settings) -> None:
    workdir = _initial_repo(tmp_path)

    engine = create_engine(e2e_settings)
    session_factory = create_session_factory(engine)
    await dao.create_all(engine)

    repo_record = await dao.create_repository(
        session_factory, url="https://github.com/demo/repo2", name="demo/repo2", depth=1
    )
    await dao.save_snapshot(session_factory, repo_record.id, _snapshot_stub(workdir))

    job = await dao.create_swarm_job(
        session_factory,
        repository_id=repo_record.id,
        task="Impossible task",
        config={"validation_enabled": True},
        max_repair_iterations=2,
    )

    scripts = _scripts()
    # Patcher never fixes the bug → loop must exhaust after 2 iterations.
    scripts["patcher"] = {
        "rationale": "no-op attempt",
        "edits": [{"path": "notes.md", "action": "create", "content": "attempt\n"}],
    }
    fake_router = FakeRouter(scripts=scripts)  # type: ignore[arg-type]
    orchestrator = SwarmOrchestrator(
        settings=e2e_settings,
        session_factory=session_factory,
        bus=EventBus(),
        router=fake_router,  # type: ignore[arg-type]
    )
    orchestrator.launch(job.id)
    for _ in range(120):
        await asyncio.sleep(0.25)
        current = await dao.get_swarm_job(session_factory, job.id)
        assert current is not None
        if current.status in ("completed", "failed", "cancelled"):
            break
    else:
        pytest.fail("Swarm job did not finish in time")

    assert current is not None
    assert current.status == "failed"
    assert current.repair_iteration == 2
    assert fake_router.patcher_runs == 2
    await engine.dispose()


def _snapshot_stub(workdir: Path):
    from app.services.git_ingestion import RepositorySnapshot

    return RepositorySnapshot(
        url="https://github.com/demo/repo",
        name="demo/repo",
        branch=None,
        default_branch="main",
        head_commit="0" * 40,
        clone_path=str(workdir),
        depth=1,
        files=["calc.py", "test_calc.py"],
        file_count=2,
        total_loc=8,
        languages={"python": 2},
        secret_findings=[],
        dep_graph=None,
    )
