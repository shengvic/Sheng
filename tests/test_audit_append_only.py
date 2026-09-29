import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from travo_api.db import get_admin_engine, tenant_session

from tests.conftest import create_matter


@pytest.mark.parametrize("table", ["audit_events", "routing_decisions"])
@pytest.mark.parametrize("stmt", ["UPDATE {t} SET tenant_id = tenant_id", "DELETE FROM {t}"])
def test_append_only_even_for_owner(client, make_tenant, table, stmt):
    t = make_tenant()
    create_matter(client, t)
    # Owner/superuser bypasses RLS and grants, but not the trigger.
    with pytest.raises(DBAPIError, match="append-only"):
        with get_admin_engine().begin() as c:
            c.execute(text(stmt.format(t=table)))


def test_app_role_has_no_update_grant(make_tenant):
    t = make_tenant()
    with pytest.raises(DBAPIError, match="permission denied"):
        with tenant_session(t.tenant_id) as s:
            s.execute(text("UPDATE audit_events SET action = 'x'"))
