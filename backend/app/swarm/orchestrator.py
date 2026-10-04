"""Swarm Orchestrator: the Planner→Architect→Coder→Reviewer→Patcher pipeline.

Lifecycle
---------
1. ``launch(job_id)`` spawns a supervised asyncio task and returns immediately.
2. The pipeline builds token-aware context windows (secret-bearing files are
   excluded), then runs each agent in order, persisting artifacts and
   streaming every state change to the event bus.
3. The **self-healing loop**: after coding, the validator runs lint + tests.
   Failures (or a blocking review) route failure context back into
   ``PatcherAgent`` for up to ``N`` repair iterations, re-validating each time.
4. The final unified git diff is computed and persisted for the side-by-side
   diff viewer.
"""

from __future__ import annotations

import asyncio
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.db import dao
from app.services.context_window import build_context_windows
from app.services.event_bus import EventBus
from app.services.git_ingestion import list_source_files
from app.services.provider_router import ProviderRouter
from app.swarm.agents.architect import ArchitectAgent
from app.swarm.agents.coder import CoderAgent
from app.swarm.agents.patcher import PatcherAgent
from app.swarm.agents.planner import PlannerAgent
from app.swarm.agents.reviewer import ReviewerAgent, blocking_findings
from app.swarm.context import SwarmContext
from app.swarm.diff_engine import compute_diff, parse_unified_diff, to_payload
from app.swarm.execution import CommandRunner, extract_failing_files, summarize_results

logger = get_logger("nexus.orchestrator")

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


class SwarmOrchestrator:
    """Supervises swarm job execution."""

    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: Any,
        bus: EventBus,
        router: ProviderRouter,
    ) -> None:
        self._settings = settings
        self._sessions = session_factory
        self._bus = bus
        self._router = router
        self._tasks: dict[str, asyncio.Task[None]] = {}

    # ── Public API ─────────────────────────────────────────────────────────
    def launch(self, job_id: str) -> None:
        """Spawn (exactly once) the background pipeline for ``job_id``."""
        if job_id in self._tasks and not self._tasks[job_id].done():
            return
        task = asyncio.create_task(self._run(job_id), name=f"swarm-{job_id}")
        self._tasks[job_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(job_id, None))

    async def cancel(self, job_id: str) -> bool:
        """Request cancellation at the next stage boundary."""
        job = await dao.get_swarm_job(self._sessions, job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} not found.")
        if job.status in TERMINAL_STATUSES:
            return False
        await dao.update_swarm_job(self._sessions, job_id, cancel_requested=True)
        await self._emit(job_id, "job.update", None, {"status": job.status, "cancelling": True})
        return True

    def active_jobs(self) -> list[str]:
        return [job_id for job_id, task in self._tasks.items() if not task.done()]

    # ── Internals ──────────────────────────────────────────────────────────
    async def _emit(
        self,
        job_id: str,
        type_: str,
        agent: str | None,
        data: dict[str, Any],
        *,
        persist: bool = True,
    ) -> None:
        await self._bus.publish(f"job:{job_id}", type_, {"agent": agent, **data})
        if persist:
            await dao.add_swarm_event(
                self._sessions, job_id=job_id, type_=type_, agent=agent, data=data
            )

    async def _set_status(self, job_id: str, status: str, agent: str | None = None) -> None:
        await dao.update_swarm_job(
            self._sessions, job_id, status=status, current_agent=agent
        )
        await self._emit(
            job_id, "job.update", agent, {"status": status, "current_agent": agent}
        )

    async def _is_cancelled(self, job_id: str) -> bool:
        job = await dao.get_swarm_job(self._sessions, job_id)
        return bool(job and job.cancel_requested)

    async def _run(self, job_id: str) -> None:
        try:
            await self._pipeline(job_id)
        except asyncio.CancelledError:
            await dao.update_swarm_job(
                self._sessions,
                job_id,
                status="cancelled",
                finished_at=datetime.now(timezone.utc),
            )
            await self._emit(job_id, "job.cancelled", None, {"reason": "task cancelled"})
        except Exception as exc:  # noqa: BLE001 - final backstop for the pipeline
            logger.error(
                "Swarm job failed",
                extra={"job_id": job_id, "error": str(exc), "trace": traceback.format_exc()},
            )
            await dao.update_swarm_job(
                self._sessions,
                job_id,
                status="failed",
                error=str(exc)[:4000],
                finished_at=datetime.now(timezone.utc),
            )
            await self._emit(job_id, "job.failed", None, {"error": str(exc)[:2000]})
        finally:
            self._router.release_ledger(job_id)

    async def _pipeline(self, job_id: str) -> None:
        job = await dao.get_swarm_job(self._sessions, job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} not found.")
        repo = await dao.get_repository(self._sessions, job.repository_id)
        if repo is None or repo.status != "ready" or not repo.clone_path:
            raise NotFoundError("Repository is not ingested/ready. Ingest it first.")
        workdir = Path(repo.clone_path)
        if not workdir.exists():
            raise NotFoundError(f"Clone directory missing: {workdir}")

        config = job.config or {}
        await dao.update_swarm_job(
            self._sessions, job_id, started_at=datetime.now(timezone.utc), cancel_requested=False
        )

        ctx = SwarmContext(
            job_id=job_id,
            repository_id=repo.id,
            repository_name=repo.name,
            task=job.task,
            workdir=workdir,
            max_repair_iterations=job.max_repair_iterations,
            preferred_model=config.get("preferred_model"),
            preferred_provider_id=config.get("preferred_provider_id"),
        )

        # ── Context construction (token-aware, secret-free) ────────────────
        await self._set_status(job_id, "running")
        ctx.blocked_files = {
            str(finding.get("file", ""))
            for finding in (repo.secret_findings or [])
        }
        ctx.blocked_files.discard("")
        graph = repo.dep_graph if isinstance(repo.dep_graph, dict) else None
        all_files = [str(node["path"]) for node in (graph or {}).get("nodes", [])]  # type: ignore[union-attr]
        if not all_files:
            all_files = await asyncio.to_thread(list_source_files, workdir)
        plan = build_context_windows(
            workdir,
            all_files,
            graph=graph,
            blocked_files=ctx.blocked_files,
            max_tokens_per_window=24_000,
            max_windows=6,
        )
        ctx.context_windows = plan.windows
        await self._emit(
            job_id,
            "context.built",
            None,
            {
                "windows": len(plan.windows),
                "files": len(all_files),
                "skipped": len(plan.skipped_files),
                "estimated_tokens": plan.total_tokens,
                "secret_blocked_files": len(ctx.blocked_files),
            },
        )

        router = self._router
        bus = self._bus

        # ── 1. PlannerAgent ────────────────────────────────────────────────
        await self._set_status(job_id, "planning", "planner")
        await self._emit(job_id, "agent.start", "planner", {"description": "Decomposing task"})
        ctx.plan = await PlannerAgent(router, bus, job_id).run(ctx)
        await dao.update_swarm_job(self._sessions, job_id, plan=ctx.plan, token_usage=ctx.token_usage)
        await self._emit(
            job_id, "agent.complete", "planner",
            {"artifact": {"objective": ctx.plan.get("objective"), "steps": len(ctx.plan.get("steps", []))}},
        )
        await self._check_cancel(job_id)

        # ── 2. ArchitectAgent ──────────────────────────────────────────────
        await self._set_status(job_id, "architecting", "architect")
        await self._emit(job_id, "agent.start", "architect", {"description": "Designing modules"})
        ctx.architecture = await ArchitectAgent(router, bus, job_id).run(ctx)
        await dao.update_swarm_job(
            self._sessions, job_id, architecture=ctx.architecture, token_usage=ctx.token_usage
        )
        await self._emit(
            job_id, "agent.complete", "architect",
            {"artifact": {"modules": len(ctx.architecture.get("modules", []))}},
        )
        await self._check_cancel(job_id)

        # ── 3. CoderAgent ──────────────────────────────────────────────────
        await self._set_status(job_id, "coding", "coder")
        await self._emit(job_id, "agent.start", "coder", {"description": "Implementing edits"})
        coder = CoderAgent(router, bus, job_id)
        edits = await coder.run(ctx)
        ctx.edits = edits
        await self._emit(
            job_id,
            "edits.applied",
            "coder",
            {
                "count": len(edits),
                "summary": coder._last_summary,  # noqa: SLF001 - orchestrator-owned agent
                "files": [edit.to_dict() | {"content": ""} for edit in edits],
            },
        )
        await dao.update_swarm_job(
            self._sessions,
            job_id,
            edits=[e.to_dict() for e in ctx.edits],
            token_usage=ctx.token_usage,
        )
        await self._emit(
            job_id, "agent.complete", "coder", {"artifact": {"edits": len(ctx.edits)}}
        )
        await self._check_cancel(job_id)

        # ── 4. Diff + ReviewerAgent ────────────────────────────────────────
        diff_text = await compute_diff(workdir)
        await self._set_status(job_id, "reviewing", "reviewer")
        await self._emit(job_id, "agent.start", "reviewer", {"description": "Reviewing diff"})
        ctx.review = await ReviewerAgent(router, bus, job_id).run(ctx, diff_text)
        await dao.update_swarm_job(
            self._sessions, job_id, review=ctx.review, token_usage=ctx.token_usage
        )
        await self._emit(
            job_id, "agent.complete", "reviewer",
            {"artifact": {"verdict": ctx.review.get("verdict"), "findings": len(ctx.review.get("findings", []))}},
        )
        await self._check_cancel(job_id)

        # ── 5. Static-review repair (reviewer demanded revision) ───────────
        if config.get("validation_enabled", True) and ctx.review.get("verdict") == "revise":
            blockers = blocking_findings(ctx.review)
            if blockers and ctx.max_repair_iterations > 0 and ctx.repair_iteration < ctx.max_repair_iterations:
                ctx.validation = _review_failure_context(ctx.review)
                await self._emit(
                    job_id, "repair.loop", None,
                    {"trigger": "review", "iteration": ctx.repair_iteration + 1,
                     "findings": len(blockers)},
                )
                await self._repair_pass(job_id, ctx)

        # ── 6. Self-healing validation loop ────────────────────────────────
        if config.get("validation_enabled", True):
            runner = CommandRunner(timeout_seconds=self._settings.execution_timeout_seconds)
            known_files = set(all_files) | {edit.path for edit in ctx.edits}
            ctx.validation = await self._validate(job_id, ctx, runner, known_files)

            while (
                not ctx.validation.get("passed", True)
                and ctx.repair_iteration < ctx.max_repair_iterations
            ):
                await self._check_cancel(job_id)
                ctx.validation["failing_files"] = extract_failing_files(
                    str(ctx.validation.get("tests", {}).get("output", ""))
                    + str(ctx.validation.get("lint", {}).get("output", "")),
                    known_files,
                )
                await self._emit(
                    job_id, "repair.loop", None,
                    {"trigger": "validation", "iteration": ctx.repair_iteration + 1,
                     "failing_files": ctx.validation.get("failing_files", [])},
                )
                await self._repair_pass(job_id, ctx)
                ctx.validation = await self._validate(job_id, ctx, runner, known_files)

            if not ctx.validation.get("passed", True):
                raise RuntimeError(
                    f"Validation still failing after {ctx.repair_iteration} repair "
                    f"iteration(s): see job validation artifact."
                )

        # ── 7. Finalize ────────────────────────────────────────────────────
        final_diff = await compute_diff(workdir)
        parsed = parse_unified_diff(final_diff)
        await dao.update_swarm_job(
            self._sessions,
            job_id,
            status="completed",
            current_agent=None,
            diff=final_diff,
            validation=ctx.validation,
            token_usage=ctx.token_usage,
            finished_at=datetime.now(timezone.utc),
        )
        await self._emit(
            job_id, "job.diff", None,
            {"files": len(parsed.files), "additions": parsed.additions, "deletions": parsed.deletions},
        )
        await self._emit(
            job_id, "job.completed", None,
            {
                "status": "completed",
                "edits": len(ctx.edits),
                "repairs": ctx.repair_iteration,
                "token_usage": ctx.token_usage,
                "diff": to_payload(job_id, parsed),
            },
        )

    async def _repair_pass(self, job_id: str, ctx: SwarmContext) -> None:
        """One PatcherAgent iteration: heal → merge edits → persist state."""
        await self._set_status(job_id, "patching", "patcher")
        ctx.repair_iteration += 1
        await self._emit(
            job_id, "agent.start", "patcher",
            {"description": f"Repair iteration {ctx.repair_iteration}/{ctx.max_repair_iterations}"},
        )
        patcher = PatcherAgent(self._router, self._bus, job_id)
        repairs = await patcher.run(ctx)
        ctx.edits.extend(repairs)
        await self._emit(
            job_id,
            "edits.applied",
            "patcher",
            {
                "count": len(repairs),
                "summary": patcher._last_summary,  # noqa: SLF001 - orchestrator-owned agent
                "files": [edit.to_dict() | {"content": ""} for edit in repairs],
            },
        )
        await dao.update_swarm_job(
            self._sessions,
            job_id,
            edits=[e.to_dict() for e in ctx.edits],
            repair_iteration=ctx.repair_iteration,
            token_usage=ctx.token_usage,
        )
        await self._emit(
            job_id, "agent.complete", "patcher",
            {"artifact": {"repairs": len(repairs), "iteration": ctx.repair_iteration}},
        )

    async def _validate(
        self,
        job_id: str,
        ctx: SwarmContext,
        runner: CommandRunner,
        known_files: set[str],
    ) -> dict[str, Any]:
        """Run lint + tests; persist + broadcast the result."""
        if not self._settings.execution_enabled:
            return {"passed": True, "skipped": True, "reason": "execution disabled"}
        await self._set_status(job_id, "validating", "validator")
        lint = await runner.run(ctx.workdir, self._settings.lint_command)
        tests = await runner.run(ctx.workdir, self._settings.test_command)
        validation = summarize_results(lint, tests)
        validation["failing_files"] = extract_failing_files(
            lint.output + tests.output, known_files
        )
        await dao.update_swarm_job(
            self._sessions, job_id, validation=validation, token_usage=ctx.token_usage
        )
        await self._emit(
            job_id, "validation.result", "validator",
            {
                "passed": validation["passed"],
                "lint_ok": lint.ok,
                "tests_ok": tests.ok,
                "lint_excerpt": lint.output[:600],
                "tests_excerpt": tests.output[:600],
            },
        )
        return validation

    async def _check_cancel(self, job_id: str) -> None:
        if await self._is_cancelled(job_id):
            await dao.update_swarm_job(
                self._sessions,
                job_id,
                status="cancelled",
                finished_at=datetime.now(timezone.utc),
            )
            await self._emit(job_id, "job.cancelled", None, {"reason": "cancelled by operator"})
            raise asyncio.CancelledError


def _review_failure_context(review: dict[str, Any]) -> dict[str, Any]:
    """Convert blocking review findings into PatcherAgent-compatible context."""
    lines = [
        f"[{finding.get('severity', 'major')}] {finding.get('file', '?')}: "
        f"{finding.get('message', '')} → {finding.get('suggestion', '')}"
        for finding in blocking_findings(review)
    ]
    return {
        "passed": False,
        "lint": {
            "command": "(static review via ReviewerAgent)",
            "exit_code": 1,
            "output": "Blocking review findings:\n" + "\n".join(lines),
        },
        "tests": {"command": "(not run)", "exit_code": 0, "output": ""},
    }
