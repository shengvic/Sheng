"""Load normalised legal units (JSONL) into the shared legal index (docs/04 §3).

One JSON object per line:
  {"source": {"id", "jurisdiction", "instrument_type", "number", "title", "issuing_body",
              "language", "official_url", "is_fixture"},
   "unit_path": "s 75", "heading": "...", "text": "...",
   "effective_from": "2001-01-01", "effective_to": null, "status": "in_force"}

Fetchers for SSO / AGC portals produce this format (deferred: sites unreachable from dev).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import Connection, text


class SourceIn(BaseModel):
    id: str = Field(max_length=160)
    jurisdiction: str = Field(max_length=8)
    instrument_type: str
    number: str | None = None
    title: str
    issuing_body: str | None = None
    language: str = "en"
    official_url: str | None = None
    is_fixture: bool = False
    # Provenance of the official snapshot this unit was parsed from (ADR-019).
    snapshot_sha256: str | None = None
    retrieved_at: datetime | None = None


class UnitIn(BaseModel):
    source: SourceIn
    unit_path: str = Field(max_length=160)
    heading: str = ""
    text: str = Field(min_length=1)
    effective_from: date | None = None
    effective_to: date | None = None
    status: Literal["in_force", "amended", "repealed"] = "in_force"

    @property
    def unit_id(self) -> str:
        return f"{self.source.id}#{self.unit_path}"


def read_jsonl(path: str | Path) -> list[UnitIn]:
    units = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                units.append(UnitIn.model_validate_json(line))
            except ValueError as exc:
                raise ValueError(f"{path}:{n}: {exc}") from None
    return units


def upsert_units(conn: Connection, units: Iterable[UnitIn]) -> int:
    """Idempotent load. Must run on the owner connection (the app role is read-only)."""
    count = 0
    for u in units:
        conn.execute(
            text(
                "INSERT INTO legal_sources (id, jurisdiction, instrument_type, number, title,"
                " issuing_body, language, official_url, is_fixture, snapshot_sha256, retrieved_at)"
                " VALUES (:id, :jurisdiction, :instrument_type, :number, :title, :issuing_body,"
                " :language, :official_url, :is_fixture, :snapshot_sha256, :retrieved_at)"
                " ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title,"
                " official_url = EXCLUDED.official_url, is_fixture = EXCLUDED.is_fixture,"
                # A different official snapshot needs a fresh lawyer check.
                " review_status = CASE WHEN legal_sources.snapshot_sha256 IS DISTINCT FROM"
                " EXCLUDED.snapshot_sha256 THEN 'unverified'"
                " ELSE legal_sources.review_status END,"
                " verified_by = CASE WHEN legal_sources.snapshot_sha256 IS DISTINCT FROM"
                "   EXCLUDED.snapshot_sha256 THEN NULL ELSE legal_sources.verified_by END,"
                " verified_at = CASE WHEN legal_sources.snapshot_sha256 IS DISTINCT FROM"
                "   EXCLUDED.snapshot_sha256 THEN NULL ELSE legal_sources.verified_at END,"
                " snapshot_sha256 = EXCLUDED.snapshot_sha256,"
                " retrieved_at = EXCLUDED.retrieved_at"
            ),
            u.source.model_dump(),
        )
        conn.execute(
            text(
                "INSERT INTO legal_units (id, source_id, unit_path, heading, text,"
                " effective_from, effective_to, status, version_hash)"
                " VALUES (:id, :source_id, :unit_path, :heading, :text, :effective_from,"
                " :effective_to, :status, :version_hash)"
                " ON CONFLICT (id) DO UPDATE SET heading = EXCLUDED.heading,"
                " text = EXCLUDED.text, effective_from = EXCLUDED.effective_from,"
                " effective_to = EXCLUDED.effective_to, status = EXCLUDED.status,"
                " version_hash = EXCLUDED.version_hash"
            ),
            {
                "id": u.unit_id,
                "source_id": u.source.id,
                "unit_path": u.unit_path,
                "heading": u.heading,
                "text": u.text,
                "effective_from": u.effective_from,
                "effective_to": u.effective_to,
                "status": u.status,
                "version_hash": hashlib.sha256(u.text.encode()).hexdigest(),
            },
        )
        count += 1
    return count


def dump_jsonl(units: Iterable[UnitIn]) -> str:
    return "\n".join(json.dumps(u.model_dump(mode="json"), ensure_ascii=False) for u in units)


def verify_source(conn: Connection, source_id: str, by: str, note: str | None) -> bool:
    """Record that a lawyer checked this source against the official text. Owner connection."""
    row = conn.execute(
        text(
            "UPDATE legal_sources SET review_status = 'verified', verified_by = :by,"
            " verified_at = now(), verification_note = :note WHERE id = :id RETURNING id"
        ),
        {"id": source_id, "by": by, "note": note},
    ).first()
    return row is not None
