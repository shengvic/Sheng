from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from travo_api.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_admin_engine() -> Engine:
    return create_engine(get_settings().admin_database_url, pool_pre_ping=True)


def set_tenant(session: Session, tenant_id: str) -> None:
    """Scope the current transaction to one tenant; RLS policies read this setting."""
    session.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": tenant_id})


def after_commit(session: Session, fn: Callable[[], None]) -> None:
    """Run `fn` once this tenant session's transaction has committed (not on rollback)."""
    session.info.setdefault("after_commit", []).append(fn)


@contextmanager
def tenant_session(tenant_id: str, engine: Engine | None = None) -> Iterator[Session]:
    factory = sessionmaker(bind=engine or get_engine(), expire_on_commit=False)
    with factory() as session:
        with session.begin():
            set_tenant(session, tenant_id)
            yield session
        for fn in session.info.pop("after_commit", []):
            fn()
