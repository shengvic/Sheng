"""Mock OpenID Connect provider for tests and local e2e — never for production.

Implements discovery, authorize (auto-approves the user named by `login_hint`), token (auth code
+ PKCE S256, optional client secret), and JWKS, with a fresh RS256 key per process.

    uv run python -m scripts.mock_oidc --port 8791 --client-id travo-web \\
        --user wei.ling@lionpartners.test
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def pkce_challenge(verifier: str) -> str:
    return _b64url(hashlib.sha256(verifier.encode()).digest())


@dataclass
class MockIdP:
    issuer: str
    client_id: str
    client_secret: str | None = None
    users: dict[str, str] = field(default_factory=dict)  # email -> subject
    # Tests can tamper with the next id_token (e.g. {"aud": "other"}), or break verification.
    overrides: dict[str, Any] = field(default_factory=dict)
    email_verified: bool = True
    sign_with_foreign_key: bool = False

    def __post_init__(self) -> None:
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = "mock-" + secrets.token_hex(4)
        self.codes: dict[str, dict[str, Any]] = {}

    # --- endpoints -------------------------------------------------------------------------
    def discovery(self) -> dict[str, Any]:
        return {
            "issuer": self.issuer,
            "authorization_endpoint": f"{self.issuer}/authorize",
            "token_endpoint": f"{self.issuer}/token",
            "jwks_uri": f"{self.issuer}/jwks",
            "end_session_endpoint": f"{self.issuer}/logout",
            "response_types_supported": ["code"],
            "code_challenge_methods_supported": ["S256"],
            "id_token_signing_alg_values_supported": ["RS256"],
        }

    def jwks(self) -> dict[str, Any]:
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        return {"keys": [{**jwk, "kid": self.kid, "use": "sig", "alg": "RS256"}]}

    def authorize(self, params: dict[str, str]) -> str:
        """Returns the redirect URL back to the client (auto-approve)."""
        if params.get("client_id") != self.client_id or params.get("response_type") != "code":
            raise ValueError("bad authorize request")
        if params.get("code_challenge_method") != "S256" or not params.get("code_challenge"):
            raise ValueError("PKCE S256 required")
        email = (params.get("login_hint") or next(iter(self.users), "")).lower()
        if email not in self.users:
            raise ValueError("unknown user")
        code = secrets.token_urlsafe(24)
        self.codes[code] = {
            "redirect_uri": params["redirect_uri"],
            "challenge": params["code_challenge"],
            "nonce": params.get("nonce"),
            "email": email,
        }
        sep = "&" if "?" in params["redirect_uri"] else "?"
        query = urlencode({"code": code, "state": params.get("state", "")})
        return f"{params['redirect_uri']}{sep}{query}"

    def token(
        self, form: dict[str, str], basic: tuple[str, str] | None
    ) -> tuple[int, dict[str, Any]]:
        if self.client_secret and basic != (self.client_id, self.client_secret):
            return 401, {"error": "invalid_client"}
        grant = self.codes.pop(form.get("code", ""), None)  # single use
        if grant is None or form.get("grant_type") != "authorization_code":
            return 400, {"error": "invalid_grant"}
        if form.get("redirect_uri") != grant["redirect_uri"]:
            return 400, {"error": "invalid_grant", "error_description": "redirect_uri"}
        if pkce_challenge(form.get("code_verifier", "")) != grant["challenge"]:
            return 400, {"error": "invalid_grant", "error_description": "pkce"}
        now = int(time.time())
        claims = {
            "iss": self.issuer,
            "aud": self.client_id,
            "sub": self.users[grant["email"]],
            "email": grant["email"],
            "email_verified": self.email_verified,
            "name": grant["email"].split("@")[0],
            "nonce": grant["nonce"],
            "iat": now,
            "exp": now + 300,
        }
        claims.update(self.overrides)
        key = rsa.generate_private_key(65537, 2048) if self.sign_with_foreign_key else self.key
        id_token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": self.kid})
        return 200, {
            "access_token": secrets.token_urlsafe(16),
            "token_type": "Bearer",
            "id_token": id_token,
            "expires_in": 300,
        }

    # --- transports ------------------------------------------------------------------------
    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        base = urlparse(self.issuer).path.rstrip("/")
        if path == f"{base}/.well-known/openid-configuration":
            return httpx.Response(200, json=self.discovery())
        if path == f"{base}/jwks":
            return httpx.Response(200, json=self.jwks())
        if path == f"{base}/token" and request.method == "POST":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            basic = None
            auth = request.headers.get("authorization", "")
            if auth.startswith("Basic "):
                user, _, pw = base64.b64decode(auth[6:]).decode().partition(":")
                basic = (user, pw)
            status, body = self.token(form, basic)
            return httpx.Response(status, json=body)
        return httpx.Response(404)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)


def create_app(idp: MockIdP) -> FastAPI:
    app = FastAPI(title="Mock OIDC (test only)")

    @app.get("/.well-known/openid-configuration")
    def disc() -> dict[str, Any]:
        return idp.discovery()

    @app.get("/jwks")
    def jwks() -> dict[str, Any]:
        return idp.jwks()

    @app.get("/authorize")
    def authorize(request: Request) -> Response:
        try:
            return RedirectResponse(idp.authorize(dict(request.query_params)), status_code=302)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.post("/token")
    async def token(request: Request) -> Response:
        req = httpx.Request(
            "POST",
            f"{idp.issuer}/token",
            headers=dict(request.headers),
            content=await request.body(),
        )
        resp = idp.handle(req)
        return Response(resp.content, status_code=resp.status_code, media_type="application/json")

    @app.get("/logout")
    def logout(post_logout_redirect_uri: str = "/") -> Response:
        return RedirectResponse(post_logout_redirect_uri, status_code=302)

    return app


def main() -> None:
    import uvicorn

    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8791)
    p.add_argument("--client-id", default="travo-web")
    p.add_argument("--client-secret")
    p.add_argument("--user", action="append", default=[], help="email (repeatable)")
    a = p.parse_args()
    issuer = f"http://localhost:{a.port}"
    users = {
        u.lower(): "mock|" + hashlib.sha256(u.lower().encode()).hexdigest()[:16] for u in a.user
    }
    uvicorn.run(
        create_app(MockIdP(issuer, a.client_id, a.client_secret, users)),
        host="127.0.0.1",
        port=a.port,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
