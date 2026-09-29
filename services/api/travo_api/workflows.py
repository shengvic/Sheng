"""Durable review runs on Postgres (ADR-013). Temporal can replace this behind the same API.

- A run is a fixed list of named steps. Each step executes in its own transaction together
  with the rows it writes and the step's `completed` marker, so a crash leaves either nothing
  or a completed step. Resuming skips completed steps.
- Workers claim runs across tenants only through `claim_review_run()` (returns ids); all work
  then happens in `tenant_session(tenant_id)` so RLS applies.
"""

from __future__ import annotations

import logging
import socket
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import yaml
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from travo_api.config import get_settings
from travo_api.db import get_engine, tenant_session
from travo_api.models import ReviewRun, ReviewStep

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReviewConfig:
    steps: list[str]
    max_attempts: int = 3
    lease_seconds: int = 300
    retry_backoff_seconds: list[int] = field(default_factory=lambda: [5, 30, 120])
    thresholds: dict[str, float] = field(default_factory=dict)
    few_shot_examples: int = 3


@lru_cache
def get_review_config() -> ReviewConfig:
    data = yaml.safe_load(get_settings().review_config_file.read_text())
    return ReviewConfig(**data)


@dataclass
class StepContext:
    session: Session
    tenant_id: str
    run: ReviewRun
    outputs: dict[str, dict[str, Any]]  # outputs of completed earlier steps


StepFn = Callable[[StepContext], dict[str, Any]]


class LeaseLost(RuntimeError):
    pass


def worker_id() -> str:
    return f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"


def claim(worker: str, cfg: ReviewConfig | None = None) -> tuple[uuid.UUID, str] | None:
    cfg = cfg or get_review_config()
    with get_engine().begin() as conn:
        row = conn.execute(
            text("SELECT run_id, tenant_id FROM claim_review_run(:w, :lease, :max)"),
            {"w": worker, "lease": cfg.lease_seconds, "max": cfg.max_attempts},
        ).first()
    return (row[0], str(row[1])) if row else None


class WorkflowRunner:
    def __init__(self, steps: dict[str, StepFn], cfg: ReviewConfig | None = None):
        self.steps = steps
        self.cfg = cfg or get_review_config()

    def run_once(self, worker: str) -> uuid.UUID | None:
        claimed = claim(worker, self.cfg)
        if claimed is None:
            return None
        run_id, tenant_id = claimed
        self.execute(run_id, tenant_id, worker)
        return run_id

    def drain(self, worker: str, limit: int = 100) -> int:
        n = 0
        while n < limit and self.run_once(worker):
            n += 1
        return n

    def execute(self, run_id: uuid.UUID, tenant_id: str, worker: str) -> None:
        for idx, name in enumerate(self.cfg.steps):
            try:
                done = self._step(run_id, tenant_id, worker, idx, name)
            except LeaseLost:
                log.warning("lease lost on run %s; another worker owns it", run_id)
                return
            except Exception as exc:  # noqa: BLE001 - any step failure is recorded and retried
                log.exception("review step %s failed for run %s", name, run_id)
                self._fail(run_id, tenant_id, name, exc)
                return
            if not done:
                return
        with tenant_session(tenant_id) as s:
            run = self._owned(s, run_id, worker)
            run.status = "completed"
            run.finished_at = datetime.now(UTC)
            run.lease_owner = None
            run.lease_expires = None

    def _owned(self, s: Session, run_id: uuid.UUID, worker: str) -> ReviewRun:
        run = s.scalar(select(ReviewRun).where(ReviewRun.id == run_id).with_for_update())
        if run is None or run.lease_owner != worker or run.status != "running":
            raise LeaseLost(str(run_id))
        return run

    def _step(self, run_id: uuid.UUID, tenant_id: str, worker: str, idx: int, name: str) -> bool:
        with tenant_session(tenant_id) as s:
            run = self._owned(s, run_id, worker)
            run.lease_expires = datetime.now(UTC) + timedelta(seconds=self.cfg.lease_seconds)
            steps = {
                st.name: st
                for st in s.scalars(select(ReviewStep).where(ReviewStep.run_id == run_id))
            }
            step = steps.get(name)
            if step is not None and step.status == "completed":
                return True
            if step is None:
                step = ReviewStep(tenant_id=run.tenant_id, run_id=run_id, idx=idx, name=name)
                s.add(step)
            step.attempts = (step.attempts or 0) + 1
            step.started_at = datetime.now(UTC)
            outputs = {n: st.output for n, st in steps.items() if st.status == "completed"}
            out = self.steps[name](
                StepContext(session=s, tenant_id=tenant_id, run=run, outputs=outputs)
            )
            step.output = out
            step.status = "completed"
            step.error = None
            step.finished_at = datetime.now(UTC)
            cost = float(out.get("cost_usd", 0) or 0)
            if cost:
                run.cost_usd = run.cost_usd + type(run.cost_usd)(str(round(cost, 6)))
        return True

    def _fail(self, run_id: uuid.UUID, tenant_id: str, name: str, exc: Exception) -> None:
        message = f"{name}: {type(exc).__name__}: {exc}"[:1000]
        with tenant_session(tenant_id) as s:
            run = s.get(ReviewRun, run_id)
            if run is None:
                return
            step = s.scalar(
                select(ReviewStep).where(ReviewStep.run_id == run_id, ReviewStep.name == name)
            )
            if step is None:
                idx = self.cfg.steps.index(name)
                step = ReviewStep(
                    tenant_id=run.tenant_id, run_id=run_id, idx=idx, name=name, attempts=0
                )
                s.add(step)
            step.attempts = (step.attempts or 0) + 1
            step.error = message
            run.error = message
            run.lease_owner = None
            run.lease_expires = None
            if run.attempts >= self.cfg.max_attempts:
                step.status = "failed"
                run.status = "failed"
                run.finished_at = datetime.now(UTC)
            else:
                backoff = self.cfg.retry_backoff_seconds
                delay = backoff[min(run.attempts - 1, len(backoff) - 1)] if backoff else 0
                run.status = "queued"
                run.not_before = datetime.now(UTC) + timedelta(seconds=delay)
