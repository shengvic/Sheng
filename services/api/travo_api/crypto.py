"""Envelope encryption: master key (KMS stand-in) wraps a per-tenant data key (docs/06 §2)."""

from __future__ import annotations

import base64
import os
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE = 12


class Kms(Protocol):
    def wrap(self, tenant_id: str, dek: bytes) -> bytes: ...
    def unwrap(self, tenant_id: str, wrapped: bytes) -> bytes: ...


class LocalKms:
    """P0 KMS. Swap for AWS KMS / GCP KMS / customer-managed keys (BYOK) later."""

    def __init__(self, master_key_b64: str):
        key = base64.b64decode(master_key_b64) if master_key_b64 else b""
        if len(key) != 32:
            raise ValueError("TRAVO_MASTER_KEY must be base64 of 32 random bytes")
        self._aead = AESGCM(key)

    def wrap(self, tenant_id: str, dek: bytes) -> bytes:
        nonce = os.urandom(NONCE)
        return nonce + self._aead.encrypt(nonce, dek, f"tenant:{tenant_id}".encode())

    def unwrap(self, tenant_id: str, wrapped: bytes) -> bytes:
        return self._aead.decrypt(wrapped[:NONCE], wrapped[NONCE:], f"tenant:{tenant_id}".encode())


def new_dek() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def encrypt(dek: bytes, plaintext: bytes, aad: str) -> bytes:
    nonce = os.urandom(NONCE)
    return nonce + AESGCM(dek).encrypt(nonce, plaintext, aad.encode())


def decrypt(dek: bytes, blob: bytes, aad: str) -> bytes:
    return AESGCM(dek).decrypt(blob[:NONCE], blob[NONCE:], aad.encode())
