"""Operator CLI: bootstrap tenants/users (owner connection) and mint dev tokens.

python -m travo_api.cli bootstrap-tenant "Acme Law LLP" admin@acme.test
python -m travo_api.cli add-user <tenant_id> alice@acme.test partner
python -m travo_api.cli mint-token <tenant_id> <user_id>
"""

from __future__ import annotations

import argparse
import uuid
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from travo_api.auth import mint_dev_token
from travo_api.config import check_production, get_settings
from travo_api.crypto import new_dek
from travo_api.db import get_admin_engine, set_tenant
from travo_api.keys import get_kms
from travo_api.models import Tenant, User

if TYPE_CHECKING:
    from travo_rag.sources.fetch import Snapshot


def bootstrap_tenant(name: str, admin_email: str, region: str | None = None) -> tuple[str, str]:
    tenant_id = uuid.uuid4()
    wrapped = get_kms().wrap(str(tenant_id), new_dek())
    with Session(get_admin_engine()) as s, s.begin():
        s.add(
            Tenant(
                id=tenant_id,
                name=name,
                region_cell=region or get_settings().region_cell,
                wrapped_dek=wrapped,
            )
        )
        s.flush()
        user = User(
            tenant_id=tenant_id, email=admin_email, name=admin_email.split("@")[0], role="admin"
        )
        s.add(user)
        s.flush()
        return str(tenant_id), str(user.id)


def add_user(tenant_id: str, email: str, role: str) -> str:
    with Session(get_admin_engine()) as s, s.begin():
        set_tenant(s, tenant_id)
        user = User(
            tenant_id=uuid.UUID(tenant_id), email=email, name=email.split("@")[0], role=role
        )
        s.add(user)
        s.flush()
        return str(user.id)


def main() -> None:
    p = argparse.ArgumentParser(prog="travo")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bootstrap-tenant")
    b.add_argument("name")
    b.add_argument("admin_email")
    b.add_argument("--region")
    u = sub.add_parser("add-user")
    u.add_argument("tenant_id")
    u.add_argument("email")
    u.add_argument("role", choices=["partner", "associate", "km", "admin"])
    t = sub.add_parser("mint-token")
    t.add_argument("tenant_id")
    t.add_argument("user_id")
    t.add_argument("--ttl", type=int, default=3600)
    w = sub.add_parser("worker")
    w.add_argument("--once", action="store_true", help="drain the queue once and exit")
    w.add_argument("--poll", type=float, default=2.0)
    sub.add_parser("dev-token", help="demo tenant + partner; prints a 12h token (dev only)")
    c = sub.add_parser("configure-idp", help="set a firm's OIDC identity provider")
    c.add_argument("tenant_id")
    c.add_argument("issuer")
    c.add_argument("client_id")
    c.add_argument("--domain", action="append", required=True)
    c.add_argument("--client-secret")
    lf = sub.add_parser("legal-fetch", help="fetch + parse official statutes (docs/04 §9)")
    lf.add_argument("--jurisdiction", "-j", action="append", help="SG, MY (default: all)")
    lf.add_argument("--only", action="append", help="instrument id, e.g. SG/UCTA1977")
    lf.add_argument("--offline", action="store_true", help="re-parse stored snapshots only")
    lf.add_argument("--out", default="out/legal")
    sub.add_parser("migrate", help="apply migrations and ensure the app login role (deploy)")
    li = sub.add_parser("legal-import", help="store a supplied official file as a snapshot")
    li.add_argument("file")
    li.add_argument("--id", required=True, dest="instrument", help="manifest id, e.g. MY/ACT136")
    li.add_argument("--url", help="official URL of this file, if known")
    lv = sub.add_parser("legal-verify", help="record a lawyer's check of a legal source")
    lv.add_argument("source_id")
    lv.add_argument("--by", required=True, help="reviewing lawyer's email")
    lv.add_argument("--note")
    i = sub.add_parser("ingest-legal")
    i.add_argument("path")
    args = p.parse_args()
    if args.cmd == "bootstrap-tenant":
        tid, uid = bootstrap_tenant(args.name, args.admin_email, args.region)
        print(f"tenant_id={tid}\nadmin_user_id={uid}")
    elif args.cmd == "add-user":
        print(add_user(args.tenant_id, args.email, args.role))
    elif args.cmd == "mint-token":
        print(mint_dev_token(args.user_id, args.tenant_id, args.ttl))
    elif args.cmd == "dev-token":
        print(dev_token())
    elif args.cmd == "configure-idp":
        print(
            configure_idp(
                args.tenant_id, args.issuer, args.client_id, args.domain, args.client_secret
            )
        )
    elif args.cmd == "legal-fetch":
        legal_fetch(args.jurisdiction, args.only, args.offline, args.out)
    elif args.cmd == "migrate":
        migrate()
    elif args.cmd == "legal-import":
        snap = legal_import(args.file, args.instrument, args.url)
        print(f"{args.instrument}: stored {snap.path} (sha256 {snap.sha256[:12]}…)")
        print(f"next: legal-fetch -j {args.instrument[:2]} --offline, then read the review report")
    elif args.cmd == "legal-verify":
        if not legal_verify(args.source_id, args.by, args.note):
            raise SystemExit(f"unknown legal source {args.source_id}")
        print(f"{args.source_id} marked verified by {args.by}")
    elif args.cmd == "worker":
        run_worker(args.once, args.poll)
    else:
        print(f"loaded {ingest_legal(args.path)} legal units")


def migrate() -> None:
    """Deploy step: alembic upgrade head on the owner connection, then create/update the app
    login role named in TRAVO_DATABASE_URL (its password comes from that URL, never a file)."""
    from pathlib import Path

    import psycopg
    from alembic import command
    from alembic.config import Config
    from psycopg import sql
    from sqlalchemy.engine import make_url

    s = get_settings()
    check_production(s)
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("sqlalchemy.url", s.admin_database_url.replace("%", "%%"))
    command.upgrade(cfg, "head")
    app = make_url(s.database_url)
    if not app.username or not app.password:
        raise SystemExit("TRAVO_DATABASE_URL must include the app role's user and password")
    role, password = sql.Identifier(app.username), sql.Literal(app.password)
    admin = make_url(s.admin_database_url).set(drivername="postgresql")
    with psycopg.connect(admin.render_as_string(hide_password=False)) as conn:
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (app.username,))
        verb = "ALTER" if exists.fetchone() else "CREATE"
        conn.execute(sql.SQL(verb + " ROLE {} LOGIN PASSWORD {}").format(role, password))
        conn.execute(sql.SQL("GRANT travo_app TO {}").format(role))
    print(f"migrations applied; role {app.username} ready")


def run_worker(once: bool, poll: float) -> None:
    import time

    check_production(get_settings())

    from travo_api.reviews import runner
    from travo_api.workflows import worker_id

    wid, r = worker_id(), runner()
    print(f"worker {wid} started")
    while True:
        n = r.drain(wid)
        if n:
            print(f"processed {n} review run(s)")
        if once:
            return
        time.sleep(poll)


def ingest_legal(path: str) -> int:
    from travo_rag.legal_index import read_jsonl, upsert_units

    units = read_jsonl(path)
    with get_admin_engine().begin() as conn:
        return upsert_units(conn, units)


DEV_TENANT = "Travo Demo LLP"


def dev_token() -> str:
    """Development only: reuse (or create) a demo tenant and partner and mint a 12h token."""
    from sqlalchemy import select

    with Session(get_admin_engine()) as s:
        tenant = s.scalar(select(Tenant).where(Tenant.name == DEV_TENANT))
        partner = (
            s.scalar(select(User).where(User.tenant_id == tenant.id, User.role == "partner"))
            if tenant
            else None
        )
        tid, uid = (str(tenant.id), str(partner.id)) if tenant and partner else (None, None)
    if tid is None:
        tid, _admin = bootstrap_tenant(DEV_TENANT, "admin@demo.travo.test")
        uid = add_user(tid, "partner@demo.travo.test", "partner")
    return mint_dev_token(str(uid), tid, 12 * 3600)


def configure_idp(
    tenant_id: str, issuer: str, client_id: str, domains: list[str], secret: str | None
) -> str:
    from sqlalchemy import delete, select

    from travo_api.keys import encrypt_idp_secret
    from travo_api.models import IdpDomain, TenantIdp

    with Session(get_admin_engine()) as s, s.begin():
        set_tenant(s, tenant_id)
        row = s.scalar(select(TenantIdp).where(TenantIdp.tenant_id == uuid.UUID(tenant_id)))
        if row is None:
            row = TenantIdp(tenant_id=uuid.UUID(tenant_id), issuer=issuer, client_id=client_id)
            s.add(row)
            s.flush()
        row.issuer, row.client_id, row.enabled = issuer.rstrip("/"), client_id, True
        if secret:
            row.client_secret_ciphertext = encrypt_idp_secret(s, tenant_id, row.id, secret)
        s.execute(delete(IdpDomain).where(IdpDomain.idp_id == row.id))
        for d in sorted({d.lower().strip() for d in domains}):
            s.add(IdpDomain(domain=d, idp_id=row.id, tenant_id=row.tenant_id))
        return str(row.id)


def legal_fetch(
    jurisdictions: list[str] | None, only: list[str] | None, offline: bool, out: str
) -> None:
    import os
    from pathlib import Path

    import httpx
    from travo_rag.sources.fetch import PoliteFetcher, SnapshotStore
    from travo_rag.sources.manifest import load_manifests
    from travo_rag.sources.pipeline import run, write_outputs

    s = get_settings()
    manifests = load_manifests(s.legal_manifest_dir)
    wanted = [j.upper() for j in jurisdictions] if jurisdictions else sorted(manifests)
    contact = os.environ.get("TRAVO_FETCH_CONTACT", "set TRAVO_FETCH_CONTACT")
    fetcher = None
    if not offline:
        fetcher = PoliteFetcher(
            httpx.Client(timeout=60.0),
            user_agent=f"TravoLegalFetcher/0.1 (+{contact})",
        )
    store = SnapshotStore(s.legal_snapshot_dir)
    for jur in wanted:
        if jur not in manifests:
            raise SystemExit(f"no manifest for {jur}")
        outcomes = run(manifests[jur], store, fetcher, only=set(only) if only else None)
        jsonl, report, n = write_outputs(outcomes, jur, Path(out))
        for o in outcomes:
            print(f"  {o.id:<16} {o.status:<13} {len(o.units):>4} sections  {o.detail}")
        print(f"{jur}: {n} units → {jsonl}; review report → {report}")


def legal_import(file: str, instrument_id: str, url: str | None) -> Snapshot:
    """Store a file someone obtained from the official portal (e.g. an AGC PDF) as a snapshot."""
    from pathlib import Path

    from travo_rag.sources.fetch import SnapshotStore
    from travo_rag.sources.manifest import load_manifests

    s = get_settings()
    manifest = load_manifests(s.legal_manifest_dir).get(instrument_id[:2].upper())
    found = [i for i in manifest.instruments if i.id == instrument_id] if manifest else []
    inst = found[0] if found else None
    if inst is None:
        raise SystemExit(f"{instrument_id} is not in config/legal_sources — add it there first")
    if url and not url.startswith("https://"):
        raise SystemExit("--url must be an https:// link to the official portal")
    path = Path(file)
    content = path.read_bytes()
    if inst.format == "pdf" and not content.startswith(b"%PDF"):
        raise SystemExit(f"{file} is not a PDF but {instrument_id} expects format pdf")
    ctype = {
        "pdf": "application/pdf",
        "sso_html": "text/html",
        "vbpl_html": "text/html",
        "text": "text/plain",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    return SnapshotStore(s.legal_snapshot_dir).save(
        inst, url or inst.url, content, ctype[inst.format], origin="supplied", filename=path.name
    )


def legal_verify(source_id: str, by: str, note: str | None) -> bool:
    from travo_rag.legal_index import verify_source

    with get_admin_engine().begin() as conn:
        return verify_source(conn, source_id, by, note)


if __name__ == "__main__":
    main()
