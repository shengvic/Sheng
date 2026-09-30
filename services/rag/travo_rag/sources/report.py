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
    origin: str = "fetched"
    manifest_note: str = ""
    filename: str | None = None
    notes: dict[str, list[str]] = field(default_factory=dict)
    parts: dict[str, str] = field(default_factory=dict)
    stats: dict[str, str] = field(default_factory=dict)


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
        "**Before running `legal-verify` for a source, a lawyer should:** open the official text,",
        "compare the first and last sections and at least three sections used by the jurisdiction",
        "pack, confirm section numbers and headings line up, and confirm nothing is truncated.",
        "Every ⚠ line needs a decision. Text is kept exactly as extracted from the PDF, including",
        "split-word artefacts such as 'di -Pertua'; schedules and appendices are not ingested yet.",
        "",
        "| Instrument | Status | Sections | Notes |",
        "|---|---|---|---|",
    ]
    for o in outcomes:
        notes = o.detail or (f"{len(o.warnings)} warning(s) — see below" if o.warnings else "")
        lines.append(f"| {o.id} — {o.title} | {o.status} | {len(o.units)} | {notes} |")
    for o in outcomes:
        if o.status != "parsed":
            continue
        if o.url:
            where = o.url
        else:
            where = f"none — supplied file `{o.filename or '?'}`; add the official URL"
        lines += [
            "",
            f"## {o.id} — {o.title}",
            "",
            f"- Official URL: {where}",
            f"- Origin: {o.origin}",
            *([f"- ⚠ Manifest note: {o.manifest_note}"] if o.manifest_note else []),
            f"- Snapshot sha256: `{o.sha256}`",
        ]
        lines += [f"- {k.capitalize()}: {v}" for k, v in o.stats.items()]
        for w in o.warnings:
            lines.append(f"- ⚠ {w}")
        picks = o.units if len(o.units) <= 6 else o.units[:3] + o.units[-3:]
        lines += ["", "| Section | Part | Heading | Text (start) |", "|---|---|---|---|"]
        for u in picks:
            cells = [u.unit_path, o.parts.get(u.unit_path, ""), u.heading, _excerpt(u.text)]
            lines.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
        if o.notes:
            lines += ["", "Editorial notes set aside (not ingested):", ""]
            for path, note_lines in o.notes.items():
                lines.append(f"- {path}: {_excerpt(' '.join(note_lines), 300)}")
    return "\n".join(lines) + "\n"
