from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRAVO_", env_file=".env", extra="ignore")

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
    region_cell: str = "SG"
    max_upload_bytes: int = 25 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
