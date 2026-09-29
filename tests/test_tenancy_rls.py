"""Tenant isolation is enforced by Postgres RLS, not only by application code."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from travo_api.db import get_engine, tenant_session

from tests.conftest import create_matter, upload


def _count(tenant_id: str | None, table: str) -> int:
    with get_engine().connect() as c, c.begin():
        if tenant_id:
            c.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": tenant_id})
        return int(c.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())  # noqa: S608


def test_app_role_sees_only_own_tenant(client, make_tenant):
    a, b = make_tenant("A"), make_tenant("B")
    ma = create_matter(client, a)
    upload(client, a, ma["id"])

    for table in ("matters", "documents", "clauses", "routing_decisions", "audit_events"):
        assert _count(a.tenant_id, table) > 0, table
        assert _count(b.tenant_id, table) == 0, table
    assert _count(None, "matters") == 0  # no tenant context → nothing visible
    assert _count(None, "tenants") == 0


def test_cannot_insert_into_other_tenant(make_tenant):
    a, b = make_tenant("A"), make_tenant("B")
    with pytest.raises(DBAPIError, match="row-level security"):
        with tenant_session(a.tenant_id) as s:
            s.execute(
                text(
                    "INSERT INTO matters (tenant_id, number, name, created_by) "
                    "VALUES (:t, 'X-1', 'x', :u)"
                ),
                {"t": b.tenant_id, "u": b.admin_id},
            )


def test_token_for_other_tenant_user_rejected(client, make_tenant):
    a, b = make_tenant("A"), make_tenant("B")
    from travo_api.auth import mint_dev_token

    # User of B presented with A's tenant id: RLS hides the user → 401.
    forged = mint_dev_token(b.admin_id, a.tenant_id)
    r = client.get("/v1/matters", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_cross_tenant_resource_ids_are_404(client, make_tenant):
    a, b = make_tenant("A"), make_tenant("B")
    ma = create_matter(client, a)
    doc = upload(client, a, ma["id"]).json()
    assert client.get(f"/v1/matters/{ma['id']}", headers=b.headers()).status_code == 404
    assert client.get(f"/v1/documents/{doc['id']}", headers=b.headers()).status_code == 404
    assert client.get(f"/v1/matters/{uuid.uuid4()}", headers=a.headers()).status_code == 404


def test_missing_or_bad_token(client, database):
    assert client.get("/v1/matters").status_code == 401
    r = client.get("/v1/matters", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401
