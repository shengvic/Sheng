"""Operator CLI: bootstrap tenants/users (owner connection) and mint dev tokens.

python -m travo_api.cli bootstrap-tenant "Acme Law LLP" admin@acme.test
python -m travo_api.cli add-user <tenant_id> alice@acme.test partner
python -m travo_api.cli mint-token <tenant_id> <user_id>
"""

from __future__ import annotations

import argparse
import uuid

from sqlalchemy.orm import Session

from travo_api.auth import mint_dev_token
from travo_api.config import get_settings
from travo_api.crypto import new_dek
from travo_api.db import get_admin_engine, set_tenant
from travo_api.keys import get_kms
from travo_api.models import Tenant, User


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
    elif args.cmd == "worker":
        run_worker(args.once, args.poll)
    else:
        print(f"loaded {ingest_legal(args.path)} legal units")


def run_worker(once: bool, poll: float) -> None:
    import time

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


if __name__ == "__main__":
    main()
