"""Tenant data keys and BYO provider credentials."""

from __future__ import annotations

import uuid
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from travo_api import crypto
from travo_api.config import get_settings
from travo_api.models import ProviderCredential, Tenant


@lru_cache
def get_kms() -> crypto.Kms:
    return crypto.LocalKms(get_settings().master_key)


def tenant_dek(session: Session, tenant_id: str) -> bytes:
    tenant = session.get(Tenant, uuid.UUID(tenant_id))
    if tenant is None:
        raise LookupError("tenant not visible in this session")
    return get_kms().unwrap(tenant_id, tenant.wrapped_dek)


def _cred_aad(tenant_id: str, provider: str) -> str:
    return f"{tenant_id}/provider/{provider}"


def store_credential(session: Session, tenant_id: str, provider: str, api_key: str) -> None:
    dek = tenant_dek(session, tenant_id)
    blob = crypto.encrypt(dek, api_key.encode(), _cred_aad(tenant_id, provider))
    row = session.scalar(
        select(ProviderCredential).where(
            ProviderCredential.tenant_id == uuid.UUID(tenant_id),
            ProviderCredential.provider == provider,
        )
    )
    if row is None:
        row = ProviderCredential(tenant_id=uuid.UUID(tenant_id), provider=provider)
        session.add(row)
    row.ciphertext = blob
    row.last4 = api_key[-4:]
    row.status = "active"


def load_credential(session: Session, tenant_id: str, provider: str) -> str | None:
    row = session.scalar(
        select(ProviderCredential).where(
            ProviderCredential.provider == provider, ProviderCredential.status == "active"
        )
    )
    if row is None:
        return None
    dek = tenant_dek(session, tenant_id)
    return crypto.decrypt(dek, row.ciphertext, _cred_aad(tenant_id, provider)).decode()


def _idp_aad(tenant_id: str, idp_id: object) -> str:
    return f"{tenant_id}/idp/{idp_id}"


def encrypt_idp_secret(session: Session, tenant_id: str, idp_id: object, secret: str) -> bytes:
    return crypto.encrypt(
        tenant_dek(session, tenant_id), secret.encode(), _idp_aad(tenant_id, idp_id)
    )


def decrypt_idp_secret(session: Session, tenant_id: str, idp_id: object, blob: bytes) -> str:
    return crypto.decrypt(
        tenant_dek(session, tenant_id), blob, _idp_aad(tenant_id, idp_id)
    ).decode()
