"""Parse Vietnamese legislation into legal units (docs/14 §3.3, ADR-023).

Vietnamese normative documents are structured Phần / Chương / Mục / Tiểu mục / Điều, with
khoản ("1.") and điểm ("a)") inside an article. The unit is the article: `unit_path = "Điều N"`.
The same guarantees as the SG/MY splitter (ADR-020) apply:
- Articles start only in increasing order, so "Điều 5" quoted inside a sentence never splits.
- No line is dropped silently: every body line lands in an article (heading or text), a
  Phần/Chương/Mục label, a note, the preamble or the closing block, and an accounting check
  compares characters.
- Text is Unicode-normalised (NFC). Files in legacy Vietnamese font encodings (TCVN3 / VNI)
  are refused rather than ingested as garbled text.
"""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

from travo_rag.legal_index import SourceIn, UnitIn
from travo_rag.sources.fetch import Snapshot
from travo_rag.sources.manifest import Instrument
from travo_rag.sources.parsers import MIN_UNITS, ParseError, ParseResult, html_lines, norm

_ARTICLE = re.compile(r"^Điều\s+(\d{1,4}[a-z]?)\s*[.:]\s*(.*)$")
_STRUCTURE = re.compile(r"^(PHẦN|Phần|CHƯƠNG|Chương|MỤC|Mục|TIỂU MỤC|Tiểu mục)\s+[\wIVXLC]+\b")
_END = re.compile(
    r"^(Nơi nhận\s*:|TM\.\s|KT\.\s|Q\.\s|CHỦ TỊCH\b|THỦ TƯỚNG\b|BỘ TRƯỞNG\b|PHỤ LỤC\b|"
    r"(Bộ luật|Luật|Pháp lệnh|Nghị quyết) này (đã )?được Quốc hội)"
)
_NOTE = re.compile(r"^\[\d{1,3}\]\s")  # footnotes of consolidated texts (văn bản hợp nhất)
_NUMBER = re.compile(
    r"\b(?:(Bộ luật|Luật|Pháp lệnh|Nghị định|Nghị quyết|Thông tư)\s+)?số\s*:?\s*"
    r"(\d{1,4}/\d{4}/[A-ZĐ0-9-]+)",
    re.I,
)
_EFFECTIVE = re.compile(
    r"có hiệu lực(?: thi hành)?(?: kể)? từ ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
    re.I,
)
_NEW_LINE = re.compile(r"^(\d{1,2}\.|[a-zđ]\)|\d{1,2}\.\d{1,2}\.|[-–•])\s")
# Unicode Vietnamese is full of Latin Extended Additional letters (ạ ả ấ … ỹ) and ă đ ơ ư;
# TCVN3 (.VnTime) and VNI text read as Unicode never contains them, but is full of Latin-1
# symbols and accented capitals instead (§iÒu, Ph¹m, ®).
_VI_UNICODE = re.compile(r"[\u1ea0-\u1ef9ăĂđĐơƠưƯ]")
_LATIN1 = re.compile(r"[\u00a1-\u00ff]")


@dataclass
class Article:
    number: str
    heading: str
    start_line: str = ""  # the "Điều N. …" line itself
    lines: list[str] = field(default_factory=list)
    part: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        out: list[str] = []
        for ln in self.lines:
            if out and not _NEW_LINE.match(ln):
                out[-1] = f"{out[-1]} {ln}"  # a wrapped line continues the previous one
            else:
                out.append(ln)
        return "\n".join(out).strip()


def _nfc(line: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", line)).strip()


def check_encoding(lines: list[str]) -> None:
    text = " ".join(lines[:400])
    letters = sum(ch.isalpha() for ch in text) or 1
    vi = len(_VI_UNICODE.findall(text)) / letters
    latin1 = len(_LATIN1.findall(text)) / letters
    if vi < 0.005 and latin1 > 0.03:
        raise ParseError(
            "text looks like a legacy Vietnamese font encoding (TCVN3/VNI); convert the file to "
            "Unicode before importing"
        )


def docx_lines(raw: bytes) -> list[str]:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(io.BytesIO(raw))
    out: list[str] = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            out.append(Paragraph(child, doc).text)
        elif tag == "tbl":  # header blocks (issuing body | national motto) are tables
            for row in Table(child, doc).rows:
                out.extend(c.text for c in row.cells)
    return out


def vn_lines(inst: Instrument, raw: bytes) -> tuple[str, list[str]]:
    if inst.format == "vbpl_html":
        title, lines = html_lines(raw)
    elif inst.format == "docx":
        title, lines = "", docx_lines(raw)
    elif inst.format == "pdf":
        from travo_rag.sources.parsers import pdf_pages

        title, pages = pdf_pages(raw)
        lines = [ln for p in pages for ln in p]
    else:
        title, lines = "", raw.decode("utf-8", "replace").splitlines()
    out = [ln for ln in (_nfc(x) for x in lines) if ln]
    check_encoding(out)
    return _nfc(title), out


@dataclass
class VnSplit:
    articles: list[Article]
    preamble: list[str]
    closing: list[str]
    warnings: list[str]
    number: str | None
    effective_from: date | None


def split_vn(lines: list[str]) -> VnSplit:
    warnings: list[str] = []
    articles: list[Article] = []
    preamble: list[str] = []
    closing: list[str] = []
    part = ""
    part_lines: list[str] = []
    structure: list[str] = []  # Phần/Chương/Mục lines and their titles
    cur: Article | None = None
    expected = 1
    stopped = False
    numbers_ahead = [
        (i, int(re.sub(r"\D", "", m.group(1))))
        for i, ln in enumerate(lines)
        if (m := _ARTICLE.match(ln))
    ]

    def appears_later(pos: int, n: int) -> bool:
        return any(i > pos and k == n for i, k in numbers_ahead)

    for pos, ln in enumerate(lines):
        if stopped:
            closing.append(ln)
            continue
        if articles and _END.match(ln):
            stopped = True
            closing.append(ln)
            continue
        m = _ARTICLE.match(ln)
        if m:
            num = m.group(1)
            n = int(re.sub(r"\D", "", num))
            # Articles are consecutive; a jump is accepted only if the expected article never
            # comes (e.g. it was repealed and dropped from a consolidated text).
            if n == expected or (n > expected and not appears_later(pos, expected)):
                if n > expected:
                    warnings.append(f"articles {expected}–{n - 1} not found before Điều {num}")
                cur = Article(number=num, heading=m.group(2).strip(), start_line=ln, part=part)
                articles.append(cur)
                expected = n + 1
                part_lines = []
                continue
        if _STRUCTURE.match(ln):
            # Phần/Chương/Mục and its title line (next line if upper-case) label what follows.
            part_lines = [ln]
            part = ln
            structure.append(ln)
            continue
        if part_lines and ln.isupper() and len(part_lines) == 1:
            part_lines.append(ln)
            part = " ".join(part_lines)
            structure.append(ln)
            continue
        part_lines = []
        if cur is None:
            preamble.append(ln)
        elif _NOTE.match(ln):
            cur.notes.append(ln)
        else:
            cur.lines.append(ln)

    # Accounting: every input line is in exactly one bucket; a mismatch means a code change
    # started dropping text (ADR-020).
    buckets = preamble + closing + structure
    for a in articles:
        buckets += [a.start_line, *a.lines, *a.notes]
    missing = sum(len(norm(ln)) for ln in lines) - sum(len(norm(ln)) for ln in buckets)
    if missing:
        warnings.append(f"accounting check: {missing} characters not placed")

    head = " ".join(preamble[:40])
    m_num = _NUMBER.search(head)
    effective = None
    for a in reversed(articles):  # "Hiệu lực thi hành" is near the end
        m_eff = _EFFECTIVE.search(a.text)
        if m_eff:
            try:
                effective = date(int(m_eff.group(3)), int(m_eff.group(2)), int(m_eff.group(1)))
            except ValueError:
                effective = None
            break
    empty = [a.number for a in articles if not a.text and not a.heading]
    if empty:
        warnings.append(f"articles with no text: {', '.join(empty[:10])}")
    return VnSplit(
        articles=[a for a in articles if a.text or a.heading],
        preamble=preamble,
        closing=closing,
        warnings=warnings,
        number=m_num.group(2) if m_num else None,
        effective_from=effective,
    )


def parse_vn_snapshot(inst: Instrument, snap: Snapshot, issuing_body: str) -> ParseResult:
    title, lines = vn_lines(inst, snap.read())
    if norm(inst.expect_title) not in norm(" ".join([title, *lines[:80]])):
        raise ParseError(
            f"{inst.id}: expected title '{inst.expect_title}' not found — wrong URL or page?"
        )
    split = split_vn(lines)
    if len(split.articles) < MIN_UNITS:
        raise ParseError(f"{inst.id}: only {len(split.articles)} articles parsed")
    warnings = list(split.warnings)
    if inst.number and split.number and inst.number.lower() != split.number.lower():
        warnings.append(f"document number {split.number} differs from manifest {inst.number}")
    if split.effective_from is None:
        warnings.append("no 'có hiệu lực … từ ngày' date found; units have no effective_from")
    source = SourceIn(
        id=inst.id,
        jurisdiction=inst.jurisdiction,
        instrument_type=inst.instrument_type,
        number=inst.number or split.number,
        title=inst.title,
        issuing_body=issuing_body,
        language="vi",
        official_url=snap.url,
        is_fixture=False,
        snapshot_sha256=snap.sha256,
        retrieved_at=snap.retrieved_at,
    )
    units = [
        UnitIn(
            source=source,
            unit_path=f"Điều {a.number}",
            heading=a.heading,
            text=a.text or a.heading,
            effective_from=split.effective_from,
            status="in_force",
        )
        for a in split.articles
    ]
    return ParseResult(
        units=units,
        warnings=warnings,
        title_seen=title,
        version_date=split.effective_from,
        notes={f"Điều {a.number}": a.notes for a in split.articles if a.notes},
        parts={f"Điều {a.number}": a.part for a in split.articles if a.part},
        stats={
            "articles parsed": str(len(split.articles)),
            "document number": split.number or "not found",
            "preamble lines (not ingested)": str(len(split.preamble)),
            "closing lines (not ingested)": str(len(split.closing)),
        },
    )
