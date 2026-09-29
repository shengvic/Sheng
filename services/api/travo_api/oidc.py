"""Minimal OIDC relying party (authorization code + PKCE; code exchange server-side).

All IdP HTTP goes through `get_http()` so tests can route it to a mock provider.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
import jwt

ALGORITHMS = ["RS256", "ES256", "PS256"]
_TTL = 3600.0
_discovery: dict[str, tuple[float, dict[str, Any]]] = {}
_jwks: dict[str, tuple[float, jwt.PyJWKSet]] = {}


class OidcError(Exception):
    """Sign-in failed. The message is for the audit log, not for the user."""


@lru_cache
def get_http() -> httpx.Client:
    return httpx.Client(timeout=10.0, follow_redirects=False)


def clear_caches() -> None:
    _discovery.clear()
    _jwks.clear()


def discovery(issuer: str) -> dict[str, Any]:
    cached = _discovery.get(issuer)
    if cached and time.monotonic() - cached[0] < _TTL:
        return cached[1]
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    try:
        doc = get_http().get(url).raise_for_status().json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OidcError(f"discovery failed: {type(exc).__name__}") from None
    if doc.get("issuer") != issuer:
        raise OidcError("discovery issuer mismatch")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not str(doc.get(key, "")).startswith(("https://", "http://")):
            raise OidcError(f"discovery missing {key}")
    _discovery[issuer] = (time.monotonic(), doc)
    return doc


def _keyset(jwks_uri: str, refresh: bool = False) -> jwt.PyJWKSet:
    cached = _jwks.get(jwks_uri)
    if cached and not refresh and time.monotonic() - cached[0] < _TTL:
        return cached[1]
    try:
        data = get_http().get(jwks_uri).raise_for_status().json()
        keys = jwt.PyJWKSet.from_dict(data)
    except (httpx.HTTPError, ValueError, jwt.PyJWTError) as exc:
        raise OidcError(f"jwks fetch failed: {type(exc).__name__}") from None
    _jwks[jwks_uri] = (time.monotonic(), keys)
    return keys


def _signing_key(jwks_uri: str, token: str) -> Any:
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except jwt.PyJWTError:
        raise OidcError("malformed id_token") from None
    for refresh in (False, True):  # key rotation: refetch once on unknown kid
        for k in _keyset(jwks_uri, refresh).keys:
            if kid is None or k.key_id == kid:
                return k.key
    raise OidcError("id_token signed with unknown key")


def exchange_code(
    doc: dict[str, Any],
    client_id: str,
    client_secret: str | None,
    code: str,
    verifier: str,
    redirect_uri: str,
) -> dict[str, Any]:
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    try:
        if client_secret:  # confidential client: client_secret_basic
            resp = get_http().post(
                doc["token_endpoint"], data=form, auth=(client_id, client_secret)
            )
        else:  # public client: PKCE only
            resp = get_http().post(doc["token_endpoint"], data=form)
    except httpx.HTTPError as exc:
        raise OidcError(f"token endpoint unreachable: {type(exc).__name__}") from None
    if resp.status_code != 200:
        raise OidcError(f"token endpoint returned {resp.status_code}")
    data = resp.json()
    if "id_token" not in data:
        raise OidcError("no id_token in token response")
    return dict(data)


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str | None
    name: str | None


def verify_id_token(doc: dict[str, Any], id_token: str, client_id: str, nonce: str) -> Identity:
    key = _signing_key(doc["jwks_uri"], id_token)
    try:
        claims = jwt.decode(
            id_token,
            key,
            algorithms=ALGORITHMS,
            audience=client_id,
            issuer=doc["issuer"],
            leeway=60,
            options={"require": ["iss", "aud", "exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise OidcError(f"id_token invalid: {type(exc).__name__}") from None
    if claims.get("nonce") != nonce:
        raise OidcError("nonce mismatch")
    aud = claims.get("aud")
    if isinstance(aud, list) and len(aud) > 1 and claims.get("azp") != client_id:
        raise OidcError("azp mismatch")
    if claims.get("email_verified") is False:
        raise OidcError("email not verified")
    email = claims.get("email") or claims.get("preferred_username")
    return Identity(
        subject=str(claims["sub"]),
        email=str(email).lower() if email and "@" in str(email) else None,
        name=claims.get("name"),
    )
