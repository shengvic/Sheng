"""Parse official snapshots into legal units.

Both formats reduce to text lines (per page for PDFs), then one statute splitter finds sections.
The PDF path has been checked against real AGC Malaysia reprints, English and Malay (ADR-020).
The SSO HTML path is still tested only on synthetic pages `[verify]`. Every run must be checked
in the review report before `legal-verify` (ADR-019).
"""

from __future__ import annotations

import io
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
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


def pdf_pages(raw: bytes) -> tuple[str, list[list[str]]]:
    """Text lines per page (page structure is needed to find running headers and footnotes)."""
    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)  # font-encoding chatter on colophons
    reader = PdfReader(io.BytesIO(raw))
    pages: list[list[str]] = []
    for page in reader.pages:
        lines = [re.sub(r"\s+", " ", ln).strip() for ln in (page.extract_text() or "").splitlines()]
        pages.append([ln for ln in lines if ln])
    if not any(pages):
        raise ParseError("PDF has no text layer (scanned); OCR is not supported yet")
    titles: list[str] = []
    meta = reader.metadata
    if meta is not None:
        for key in ("/Title", "/titleBI", "/titleBM"):
            value = meta.get(key)
            if value:
                titles.append(str(value))
    return " | ".join(titles), pages


# ---------------------------------------------------------------- statute splitter
#
# Rules (ADR-020):
# - Page chrome (running headers/footers, page numbers, rules) is removed only at page edges.
# - Editorial footnotes ("*NOTE—…" to the end of the page) are kept aside as notes.
# - With a contents table ("Arrangement of Sections" / "Susunan Seksyen"), a numbered line starts
#   a section only in contents order, and the heading + Part/Division lines before it are
#   matched against the contents text. Without one, a conservative one-line heading rule applies.
# - No line is dropped silently: every body line ends up in a heading, section text, a Part
#   label, a note or the preamble, and an accounting check warns if characters go missing.

_SECTION = re.compile(r"^(\d{1,4}[A-Z]{0,3})\s*\.\s*(?:[—–-]\s*)?(.*)$")
_END = re.compile(
    r"^(THE )?((FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH) )?SCHEDULES?\b|^JADUAL\b|"
    r"^LIST OF (AMENDMENTS|SECTIONS AMENDED)\b|^SENARAI PINDAAN\b|^SEKSYEN YANG DIPINDA\b|"
    r"^LEGISLATIVE (HISTORY|SOURCE)\b|^APPENDIX\b|^LAMPIRAN\b|^DICETAK OLEH\b|^PRINTED BY\b",
    re.I,
)
_TOC = re.compile(
    r"^(ARRANGEMENT OF (SECTIONS|PROVISIONS)|TABLE OF CONTENTS|SUSUNAN SEKSYEN)$", re.I
)
_TOC_LABEL = re.compile(r"^(Sections?|Seksyen)$", re.I)
_LONG_TITLE = re.compile(r"^(An|Suatu)\s+(Act|Akta|Ordinance|Ordinan|Enactment|Enakmen)\b", re.I)
_NOTE = re.compile(r"^\*+\s*(NOTE|CATATAN)\b", re.I)
_RULE = re.compile(r"^[\W_]+$")
_NEW_PARA = re.compile(
    r"^(\(\w{1,4}\)|ILLUSTRATIONS?\b|Illustrations?\b|Explanation\b|Exception\b|"
    r"Provided\b|Huraian\b|Penjelasan\b|Pengecualian\b|Contoh\b|Dengan syarat\b)"
)
_LABEL = re.compile(r"^(ILLUSTRATIONS?|Illustrations?|CONTOH|Contoh|HURAIAN|Huraian)$")
_DEFINITION = re.compile(r"^[“\"‘]")  # a new definition only after a finished clause
_SENTENCE_END = re.compile(r"[.;:—–\-\]]$")
_PAGE_NO = re.compile(r"^(page\s+)?\d{1,4}(\s+of\s+\d{1,4})?$", re.I)
_VERSION = re.compile(
    r"(?:current version as at|reprint as at|as at|revised edition|"
    r"incorporating all amendments up to|sebagaimana pada)\s+(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})",
    re.I,
)
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "mac": 3, "apr": 4, "may": 5, "mei": 5, "jun": 6, "jul": 7,
    "aug": 8, "ogo": 8, "sep": 9, "oct": 10, "okt": 10, "nov": 11, "dec": 12, "dis": 12,
}  # fmt: skip
CHROME_ZONE = 3  # lines at the top/bottom of a page that may be running headers/footers
STALE_YEARS = 5


def norm(text: str) -> str:
    """Comparison key: case, spacing and punctuation removed (pypdf splits words: 'PARLIAMEN t')."""
    return re.sub(r"[\W_]+", "", text.lower())


def _shape(line: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", line.lower())).strip()


def strip_chrome(pages: list[list[str]]) -> tuple[list[list[str]], Counter[str]]:
    """Drop line shapes that recur at page edges on many pages, plus rule/separator lines."""
    seen: Counter[str] = Counter()
    for p in pages:
        seen.update({_shape(ln) for ln in p[:CHROME_ZONE] + p[-CHROME_ZONE:]})
    need = max(3, math.ceil(0.3 * len(pages)))
    chrome = {s for s, n in seen.items() if n >= need and len(s) <= 80}
    removed: Counter[str] = Counter()
    out: list[list[str]] = []
    for p in pages:
        lines = []
        for ln in p:
            if _RULE.match(ln):
                removed["<rule line>"] += 1
            else:
                lines.append(ln)
        top, bottom = 0, len(lines)
        while top < min(CHROME_ZONE, bottom) and _shape(lines[top]) in chrome:
            top += 1
        while (
            bottom > top
            and len(lines) - bottom < CHROME_ZONE
            and (_shape(lines[bottom - 1]) in chrome or _PAGE_NO.match(lines[bottom - 1]))
        ):
            bottom -= 1
        for ln in lines[:top] + lines[bottom:]:
            removed[_shape(ln)] += 1
        out.append(lines[top:bottom])
    return out, removed


def _is_heading(line: str) -> bool:
    return (
        2 <= len(line) <= 140
        and not line.endswith((".", ";", ",", ":"))
        and not _SECTION.match(line)
        and not line.startswith("(")
    )


def _is_end(line: str) -> bool:
    # Upper-case lines only: "Jadual ini terpakai …" in a sentence is not a schedule title.
    return bool(_END.match(line)) and line.upper() == line


def _key(number: str) -> tuple[int, str]:
    m = re.match(r"(\d+)(.*)", number)
    return (int(m.group(1)), m.group(2)) if m else (0, number)


@dataclass
class Section:
    number: str
    heading: str = ""
    lines: list[str] = field(default_factory=list)
    heading_lines: list[str] = field(default_factory=list)
    part: str = ""
    part_lines: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    subheadings: set[str] = field(default_factory=set)

    @property
    def text(self) -> str:
        out: list[str] = []
        new_para = False
        for ln in self.lines:
            key = norm(ln)
            side_note = key in self.subheadings or (
                len(key) >= 20 and any(h.startswith(key) for h in self.subheadings)
            )
            starts = (
                new_para
                or bool(_NEW_PARA.match(ln))
                or side_note
                or (bool(_DEFINITION.match(ln)) and bool(out) and _SENTENCE_END.search(out[-1]))
            )
            if out and not starts:
                out[-1] = f"{out[-1]} {ln}"  # continuation of the previous line
            else:
                out.append(ln)
            # Side notes and "ILLUSTRATION(S)" labels stand on their own line.
            new_para = key in self.subheadings or bool(_LABEL.match(ln))
        return "\n".join(out).strip()


@dataclass
class TocEntry:
    number: str
    lines: list[str]  # heading (number removed) and following lines up to the next entry
    head_n: int = 1  # how many of `lines` are the heading (the rest are Part/Division lines)


@dataclass
class Split:
    sections: list[Section]
    warnings: list[str]
    toc: list[TocEntry]
    chrome: Counter[str]
    preamble: list[str]
    stopped_at: str = ""


def _subheadings(entry: TocEntry) -> set[str]:
    """Side notes for subsections, e.g. "(2) Exception in favour of …" (may wrap in the contents).

    Returned as comparison keys of the whole note; the body may wrap it differently.
    """
    notes: list[list[str]] = []
    for ln in entry.lines[1 : entry.head_n]:
        if ln.startswith("("):
            notes.append([re.sub(r"^\(\w{1,3}\)\s*", "", ln)])
        elif notes:
            notes[-1].append(ln)
    return {k for k in (norm(" ".join(n)) for n in notes) if len(k) >= 8}


def _parse_toc(lines: list[str], start: int) -> tuple[list[TocEntry], list[str], int]:
    """Contents entries, lines before the first entry, and the index where the body starts."""
    entries: list[TocEntry] = []
    lead: list[str] = []
    i = start + 1
    while i < len(lines):
        ln = lines[i]
        m = _SECTION.match(ln)
        if _LONG_TITLE.match(ln) or (m and entries and m.group(1) == entries[0].number):
            break
        if _TOC_LABEL.match(ln):
            pass
        elif m:
            first = re.sub(r"^\(\w{1,3}\)\s*", "", m.group(2).strip())
            entries.append(TocEntry(m.group(1), [first] if first else []))
        elif entries:
            entries[-1].lines.append(ln)
        else:
            lead.append(ln)
        i += 1
    for e in entries:
        n = 1
        while n < len(e.lines) and (e.lines[n][:1].islower() or e.lines[n].startswith("(")):
            n += 1
        e.head_n = min(n, len(e.lines))
    if i < len(lines) and not _LONG_TITLE.match(lines[i]) and entries:
        # Numbering restarted without a long title: trailing non-heading lines are body text.
        tail = len(entries[-1].lines) - entries[-1].head_n
        if tail:
            del entries[-1].lines[entries[-1].head_n :]
            i -= tail
    return entries, lead, i


def _match_heading(
    buf: list[str], before: list[str], before_fixed: int, own: TocEntry
) -> tuple[int, int, bool] | None:
    """Find the Part/Division lines + heading of a section at the end of `buf`.

    `before` are the contents lines between the previous entry's number and this one (the
    first `before_fixed` of them are the previous heading); `own` is this entry. Returns
    (Part/Division lines, heading lines, exact?) taken from the end of `buf`. Official contents
    tables have typos ("object" vs "objects"), so a close match (≥ 0.9) is accepted and reported.
    """
    suffix: dict[str, int] = {}
    acc = ""
    for k in range(1, min(len(buf), 16) + 1):
        acc = norm(buf[-k]) + acc
        suffix.setdefault(acc, k)
    ca = min(before_fixed, len(before))
    cb = own.head_n
    options = [(a, b) for a in range(ca, len(before) + 1) for b in range(1, len(own.lines) + 1)]
    options.sort(key=lambda ab: (abs(ab[0] - ca) + abs(ab[1] - cb), -ab[1]))
    for a, b in options:
        struct, head = before[a:], own.lines[:b]
        found = suffix.get(norm(" ".join(struct + head)))
        if found is None:
            continue
        k = found
        taken = buf[-k:]
        want = len(norm(" ".join(struct)))
        cum, split = 0, 0  # a Part line split mid-line is kept with the heading
        for j in range(len(taken) + 1):
            if cum == want:
                split = j
                break
            if j < len(taken):
                cum += len(norm(taken[j]))
        return split, k - split, True
    best: tuple[float, int, int] | None = None
    for a, b in options:
        struct, head = before[a:], own.lines[:b]
        expected = norm(" ".join(struct + head))
        tail = ""
        for n in range(1, min(len(buf), 6) + 1):
            tail = norm(buf[-n]) + tail
            ratio = SequenceMatcher(None, tail, expected).ratio()
            if ratio >= 0.9 and (best is None or ratio > best[0]):
                lines, target = buf[-n:], len(norm(" ".join(struct)))
                cut = min(range(n + 1), key=lambda j: abs(len(norm(" ".join(lines[:j]))) - target))
                best = (ratio, cut, n - cut)
    if best is None:
        return None
    return best[1], best[2], False


def split_document(pages: list[list[str]], title_hints: tuple[str, ...] = ()) -> Split:
    warnings: list[str] = []
    pages, chrome = strip_chrome(pages)
    # Flatten, setting editorial footnotes aside ("*NOTE—" to the end of its page).
    stream: list[tuple[str, str, int]] = []  # (kind "t"|"n", line, page)
    for pno, p in enumerate(pages):
        in_note = False
        for ln in p:
            in_note = in_note or bool(_NOTE.match(ln))
            stream.append(("n" if in_note else "t", ln, pno))
    text_idx = [i for i, (k, _, _) in enumerate(stream) if k == "t"]
    text = [stream[i][1] for i in text_idx]

    toc: list[TocEntry] = []
    toc_lead: list[str] = []
    body_from = 0
    title_block = {norm(h) for h in title_hints if h}
    toc_at = next((j for j, ln in enumerate(text) if _TOC.match(ln)), None)
    if toc_at is not None:
        toc, toc_lead, body_text_from = _parse_toc(text, toc_at)
        title_block |= {norm(ln) for ln in text[max(0, toc_at - 5) : toc_at]}
        body_from = text_idx[body_text_from] if body_text_from < len(text_idx) else len(stream)
        if not toc:
            warnings.append("contents table found but no entries parsed")
    by_number = {e.number: n for n, e in enumerate(toc)}

    sections: list[Section] = []
    preamble: list[str] = []
    preamble_notes: list[str] = []
    cur: Section | None = None
    next_ti = 0
    part = ""
    unmatched: list[str] = []
    differs: list[str] = []
    out_of_contents: list[str] = []
    stopped_at = ""
    page_marks: list[tuple[int, Section]] = []  # sections with a "*" marker, by page
    back: list[str] = []

    def holder() -> list[str]:
        return cur.lines if cur is not None else preamble

    def start(
        number: str, rest: str, heading: tuple[int, int, bool] | None, ti: int | None
    ) -> None:
        nonlocal cur, part
        buf = holder()
        s = Section(number=number)
        if heading is not None:
            n_struct, n_head, exact = heading
            taken = buf[len(buf) - n_struct - n_head :]
            del buf[len(buf) - n_struct - n_head :]
            s.part_lines = taken[:n_struct]
            s.heading_lines = taken[n_struct:]
            if s.part_lines:
                part = " ".join(s.part_lines)
            if not exact:
                entry_head = " ".join(toc[ti].lines[: toc[ti].head_n]) if ti is not None else ""
                differs.append(f"s {number}: '{' '.join(s.heading_lines)}' vs '{entry_head}'")
        elif (
            ti is None
            and buf
            and _is_heading(buf[-1])
            and (cur is None or len(buf) == 1 or _SENTENCE_END.search(buf[-2]))
        ):
            s.heading_lines = [buf.pop()]
        s.heading = " ".join(s.heading_lines)
        if ti is not None:
            entry = toc[ti]
            if not s.heading_lines:
                s.heading = " ".join(entry.lines[: entry.head_n])
                unmatched.append(number)
            s.subheadings = _subheadings(entry)
        s.part = part
        if rest:
            s.lines.append(rest)
        sections.append(s)
        cur = s

    end = len(stream)
    for pos in range(body_from, len(stream)):
        kind, ln, pno = stream[pos]
        if kind == "n":
            target = next((s for p, s in reversed(page_marks) if p == pno), cur)
            (target.notes if target is not None else preamble_notes).append(ln)
            continue
        if sections and _is_end(ln):
            stopped_at, end = ln, pos
            assert cur is not None
            while cur.lines and norm(cur.lines[-1]) in title_block:
                back.insert(0, cur.lines.pop())
            break
        m = _SECTION.match(ln)
        accepted = False
        if m:
            num, rest = m.group(1), m.group(2).strip()
            if toc:
                ti = by_number.get(num)
                if ti is not None and ti >= next_ti:
                    before = toc[ti - 1].lines if ti > 0 else toc_lead
                    fixed = toc[ti - 1].head_n if ti > 0 else 0
                    h = _match_heading(holder(), before, fixed, toc[ti])
                    if ti == next_ti or h is not None:
                        if ti > next_ti:
                            skipped = [e.number for e in toc[next_ti:ti]]
                            warnings.append(f"sections {', '.join(skipped)} not found in the body")
                        start(num, rest, h, ti)
                        next_ti, accepted = ti + 1, True
                elif ti is None and cur is not None and _key(num) > _key(cur.number):
                    nxt = toc[next_ti].number if next_ti < len(toc) else None
                    if nxt is None or _key(num) < _key(nxt):
                        start(num, rest, None, None)
                        out_of_contents.append(num)
                        accepted = True
            else:
                start(num, rest, None, None)
                accepted = True
        if not accepted:
            holder().append(ln)
        if "*" in ln and cur is not None:
            page_marks.append((pno, cur))

    # Accounting: every body character is in a heading, text, Part label, note or preamble.
    body_chars = sum(len(norm(ln)) for _, ln, _ in stream[body_from:end])
    placed = sum(len(norm(ln)) for ln in preamble + preamble_notes + back)
    for s in sections:
        placed += len(s.number) + sum(
            len(norm(ln)) for ln in s.lines + s.heading_lines + s.part_lines + s.notes
        )
    if placed != body_chars:
        warnings.append(f"accounting check: {body_chars - placed} characters not placed")

    if toc:
        parsed = {s.number for s in sections}
        missing = [e.number for e in toc if e.number not in parsed]
        if missing:
            warnings.append(f"in contents but not parsed: {', '.join(missing[:15])}")
        if out_of_contents:
            warnings.append(f"parsed but not in contents: {', '.join(out_of_contents[:15])}")
        if differs:
            warnings.append(
                "heading differs from contents (body text used): " + "; ".join(differs[:10])
            )
        if unmatched:
            warnings.append(
                "heading not found above section (contents heading used): "
                + ", ".join(unmatched[:15])
            )
    if stopped_at:
        warnings.append(f"stopped at '{stopped_at[:60]}' (schedules/appendices not ingested)")

    # Without a contents table duplicates can only be guessed: keep the longest text.
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
    return Split(
        sections=[s for s in ordered if s.text],
        warnings=warnings,
        toc=toc,
        chrome=chrome,
        preamble=preamble,
        stopped_at=stopped_at,
    )


def split_sections(lines: list[str]) -> tuple[list[Section], list[str]]:
    s = split_document([lines])
    return s.sections, s.warnings


def version_date(lines: list[str]) -> date | None:
    # Joined, because covers wrap: "Incorporating all amendments up" / "to 1 January 2006".
    for m in _VERSION.finditer(" ".join(lines[:200])):
        month = _MONTHS.get(m.group(2)[:3].lower())
        if month is None:
            continue
        try:
            return date(int(m.group(3)), month, int(m.group(1)))
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
    notes: dict[str, list[str]] = field(default_factory=dict)  # unit_path → editorial notes
    parts: dict[str, str] = field(default_factory=dict)  # unit_path → Part/Division label
    stats: dict[str, str] = field(default_factory=dict)


def parse_snapshot(
    inst: Instrument, snap: Snapshot, issuing_body: str, today: date | None = None
) -> ParseResult:
    raw = snap.read()
    if inst.format == "sso_html":
        title, lines = html_lines(raw)
        pages = [lines]
    elif inst.format == "pdf":
        title, pages = pdf_pages(raw)
    else:
        title = ""
        pages = [[ln.strip() for ln in raw.decode("utf-8", "replace").splitlines() if ln.strip()]]
    flat = [ln for p in pages for ln in p]
    if norm(inst.expect_title) not in norm(" ".join([title, *flat[:150]])):
        raise ParseError(
            f"{inst.id}: expected title '{inst.expect_title}' not found — wrong URL or page?"
        )
    split = split_document(pages, title_hints=(inst.title, inst.expect_title))
    sections, warnings = split.sections, split.warnings
    if len(sections) < MIN_UNITS:
        raise ParseError(f"{inst.id}: only {len(sections)} sections parsed; layout not recognised")
    version = version_date(flat)
    today = today or date.today()
    if version is None:
        warnings.append("no 'as at' version date found; units have no effective_from")
    elif (today - version).days > STALE_YEARS * 365:
        warnings.append(
            f"text is as at {version.isoformat()} — check the portal for later amendments"
        )
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
    chrome = ", ".join(f"'{k}' ×{n}" for k, n in split.chrome.most_common(6))
    stats = {
        "contents entries": str(len(split.toc)) if split.toc else "no contents table",
        "sections parsed": str(len(sections)),
        "preamble lines (not ingested)": str(len(split.preamble)),
        "page chrome removed": chrome or "none",
    }
    return ParseResult(
        units=units,
        warnings=warnings,
        title_seen=title,
        version_date=version,
        notes={f"s {s.number}": s.notes for s in sections if s.notes},
        parts={f"s {s.number}": s.part for s in sections if s.part},
        stats=stats,
    )
