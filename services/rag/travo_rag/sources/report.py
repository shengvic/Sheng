"""Markdown review report for a fetch/parse run — what a lawyer checks before `legal-verify`."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from travo_rag.legal_index import UnitIn


@dataclass
class InstrumentOutcome:
    id: str
    title: str
    status: str  # parsed | needs_url | fetch_failed | parse_failed | skipped
    url: str | None = None
    detail: str = ""
    units: list[UnitIn] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sha256: str | None = None


def _excerpt(text: str, n: int = 220) -> str:
    t = " ".join(text.split())
    return t if len(t) <= n else t[: n - 1] + "…"


def render(outcomes: list[InstrumentOutcome], jurisdiction: str) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    ok = sum(1 for o in outcomes if o.status == "parsed")
    lines = [
        f"# Legal source review — {jurisdiction}",
        "",
        f"Generated {now}. {ok}/{len(outcomes)} instruments parsed.",
        "",
        "**Before running `legal-verify` for a source, a lawyer should:** open the official URL,",
        "compare the first and last sections and at least three sections used by the jurisdiction",
        "pack, confirm section numbers and headings line up, and confirm nothing is truncated.",
        "",
        "| Instrument | Status | Sections | Notes |",
        "|---|---|---|---|",
    ]
    for o in outcomes:
        notes = o.detail or ("; ".join(o.warnings) if o.warnings else "")
        lines.append(f"| {o.id} — {o.title} | {o.status} | {len(o.units)} | {notes} |")
    for o in outcomes:
        if o.status != "parsed":
            continue
        lines += [
            "",
            f"## {o.id} — {o.title}",
            "",
            f"- Official URL: {o.url}",
            f"- Snapshot sha256: `{o.sha256}`",
            f"- Sections parsed: {len(o.units)}",
        ]
        for w in o.warnings:
            lines.append(f"- ⚠ {w}")
        picks = o.units if len(o.units) <= 4 else o.units[:2] + o.units[-2:]
        lines += ["", "| Section | Heading | Text (start) |", "|---|---|---|"]
        for u in picks:
            lines.append(f"| {u.unit_path} | {u.heading} | {_excerpt(u.text).replace('|', '/')} |")
    return "\n".join(lines) + "\n"
