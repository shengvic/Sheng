"""SSO sign-in (OIDC code + PKCE), session tokens, revocation (ADR-018)."""

import secrets
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import text
from travo_api import oidc
from travo_api.db import get_engine

from scripts.mock_oidc import MockIdP, pkce_challenge

REDIRECT = "http://localhost:3000/auth/callback"


@pytest.fixture
def idp_setup(client, make_tenant, monkeypatch):
    """A firm with SSO configured against a mock IdP (confidential client)."""
    t = make_tenant(roles={"partner": "partner"})
    domain = f"firm{secrets.token_hex(3)}.test"
    # Give the partner an address on the SSO domain.
    from travo_api.db import tenant_session
    from travo_api.models import User

    with tenant_session(t.tenant_id) as s:
        u = s.get(User, uuid.UUID(t.users["partner"]))
        u.email = f"wei@{domain}"
    idp = MockIdP(
        issuer=f"https://idp.{domain}",
        client_id="travo-web",
        client_secret="s3cret-value",
        users={f"wei@{domain}": "idp-sub-wei", f"stranger@{domain}": "idp-sub-x"},
    )
    monkeypatch.setattr(oidc, "get_http", lambda: httpx.Client(transport=idp.transport()))
    oidc.clear_caches()
    r = client.put(
        "/v1/admin/idp",
        headers=t.headers(),
        json={
            "issuer": idp.issuer,
            "client_id": "travo-web",
            "client_secret": "s3cret-value",
            "email_domains": [domain.upper()],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["has_client_secret"] and r.json()["email_domains"] == [domain]
    assert "s3cret" not in r.text
    return t, idp, domain


def sso_login(client, idp, email, *, nonce=None, verifier=None, tamper=None):
    start = client.post("/v1/auth/oidc/start", json={"email": email})
    assert start.status_code == 200, start.text
    s = start.json()
    verifier = verifier or secrets.token_urlsafe(48)
    nonce = nonce or secrets.token_urlsafe(16)
    url = idp.authorize(
        {
            "client_id": s["client_id"],
            "response_type": "code",
            "redirect_uri": REDIRECT,
            "state": "st",
            "nonce": nonce,
            "code_challenge": pkce_challenge(verifier),
            "code_challenge_method": "S256",
            "login_hint": email,
        }
    )
    code = parse_qs(urlparse(url).query)["code"][0]
    body = {
        "idp_id": s["idp_id"],
        "code": code,
        "code_verifier": verifier,
        "redirect_uri": REDIRECT,
        "nonce": nonce,
    }
    if tamper:
        body.update(tamper)
    return client.post("/v1/auth/oidc/callback", json=body)


def test_sso_happy_path_binds_subject_and_session_works(client, idp_setup):
    t, idp, domain = idp_setup
    r = sso_login(client, idp, f"wei@{domain}")
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    assert r.json()["user"]["role"] == "partner"
    me = client.get("/v1/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.status_code == 200 and me.json()["id"] == t.users["partner"]
    # Second sign-in matches by bound subject.
    assert sso_login(client, idp, f"wei@{domain}").status_code == 200
    audit = client.get("/v1/admin/audit", params={"action": "auth.login"}, headers=t.headers())
    assert len(audit.json()) == 2


def test_logout_and_admin_revocation(client, idp_setup):
    t, idp, domain = idp_setup
    tok = sso_login(client, idp, f"wei@{domain}").json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    sessions = client.get("/v1/admin/sessions", headers=t.headers()).json()
    assert len(sessions) == 1 and sessions[0]["method"] == "oidc"
    assert client.post("/v1/auth/logout", headers=h).status_code == 204
    assert client.get("/v1/me", headers=h).status_code == 401
    tok2 = sso_login(client, idp, f"wei@{domain}").json()["token"]
    sid = client.get("/v1/admin/sessions", headers=t.headers()).json()[0]["id"]
    assert client.post(f"/v1/admin/sessions/{sid}/revoke", headers=t.headers()).status_code == 204
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {tok2}"}).status_code == 401


@pytest.mark.parametrize(
    "case",
    [
        "wrong_nonce",
        "wrong_verifier",
        "reused_code",
        "wrong_aud",
        "expired",
        "foreign_key",
        "unverified_email",
        "no_user",
        "wrong_redirect",
    ],
)
def test_sso_rejections(client, idp_setup, case):
    t, idp, domain = idp_setup
    email = f"wei@{domain}"
    kw = {}
    if case == "wrong_nonce":
        kw["tamper"] = {"nonce": "x" * 20}
    elif case == "wrong_verifier":
        kw["tamper"] = {"code_verifier": "v" * 50}
    elif case == "wrong_redirect":
        kw["tamper"] = {"redirect_uri": "http://evil.test/cb"}
    elif case == "wrong_aud":
        idp.overrides = {"aud": "someone-else"}
    elif case == "expired":
        idp.overrides = {"exp": 1_000_000, "iat": 999_000}
    elif case == "foreign_key":
        idp.sign_with_foreign_key = True
    elif case == "unverified_email":
        idp.email_verified = False
    elif case == "no_user":
        email = f"stranger@{domain}"
    if case == "reused_code":
        verifier, nonce = secrets.token_urlsafe(48), secrets.token_urlsafe(16)
        s = client.post("/v1/auth/oidc/start", json={"email": email}).json()
        url = idp.authorize(
            {
                "client_id": "travo-web",
                "response_type": "code",
                "redirect_uri": REDIRECT,
                "state": "s",
                "nonce": nonce,
                "code_challenge": pkce_challenge(verifier),
                "code_challenge_method": "S256",
                "login_hint": email,
            }
        )
        code = parse_qs(urlparse(url).query)["code"][0]
        body = {
            "idp_id": s["idp_id"],
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": REDIRECT,
            "nonce": nonce,
        }
        assert client.post("/v1/auth/oidc/callback", json=body).status_code == 200
        r = client.post("/v1/auth/oidc/callback", json=body)
    else:
        r = sso_login(client, idp, email, **kw)
    assert r.status_code == 401, (case, r.text)
    assert r.json()["detail"] == "sign-in failed"  # no detail leaks to the browser
    fails = client.get(
        "/v1/admin/audit", params={"action": "auth.login_failed"}, headers=t.headers()
    ).json()
    assert fails and fails[0]["result"] == "denied"


def test_subject_mismatch_refused(client, idp_setup):
    t, idp, domain = idp_setup
    assert sso_login(client, idp, f"wei@{domain}").status_code == 200
    idp.users[f"wei@{domain}"] = "a-different-person"  # email reassigned at the IdP
    assert sso_login(client, idp, f"wei@{domain}").status_code == 401


def test_unknown_domain_and_disabled_idp(client, idp_setup):
    t, idp, domain = idp_setup
    r = client.post("/v1/auth/oidc/start", json={"email": "someone@nowhere.test"})
    assert r.status_code == 404
    client.put(
        "/v1/admin/idp",
        headers=t.headers(),
        json={
            "issuer": idp.issuer,
            "client_id": "travo-web",
            "email_domains": [domain],
            "enabled": False,
        },
    )
    assert client.post("/v1/auth/oidc/start", json={"email": f"wei@{domain}"}).status_code == 404
    # The stored secret survives an update that omits it.
    assert client.get("/v1/admin/idp", headers=t.headers()).json()["has_client_secret"]


def test_domain_cannot_be_claimed_by_two_firms(client, idp_setup, make_tenant):
    _, idp, domain = idp_setup
    other = make_tenant("Other")
    r = client.put(
        "/v1/admin/idp",
        headers=other.headers(),
        json={"issuer": "https://idp.other.test", "client_id": "x", "email_domains": [domain]},
    )
    assert r.status_code == 409
    assert client.get("/v1/admin/idp", headers=other.headers()).json() is None


def test_lookup_functions_expose_only_public_coordinates(idp_setup):
    t, idp, domain = idp_setup
    with get_engine().begin() as c:  # app role, no tenant context
        assert c.execute(text("SELECT count(*) FROM tenant_idps")).scalar_one() == 0
        row = (
            c.execute(text("SELECT * FROM idp_for_email_domain(:d)"), {"d": domain})
            .mappings()
            .one()
        )
    assert set(row) == {"idp_id", "tenant_id", "issuer", "client_id"}
    assert str(row["tenant_id"]) == t.tenant_id


def test_dev_tokens_can_be_disabled(client, idp_setup, monkeypatch):
    from travo_api.config import get_settings

    t, idp, domain = idp_setup
    sso = sso_login(client, idp, f"wei@{domain}").json()["token"]
    monkeypatch.setattr(get_settings(), "allow_dev_tokens", False)
    assert client.get("/v1/me", headers=t.headers()).status_code == 401
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {sso}"}).status_code == 200


def test_session_token_for_other_tenant_rejected(client, idp_setup, make_tenant):
    import jwt
    from travo_api.config import get_settings

    t, idp, domain = idp_setup
    tok = sso_login(client, idp, f"wei@{domain}").json()["token"]
    claims = jwt.decode(tok, options={"verify_signature": False})
    other = make_tenant("Other")
    claims["tid"] = other.tenant_id
    forged = jwt.encode(claims, get_settings().jwt_secret, algorithm="HS256")
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_admin_extras(client, make_tenant):
    t = make_tenant()
    h = t.headers()
    eps = client.get("/v1/admin/endpoints", headers=h).json()
    assert {e["id"] for e in eps} >= {"travo-rules-v0", "openai-byo-frontier"}
    assert all("api_key" not in e and "base_url" not in e for e in eps)
    client.post(
        "/v1/admin/provider-credentials",
        headers=h,
        json={"provider": "anthropic", "api_key": "sk-ant-12345678"},
    )
    assert client.delete("/v1/admin/provider-credentials/anthropic", headers=h).status_code == 204
    creds = client.get("/v1/admin/provider-credentials", headers=h).json()
    assert creds == [{"provider": "anthropic", "last4": "5678", "status": "revoked"}]
    plan = client.post(
        "/v1/admin/model-policy/dry-run",
        headers=h,
        json={"task_type": "law_check", "escalation_reason": "x"},
    ).json()
    reasons = {f["endpoint_id"]: f["reason"] for f in plan["filtered"]}
    assert reasons["anthropic-byo-frontier"] == "no_byo_credential"
    assert client.delete("/v1/admin/provider-credentials/nope", headers=h).status_code == 404
    assert client.get("/v1/admin/idp", headers=t.headers("partner")).status_code == 403
    bad = client.put(
        "/v1/admin/idp",
        headers=h,
        json={"issuer": "https://x.test", "client_id": "c", "email_domains": ["not a domain"]},
    )
    assert bad.status_code == 422
