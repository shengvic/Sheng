"""Manifest of instruments to fetch, per jurisdiction (`config/legal_sources/*.yaml`)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

Format = Literal["sso_html", "pdf", "text"]


class Instrument(BaseModel):
    id: str = Field(pattern=r"^[A-Z]{2}/[A-Za-z0-9_.-]{2,80}$")
    title: str
    instrument_type: str = "act"
    number: str | None = None
    url: str | None = Field(default=None, pattern=r"^https?://\S+$")
    format: Format
    # Substring (case-insensitive) the fetched document must contain; guards wrong URLs.
    expect_title: str
    language: str = "en"
    notes: str = ""

    @property
    def jurisdiction(self) -> str:
        return self.id.split("/", 1)[0]


class Manifest(BaseModel):
    jurisdiction: str = Field(pattern=r"^[A-Z]{2}$")
    issuing_body: str
    instruments: list[Instrument]

    @model_validator(mode="after")
    def _consistent(self) -> Manifest:
        ids = [i.id for i in self.instruments]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate instrument ids")
        bad = [i.id for i in self.instruments if i.jurisdiction != self.jurisdiction]
        if bad:
            raise ValueError(f"instrument ids must start with {self.jurisdiction}/: {bad}")
        return self


def load_manifests(directory: str | Path) -> dict[str, Manifest]:
    out: dict[str, Manifest] = {}
    for path in sorted(Path(directory).glob("*.yaml")):
        m = Manifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        out[m.jurisdiction] = m
    return out
