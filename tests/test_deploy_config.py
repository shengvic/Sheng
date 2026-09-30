"""Production guard and https-only identity providers (ADR-022 pilot deployment)."""

from __future__ import annotations

import base64

import pytest
from travo_api import oidc
from travo_api.config import Settings, check_production, production_problems

GOOD = {
    "env": "production",
    "allow_dev_tokens": False,
    "inline_reviews": False,
    "require_verified_sources": True,
    "master_key": base64.b64encode(b"k" * 32).decode(),
    "jwt_secret": "s" * 40,
    "database_url": "postgresql+psycopg://travo_api:9f8e7d6c5b4a@postgres:5432/travo",
    "admin_database_url": "postgresql+psycopg://postgres:1a2b3c4d5e6f@postgres:5432/travo",
}


def test_safe_production_settings_pass():
    s = Settings(**GOOD)
    assert production_problems(s) == []
    check_production(s)


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"allow_dev_tokens": True}, "ALLOW_DEV_TOKENS"),
        ({"inline_reviews": True}, "INLINE_REVIEWS"),
        ({"require_verified_sources": False}, "REQUIRE_VERIFIED_SOURCES"),
        ({"master_key": ""}, "MASTER_KEY"),
        ({"master_key": "not base64!"}, "MASTER_KEY"),
        ({"jwt_secret": "short"}, "JWT_SECRET"),
        (
            {"database_url": "postgresql+psycopg://travo_api:travo_api@postgres:5432/travo"},
            "default development password",
        ),
    ],
)
def test_unsafe_production_settings_refuse_to_start(override, fragment):
    s = Settings(**{**GOOD, **override})
    with pytest.raises(RuntimeError, match=fragment):
        check_production(s)
    check_production(Settings(**{**GOOD, **override, "env": "dev"}))  # dev is not blocked


def test_production_requires_https_identity_providers(monkeypatch):
    monkeypatch.setattr(oidc, "get_settings", lambda: Settings(**GOOD))
    oidc.clear_caches()
    with pytest.raises(oidc.OidcError, match="https"):
        oidc.discovery("http://idp.example.test")
    monkeypatch.setattr(oidc, "get_settings", lambda: Settings(**GOOD, oidc_allow_http=True))
    assert oidc._allowed_schemes() == ("https://", "http://")
