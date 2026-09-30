"""Parse official snapshots into legal units.

Both formats reduce to text lines, then one statute splitter finds sections. The splitter is
layout-tolerant rather than tied to exact markup, because portal HTML/PDF layouts change and
the real pages could not be inspected when this was written: every run must be checked in the
review report before `legal-verify` (ADR-019). `[verify]` against real SSO / AGC documents.
"""

from __future__ import annotations

import io
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser

from travo_rag.legal_index import SourceIn, UnitIn
from travo_rag.sources.fetch import Snapshot
from travo_rag.sources.manifest import Instrument

MIN_UNITS = 3


class ParseError(ValueError):
    pass


# ---------------------------------------------------------------- HTML → lines

_BLOCK = {
    "p",
    "div",
    "td",
    "th",
    "tr",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "br",
    "section",
    "article",
    "table",
    "dt",
    "dd",
    "blockquote",
    "pre",
}
_SKIP_TAGS = {"script", "style", "nav", "header", "footer", "noscript", "button", "form"}
# Class/id fragments of page chrome and editorial notes that are not statutory text.
_SKIP_CLASSES = (
    "nav",
    "menu",
    "breadcrumb",
    "footer",
    "header",
    "footnote",
    "amendnote",
    "amend-note",
    "leghistory",
    "toc",
    "sidebar",
    "skip",
)


class _Lines(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.buf: list[str] = []
        self.skip_depth = 0
        self.stack: list[bool] = []  # per open element: does it start a skipped region?
        self.title_parts: list[str] = []
        self.in_title = False

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        if text:
            self.lines.append(text)
        self.buf = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.in_title = True
        marker = " ".join(v or "" for k, v in attrs if k in ("class", "id", "role")).lower()
        skip = tag in _SKIP_TAGS or any(c in marker for c in _SKIP_CLASSES)
        if tag in _BLOCK:
            self._flush()
        if tag in ("br", "img", "hr", "meta", "link", "input"):
            return
        self.stack.append(skip)
        if skip:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag in _BLOCK:
            self._flush()
        if tag in ("br", "img", "hr", "meta", "link", "input") or not self.stack:
            return
        if self.stack.pop():
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        elif self.skip_depth == 0:
            self.buf.append(data)


def html_lines(raw: bytes) -> tuple[str, list[str]]:
    p = _Lines()
    p.feed(raw.decode("utf-8", errors="replace"))
    p.close()
    p._flush()
    return re.sub(r"\s+", " ", "".join(p.title_parts)).strip(), p.lines


def pdf_lines(raw: bytes) -> tuple[str, list[str]]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    lines: list[str] = []
    for page in reader.pages:
        for ln in (page.extract_text() or "").splitlines():
            ln = re.sub(r"\s+", " ", ln).strip()
            if ln:
                lines.append(ln)
    if not lines:
        raise ParseError("PDF has no text layer (scanned); OCR is not supported yet")
    meta = reader.metadata
    title = str(meta.title or "") if meta is not None else ""
    return title, lines


# ---------------------------------------------------------------- statute splitter

_SECTION = re.compile(r"^(\d{1,4}[A-Z]{0,3})\s*\.\s*(?:[—–-]\s*)?(.*)$")
_END = re.compile(
    r"^(THE )?(FIRST |SECOND |THIRD )?SCHEDULE\b|^LIST OF AMENDMENTS|"
    r"^LEGISLATIVE HISTORY|^LEGISLATIVE SOURCE",
    re.I,
)
_TOC = re.compile(r"^(ARRANGEMENT OF (SECTIONS|PROVISIONS)|TABLE OF CONTENTS)$", re.I)
_VERSION = re.compile(
    r"(?:current version as at|as at|revised edition|reprint as at)\s+"
    r"(\d{1,2}\s+[A-Z][a-z]{2,8}\s+\d{4})",
    re.I,
)
_PAGE_NO = re.compile(r"^(page\s+)?\d{1,4}(\s+of\s+\d{1,4})?$", re.I)


@dataclass
class Section:
    number: str
    heading: str = ""
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        out: list[str] = []
        for ln in self.lines:
            if out and not re.match(r"^\(\w{1,4}\)", ln):
                out[-1] = f"{out[-1]} {ln}"  # continuation of the previous line
            else:
                out.append(ln)
        return "\n".join(out).strip()


def _running_lines(lines: list[str]) -> set[str]:
    """Short lines repeated on many pages (running headers/footers)."""
    counts = Counter(ln for ln in lines if len(ln) <= 70)
    return {ln for ln, n in counts.items() if n >= 3 and not _SECTION.match(ln)}


def _is_heading(line: str) -> bool:
    return (
        4 <= len(line) <= 140
        and not line.endswith((".", ";", ",", ":"))
        and not _SECTION.match(line)
        and not line.startswith("(")
    )


def split_sections(lines: list[str]) -> tuple[list[Section], list[str]]:
    warnings: list[str] = []
    running = _running_lines(lines)
    body = [ln for ln in lines if ln not in running and not _PAGE_NO.match(ln)]
    sections: list[Section] = []
    cur: Section | None = None
    pending_heading = ""
    in_toc = False
    for ln in body:
        if _END.match(ln) and sections:
            break
        if _TOC.match(ln):
            in_toc = True
            continue
        m = _SECTION.match(ln)
        if m:
            num, rest = m.group(1), m.group(2).strip()
            # A table-of-contents entry is a short title-like line; real sections have text.
            if in_toc and rest and _is_heading(rest) and len(rest) < 90:
                continue
            in_toc = False
            cur = Section(number=num, heading=pending_heading)
            pending_heading = ""
            if rest:
                cur.lines.append(rest)
            sections.append(cur)
            continue
        if in_toc:
            continue
        if cur is not None and not _is_heading(ln):
            cur.lines.append(ln)
            continue
        if _is_heading(ln):
            # A heading (marginal note) belongs to the next section; if the current section
            # already has text, keep it as the next section's heading.
            pending_heading = ln
            continue
    # Drop duplicates (e.g. TOC remnants): keep the entry with the longest text.
    best: dict[str, Section] = {}
    for s in sections:
        prev = best.get(s.number)
        if prev is not None:
            warnings.append(f"duplicate section {s.number}: kept the longer text")
        if prev is None or len(s.text) > len(prev.text):
            best[s.number] = s
    ordered = [s for s in sections if best.get(s.number) is s]
    empty = [s.number for s in ordered if not s.text]
    if empty:
        warnings.append(f"sections with no text dropped: {', '.join(empty[:10])}")
    return [s for s in ordered if s.text], warnings


def _version_date(lines: list[str]) -> date | None:
    for ln in lines[:200]:
        m = _VERSION.search(ln)
        if m:
            for fmt in ("%d %b %Y", "%d %B %Y"):
                try:
                    return datetime.strptime(m.group(1), fmt).date()
                except ValueError:
                    continue
    return None


# ---------------------------------------------------------------- entry point


@dataclass
class ParseResult:
    units: list[UnitIn]
    warnings: list[str]
    title_seen: str
    version_date: date | None


def parse_snapshot(inst: Instrument, snap: Snapshot, issuing_body: str) -> ParseResult:
    raw = snap.read()
    if inst.format == "sso_html":
        title, lines = html_lines(raw)
    elif inst.format == "pdf":
        title, lines = pdf_lines(raw)
    else:
        title, lines = "", [ln.strip() for ln in raw.decode("utf-8", "replace").splitlines()]
        lines = [ln for ln in lines if ln]
    haystack = " ".join([title, *lines[:120]]).lower()
    if inst.expect_title.lower() not in haystack:
        raise ParseError(
            f"{inst.id}: expected title '{inst.expect_title}' not found — wrong URL or page?"
        )
    sections, warnings = split_sections(lines)
    if len(sections) < MIN_UNITS:
        raise ParseError(f"{inst.id}: only {len(sections)} sections parsed; layout not recognised")
    version = _version_date(lines)
    if version is None:
        warnings.append("no 'as at' version date found; units have no effective_from")
    source = SourceIn(
        id=inst.id,
        jurisdiction=inst.jurisdiction,
        instrument_type=inst.instrument_type,
        number=inst.number,
        title=inst.title,
        issuing_body=issuing_body,
        language=inst.language,
        official_url=snap.url,
        is_fixture=False,
        snapshot_sha256=snap.sha256,
        retrieved_at=snap.retrieved_at,
    )
    units = [
        UnitIn(
            source=source,
            unit_path=f"s {s.number}",
            heading=s.heading,
            text=s.text,
            effective_from=version,
            status="in_force",
        )
        for s in sections
    ]
    return ParseResult(units=units, warnings=warnings, title_seen=title, version_date=version)
