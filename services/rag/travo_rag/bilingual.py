"""Separate the Vietnamese and English text of bilingual contracts (docs/14 §4, ADR-023).

Bilingual Vietnamese contracts come in four layouts: a two-column table (VI | EN per row),
inline pairs ("Điều 1. Định nghĩa / Definitions", or a VI sentence followed by its EN
translation), alternating paragraphs, and two halves (all VI clauses, then all EN clauses).
`separate()` gives every block its primary-language text (`text`) and the other-language text
(`alt`), so clause segmentation runs on one language and each clause carries its counterpart.
`redistribute_halves()` fixes the two-halves layout after segmentation.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from travo_rag.parsing import VI_CHARS, Block

if TYPE_CHECKING:
    from travo_rag.segmentation import Segment

EN_STOP = {
    "the", "and", "of", "to", "in", "shall", "is", "be", "by", "or", "for", "with", "any",
    "this", "that", "on", "as", "party", "parties", "agreement", "article", "clause", "which",
    "under", "from", "not", "all", "such", "will", "may", "means", "its", "at", "an", "a",
}  # fmt: skip
# Tone marks shared with Latin-1 ("giá", "và") and common unaccented Vietnamese words: evidence
# for Vietnamese in short pieces that have none of the Vietnamese-only letters in VI_CHARS.
_LATIN1_TONES = re.compile(r"[àáãèéìíòóõùúý]")
VI_STOP = {
    "và", "của", "các", "cho", "được", "theo", "trong", "với", "là", "có", "không", "khi",
    "này", "thanh", "toán", "giá", "bên", "hợp", "đồng", "điều", "khoản", "tin", "thông",
}  # fmt: skip
_WORD = re.compile(r"[^\W\d_]+")
_SENTENCE = re.compile(r"(?<=[.;!?])\s+")
_SLASH = re.compile(r"\s+/\s+")


def text_lang(text: str) -> str | None:
    """'vi', 'en' or None (undecided) for a short piece of contract text."""
    words = _WORD.findall(text.lower())
    if not words:
        return None
    vi = sum(
        1 for w in words if VI_CHARS.search(w) or w in VI_STOP or _LATIN1_TONES.search(w)
    ) / len(words)
    if vi >= 0.2:
        return "vi"
    en = sum(1 for w in words if w in EN_STOP) / len(words)
    if en >= 0.08 or (vi == 0 and len(words) <= 6):  # short plain-ASCII headings ("Term")
        return "en"
    return None


def split_block(text: str, primary: str, other: str) -> tuple[str, str]:
    """Split one block into (primary-language text, other-language text)."""
    pieces = _SLASH.split(text)
    if len(pieces) < 2 or len({text_lang(p) for p in pieces} - {None}) < 2:
        pieces = _SENTENCE.split(text)
    out: dict[str, list[str]] = {primary: [], other: []}
    whole = text_lang(text)
    current = whole if whole is not None and whole in out else primary
    for piece in pieces:
        lang = text_lang(piece)
        if lang is not None and lang in out:
            current = lang
        out[current].append(piece)  # undecided pieces (numbers, names) follow the previous one
    return " ".join(out[primary]).strip(), " ".join(out[other]).strip()


@dataclass
class Separation:
    blocks: list[Block]  # `text` = primary language, `alt` = other language
    primary: str
    other: str | None
    layout: str  # single | table | inline | paragraphs


def separate(blocks: list[Block], languages: list[str]) -> Separation:
    primary = "vi" if "vi" in languages else (languages[0] if languages else "en")
    other = "en" if primary == "vi" and "en" in languages else None
    if other is None:
        return Separation(blocks, primary, None, "single")
    layouts: Counter[str] = Counter()
    out: list[Block] = []
    for b in blocks:
        langs = [text_lang(c) for c in b.cells]
        if len(b.cells) >= 2 and primary in langs and other in langs:
            p_lines = [ln for c, lang in zip(b.cells, langs, strict=True) if lang == primary
                       for ln in c.splitlines() if ln.strip()]  # fmt: skip
            o_text = "\n".join(c for c, lang in zip(b.cells, langs, strict=True) if lang == other)
            layouts["table"] += 1
            # The first line carries the counterpart cell; the rest are plain primary lines.
            out.append(replace(b, text=p_lines[0].strip(), alt=o_text))
            out.extend(Block(text=ln.strip()) for ln in p_lines[1:])
            continue
        p, o = split_block(b.text, primary, other)
        if p and o:
            layouts["inline"] += 1
        elif o:
            layouts["paragraphs"] += 1
        out.append(replace(b, text=p, alt=o, is_heading=b.is_heading and bool(p)))
    layout = layouts.most_common(1)[0][0] if layouts else "single"
    return Separation(out, primary, other, layout)


def redistribute_halves(segments: list[Segment]) -> bool:
    """Two-halves layout: the whole other-language version piles up in the last clause.

    Split that text at its clause numbers and give each part to the clause with the same
    number. Text before the first number stays where it was. Returns True if it redistributed.
    """
    from travo_rag.segmentation import NUMBERED, split_heading

    total = sum(len(s.text_alt) for s in segments)
    numbered = {re.sub(r"\D", "", s.number): s for s in segments if s.number}
    if total == 0 or len(numbered) < 2:
        return False
    last = max(segments, key=lambda s: len(s.text_alt))
    if len(last.text_alt) < 0.6 * total:
        return False
    before: list[str] = []
    parts: dict[str, list[str]] = {}
    key: str | None = None
    for line in last.text_alt.splitlines():
        m = NUMBERED.match(line.strip())
        if m and re.sub(r"\D", "", m.group("num")) in numbered:
            key = re.sub(r"\D", "", m.group("num"))
            parts[key] = [m.group("rest")]
        elif key is None:
            before.append(line)
        else:
            parts[key].append(line)
    if len(parts) < 2:
        return False
    # Text before the first other-language article (its title, parties) is preamble.
    if last.heading_alt and last.number:
        before.insert(0, last.heading_alt)
    last.heading_alt, last.text_alt = "", ""
    preamble = segments[0] if segments[0].heading == "Preamble" else last
    preamble.text_alt = "\n".join(x for x in (preamble.text_alt, *before) if x.strip()).strip()
    for num, lines in parts.items():
        seg = numbered[num]
        heading, body = split_heading(lines[0])
        seg.heading_alt = heading
        seg.text_alt = "\n".join([body, *lines[1:]] if body else lines[1:]).strip()
    return True
