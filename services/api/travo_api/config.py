from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRAVO_", env_file=".env", extra="ignore")

    # "production" turns the checks in `production_problems()` into a hard startup failure.
    env: Literal["dev", "production"] = "dev"
    # App role connection: member of `travo_app`, NOT a superuser/owner, so RLS applies.
    database_url: str = "postgresql+psycopg://travo_api:travo_api@localhost:5432/travo"
    # Owner connection for migrations and tenant bootstrap only.
    admin_database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/travo"
    # base64 32-byte key; stands in for a cloud KMS key in P0.
    master_key: str = ""
    jwt_secret: str = ""
    jwt_audience: str = "travo-api"
    jwt_issuer: str = "travo-dev"
    # Session length for SSO sign-ins (ADR-018).
    session_ttl_seconds: int = 8 * 3600
    # Test-only: accept http identity providers when env=production (local deploy smoke tests
    # with the mock IdP). Never set on a real deployment.
    oidc_allow_http: bool = False
    # Tokens without a server-side session (`mint-token`, `dev-token`). MUST be false in any
    # deployment that holds client data.
    allow_dev_tokens: bool = True
    storage_dir: Path = ROOT / ".data" / "objects"
    endpoints_file: Path = ROOT / "config" / "endpoints.yaml"
    default_policy_file: Path = ROOT / "config" / "default_policy.yaml"
    playbooks_dir: Path = ROOT / "config" / "playbooks"
    jurisdiction_packs_dir: Path = ROOT / "config" / "jurisdiction_packs"
    review_config_file: Path = ROOT / "config" / "review.yaml"
    # Run reviews in the request process right after enqueueing (dev/tests). Production uses
    # `travo worker`.
    inline_reviews: bool = False
    # Law checks use only lawyer-verified legal sources (ADR-019). Required for pilots.
    require_verified_sources: bool = False
    # Raw official snapshots fetched by `legal-fetch` (kept out of git; licensing).
    legal_snapshot_dir: Path = ROOT / ".data" / "legal_snapshots"
    legal_manifest_dir: Path = ROOT / "config" / "legal_sources"
    # Sign-in attempts (/v1/auth/*) per client IP per minute; 0 disables (ratelimit.py).
    auth_rate_limit_per_minute: int = 20
    region_cell: str = "SG"
    max_upload_bytes: int = 25 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


def production_problems(s: Settings) -> list[str]:
    """Settings that must never reach a deployment holding client data (ADR-018/019/022)."""
    problems: list[str] = []
    if s.allow_dev_tokens:
        problems.append("TRAVO_ALLOW_DEV_TOKENS must be false")
    if s.inline_reviews:
        problems.append("TRAVO_INLINE_REVIEWS must be false (run the worker)")
    if not s.require_verified_sources:
        problems.append("TRAVO_REQUIRE_VERIFIED_SOURCES must be true")
    try:
        key_ok = len(base64.b64decode(s.master_key, validate=True)) == 32
    except ValueError:
        key_ok = False
    if not key_ok:
        problems.append("TRAVO_MASTER_KEY must be a base64-encoded 32-byte key")
    if len(s.jwt_secret) < 32:
        problems.append("TRAVO_JWT_SECRET must be at least 32 characters")
    for name, url in (
        ("TRAVO_DATABASE_URL", s.database_url),
        ("TRAVO_ADMIN_DATABASE_URL", s.admin_database_url),
    ):
        if ":travo_api@" in url or ":postgres@" in url:
            problems.append(f"{name} uses a default development password")
    return problems


def check_production(s: Settings) -> None:
    if s.env == "production" and (problems := production_problems(s)):
        raise RuntimeError("unsafe production settings: " + "; ".join(problems))
