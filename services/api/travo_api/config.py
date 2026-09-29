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
    oidc_jwks_url: str | None = None
    storage_dir: Path = ROOT / ".data" / "objects"
    endpoints_file: Path = ROOT / "config" / "endpoints.yaml"
    default_policy_file: Path = ROOT / "config" / "default_policy.yaml"
    region_cell: str = "SG"
    max_upload_bytes: int = 25 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
