"""Test fixtures: ephemeral Postgres 16 with migrations applied and a non-owner app role.

Uses TRAVO_TEST_ADMIN_DATABASE_URL if set (CI service container); otherwise runs initdb/pg_ctl
in a temp dir (as the `postgres` OS user when running as root).
"""

from __future__ import annotations

import base64
import os
import shutil
import socket
import subprocess
import tempfile
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
PG_BIN = Path(os.environ.get("TRAVO_PG_BIN", "/usr/lib/postgresql/16/bin"))
APP_ROLE_PASSWORD = "travo_api_test"  # noqa: S105 - local ephemeral test database only


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _as_pg(cmd: list[str]) -> list[str]:
    return ["runuser", "-u", "postgres", "--", *cmd] if os.geteuid() == 0 else cmd


@pytest.fixture(scope="session")
def admin_url() -> Iterator[str]:
    external = os.environ.get("TRAVO_TEST_ADMIN_DATABASE_URL")
    if external:
        yield external
        return
    tmp = Path(tempfile.mkdtemp(prefix="travo-pg-"))
    data = tmp / "data"
    port = _free_port()
    if os.geteuid() == 0:
        shutil.chown(tmp, "postgres", "postgres")
    tmp.chmod(0o755)
    subprocess.run(
        _as_pg(
            [
                str(PG_BIN / "initdb"),
                "-D",
                str(data),
                "-U",
                "postgres",
                "-A",
                "trust",
                "-E",
                "UTF8",
                "--no-instructions",
            ]
        ),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        _as_pg(
            [
                str(PG_BIN / "pg_ctl"),
                "-D",
                str(data),
                "-l",
                str(tmp / "log"),
                "-w",
                "-o",
                f"-p {port} -k {tmp} -h 127.0.0.1",
                "start",
            ]
        ),
        check=True,
        capture_output=True,
    )
    try:
        yield f"postgresql+psycopg://postgres@127.0.0.1:{port}/postgres"
    finally:
        subprocess.run(
            _as_pg([str(PG_BIN / "pg_ctl"), "-D", str(data), "-m", "immediate", "stop"]),
            capture_output=True,
        )
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="session")
def database(admin_url: str, tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    base, _, _ = admin_url.rpartition("/")
    dbname = f"travo_test_{uuid.uuid4().hex[:8]}"
    root_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with root_engine.connect() as c:
        c.execute(text(f'CREATE DATABASE "{dbname}"'))
    owner_url = f"{base}/{dbname}"

    host_part = base.split("@", 1)[1]
    os.environ.update(
        TRAVO_ADMIN_DATABASE_URL=owner_url,
        TRAVO_DATABASE_URL=f"postgresql+psycopg://travo_api:{APP_ROLE_PASSWORD}@{host_part}/{dbname}",
        TRAVO_MASTER_KEY=base64.b64encode(os.urandom(32)).decode(),
        TRAVO_JWT_SECRET=base64.b64encode(os.urandom(32)).decode(),
        TRAVO_STORAGE_DIR=str(tmp_path_factory.mktemp("objects")),
    )
    for var in ("TRAVO_FIREWORKS_API_KEY", "TRAVO_OPENROUTER_API_KEY", "TRAVO_OIDC_JWKS_URL"):
        os.environ.pop(var, None)
    _clear_caches()

    subprocess.run(
        ["uv", "run", "alembic", "-c", "services/api/alembic.ini", "upgrade", "head"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        env={**os.environ},
    )
    owner = create_engine(owner_url, isolation_level="AUTOCOMMIT")
    with owner.connect() as c:
        exists = c.execute(text("SELECT 1 FROM pg_roles WHERE rolname='travo_api'")).scalar()
        if not exists:
            c.execute(text(f"CREATE ROLE travo_api LOGIN PASSWORD '{APP_ROLE_PASSWORD}'"))
        c.execute(text("GRANT travo_app TO travo_api"))
    owner.dispose()
    from travo_api.cli import ingest_legal

    ingest_legal(str(ROOT / "tests" / "fixtures" / "legal_fixture.jsonl"))
    yield
    _clear_caches()
    with root_engine.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)'))
    root_engine.dispose()


def _clear_caches() -> None:
    from travo_api import config, db, ingest, keys, routing

    for fn in (
        config.get_settings,
        db.get_engine,
        db.get_admin_engine,
        keys.get_kms,
        routing.get_router,
        ingest.get_store,
    ):
        fn.cache_clear()


@dataclass
class TenantFixture:
    tenant_id: str
    admin_id: str
    users: dict[str, str]

    def token(self, who: str = "admin") -> str:
        from travo_api.auth import mint_dev_token

        uid = self.admin_id if who == "admin" else self.users[who]
        return mint_dev_token(uid, self.tenant_id)

    def headers(self, who: str = "admin") -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token(who)}"}


@pytest.fixture
def make_tenant(database: None):
    from travo_api.cli import add_user, bootstrap_tenant

    def _make(name: str = "Firm", roles: dict[str, str] | None = None) -> TenantFixture:
        slug = uuid.uuid4().hex[:6]
        tid, admin = bootstrap_tenant(f"{name} {slug}", f"admin-{slug}@firm.test")
        users = {
            who: add_user(tid, f"{who}-{slug}@firm.test", role)
            for who, role in (roles or {"partner": "partner", "associate": "associate"}).items()
        }
        return TenantFixture(tid, admin, users)

    return _make


@pytest.fixture
def client(database: None):
    from fastapi.testclient import TestClient
    from travo_api.main import create_app
    from travo_api.ratelimit import reset_auth_limits

    reset_auth_limits()
    with TestClient(create_app()) as c:
        yield c


GOLD = ROOT / "evals" / "gold" / "nda"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def upload(
    client, tenant: TenantFixture, matter_id: str, name: str = "sg_mutual_nda", who: str = "admin"
):
    path = GOLD / f"{name}.docx"
    with path.open("rb") as fh:
        return client.post(
            f"/v1/matters/{matter_id}/documents",
            files={"file": (path.name, fh, DOCX_MIME)},
            headers=tenant.headers(who),
        )


def create_matter(client, tenant: TenantFixture, who: str = "admin", **overrides) -> dict:
    body = {
        "number": f"M-{uuid.uuid4().hex[:6]}",
        "name": "Project Lion",
        "jurisdictions": ["SG"],
        **overrides,
    }
    r = client.post("/v1/matters", json=body, headers=tenant.headers(who))
    assert r.status_code == 201, r.text
    return r.json()


def run_reviews() -> int:
    from travo_api.reviews import runner

    return runner().drain("test-worker")


def review_document(
    client,
    tenant: TenantFixture,
    name: str = "sg_mutual_nda",
    who: str = "admin",
    matter: dict | None = None,
) -> tuple[dict, dict, dict]:
    """Upload + start review + run worker. Returns (matter, document, review)."""
    matter = matter or create_matter(
        client, tenant, who=who, jurisdictions=["SG"] if name.startswith("sg") else ["MY"]
    )
    doc = upload(client, tenant, matter["id"], name, who=who).json()
    r = client.post(f"/v1/documents/{doc['id']}/reviews", json={}, headers=tenant.headers(who))
    assert r.status_code == 202, r.text
    run_reviews()
    review = client.get(f"/v1/reviews/{r.json()['id']}", headers=tenant.headers(who)).json()
    return matter, doc, review
