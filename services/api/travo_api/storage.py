"""Object store with per-tenant envelope encryption (docs/06 §2). Local FS in P0; S3/GCS later."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol

from travo_api import crypto


class ObjectStore(Protocol):
    def put(self, tenant_id: str, dek: bytes, data: bytes) -> str: ...
    def get(self, tenant_id: str, dek: bytes, ref: str) -> bytes: ...


class LocalEncryptedStore:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, tenant_id: str, ref: str) -> Path:
        name = str(uuid.UUID(ref))  # refs are opaque uuids; blocks path traversal
        return self.root / str(uuid.UUID(tenant_id)) / name

    def put(self, tenant_id: str, dek: bytes, data: bytes) -> str:
        ref = str(uuid.uuid4())
        path = self._path(tenant_id, ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(crypto.encrypt(dek, data, aad=f"{tenant_id}/{ref}"))
        return ref

    def get(self, tenant_id: str, dek: bytes, ref: str) -> bytes:
        blob = self._path(tenant_id, ref).read_bytes()
        return crypto.decrypt(dek, blob, aad=f"{tenant_id}/{ref}")
