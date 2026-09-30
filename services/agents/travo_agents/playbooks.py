"""Playbooks: the firm's structured positions per clause (docs/05 §3)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

Severity = Literal["high", "medium", "low"]


class ClauseRule(BaseModel):
    key: str  # rule key, unique within the playbook
    clause_key: str  # taxonomy key the rule applies to
    required: bool = False
    standard: str = ""
    must_include_any: list[str] = Field(default_factory=list)
    must_not_include_any: list[str] = Field(default_factory=list)
    min_duration_months: int | None = None
    fallback_min_duration_months: int | None = None
    max_duration_months: int | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    # e.g. a contractual penalty capped at a share of the breached obligation's value.
    max_percent: float | None = None
    severity: Severity = "medium"
    rationale: str = ""
    redline_template: str | None = None
    # Vietnamese wording for VI / bilingual output (ADR-023).
    standard_vi: str = ""
    redline_template_vi: str | None = None


class AppliesTo(BaseModel):
    contract_types: list[str] = Field(default_factory=list)
    governing_laws: list[str] = Field(default_factory=list)


class Playbook(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]{2,80}$")
    version: int = 1
    name: str
    applies_to: AppliesTo = Field(default_factory=AppliesTo)
    rules: list[ClauseRule]

    def matches(self, contract_type: str | None, governing_law: str | None) -> bool:
        a = self.applies_to
        return (not a.contract_types or contract_type in a.contract_types) and (
            not a.governing_laws or governing_law in a.governing_laws
        )

    @classmethod
    def from_yaml(cls, text: str) -> Playbook:
        return cls.model_validate(yaml.safe_load(text))


def load_starter_playbooks(directory: str | Path) -> dict[str, Playbook]:
    books = {}
    for path in sorted(Path(directory).glob("*.yaml")):
        pb = Playbook.from_yaml(path.read_text(encoding="utf-8"))
        books[pb.key] = pb
    return books


def select_playbook(
    contract_type: str | None,
    governing_law: str | None,
    tenant_books: list[Playbook],
    starter_books: list[Playbook],
) -> tuple[Playbook, str] | None:
    """Precedence (docs/05 §3): firm playbook → Travo starter pack."""
    for source, books in (("tenant", tenant_books), ("starter", starter_books)):
        for pb in books:
            if pb.matches(contract_type, governing_law):
                return pb, source
    return None
