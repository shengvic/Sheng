"""Durable Postgres step runner (ADR-013): resume, retries, leases, tenant isolation."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from travo_api.db import get_engine, tenant_session
from travo_api.models import ReviewRun
from travo_api.reviews import STEPS
from travo_api.workflows import ReviewConfig, WorkflowRunner, claim

from tests.conftest import create_matter, upload

CFG = ReviewConfig(
    steps=["prepare", "compare", "lawcheck", "redline", "memo"],
    max_attempts=3,
    lease_seconds=60,
    retry_backoff_seconds=[0],
)


def _enqueue(client, t):
    WorkflowRunner(STEPS, CFG).drain("cleanup")  # leave no other claimable runs behind
    m = create_matter(client, t)
    doc = upload(client, t, m["id"]).json()
    r = client.post(f"/v1/documents/{doc['id']}/reviews", json={}, headers=t.headers())
    return r.json()["id"]


def _counting_steps(run_id: str, fail_once: str | None = None):
    calls: dict[str, int] = {}
    failed = {"done": False}

    def wrap(name, fn):
        def step(sc):
            if str(sc.run.id) != run_id:
                return fn(sc)
            calls[name] = calls.get(name, 0) + 1
            if name == fail_once and not failed["done"]:
                failed["done"] = True
                raise RuntimeError("simulated crash")
            return fn(sc)

        return step

    return {n: wrap(n, f) for n, f in STEPS.items()}, calls


def test_resume_after_failure_skips_completed_steps(client, make_tenant):
    t = make_tenant()
    run_id = _enqueue(client, t)
    steps, calls = _counting_steps(run_id, fail_once="lawcheck")
    runner = WorkflowRunner(steps, CFG)
    assert runner.drain("w1") >= 1
    review = client.get(f"/v1/reviews/{run_id}", headers=t.headers()).json()
    assert review["status"] == "completed", review
    assert calls == {"prepare": 1, "compare": 1, "lawcheck": 2, "redline": 1, "memo": 1}
    law = next(s for s in review["steps"] if s["name"] == "lawcheck")
    assert law["attempts"] == 2 and law["error"] is None
    # The failed attempt wrote nothing: findings are not duplicated.
    findings = client.get(f"/v1/reviews/{run_id}/findings", headers=t.headers()).json()
    keys = [f["rule_key"] for f in findings]
    assert len(keys) == len(set(keys))


def test_gives_up_after_max_attempts(client, make_tenant):
    t = make_tenant()
    run_id = _enqueue(client, t)

    def boom(sc):
        raise RuntimeError("always fails")

    runner = WorkflowRunner({**STEPS, "compare": boom}, CFG)
    runner.drain("w1")
    review = client.get(f"/v1/reviews/{run_id}", headers=t.headers()).json()
    assert review["status"] == "failed"
    assert review["attempts"] == 3
    assert "always fails" in review["error"]
    assert claim("w2", CFG) is None or claim("w2", CFG)[0] != run_id


def test_backoff_delays_retry(client, make_tenant):
    t = make_tenant()
    run_id = _enqueue(client, t)

    def boom(sc):
        raise RuntimeError("transient")

    cfg = ReviewConfig(
        steps=CFG.steps, max_attempts=3, lease_seconds=60, retry_backoff_seconds=[3600]
    )
    WorkflowRunner({**STEPS, "prepare": boom}, cfg).run_once("w1")
    review = client.get(f"/v1/reviews/{run_id}", headers=t.headers()).json()
    assert review["status"] == "queued" and review["attempts"] == 1
    claimed = claim("w2", cfg)
    assert claimed is None or str(claimed[0]) != run_id  # not claimable before not_before


def test_expired_lease_is_reclaimed_and_stale_worker_stops(client, make_tenant):
    t = make_tenant()
    run_id = _enqueue(client, t)
    claimed = claim("dead-worker", CFG)
    assert claimed and str(claimed[0]) == run_id
    with tenant_session(t.tenant_id) as s:
        run = s.get(ReviewRun, claimed[0])
        run.lease_expires = datetime.now(UTC) - timedelta(seconds=1)
    runner = WorkflowRunner(STEPS, CFG)
    assert str(runner.run_once("live-worker")) == run_id
    # The dead worker waking up cannot write: its lease is gone.
    runner.execute(claimed[0], claimed[1], "dead-worker")
    review = client.get(f"/v1/reviews/{run_id}", headers=t.headers()).json()
    assert review["status"] == "completed"
    assert all(s["attempts"] == 1 for s in review["steps"])


def test_claim_function_is_the_only_cross_tenant_path(client, make_tenant):
    a, b = make_tenant("A"), make_tenant("B")
    _enqueue(client, a)
    _enqueue(client, b)
    with get_engine().begin() as c:  # app role, no tenant context
        assert c.execute(text("SELECT count(*) FROM review_runs")).scalar_one() == 0
        row = c.execute(text("SELECT * FROM claim_review_run('probe', 1, 3)")).first()
    assert row is not None and len(row) == 2  # ids only
    with tenant_session(a.tenant_id) as s:
        tenants = {r[0] for r in s.execute(text("SELECT tenant_id FROM review_runs"))}
    assert {str(x) for x in tenants} == {a.tenant_id}
