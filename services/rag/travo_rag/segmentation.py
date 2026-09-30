"""Clause segmentation: split contract text into numbered clauses (docs/05 §2).

Bilingual contracts are segmented on their primary language (`Block.text`); each block's
other-language text (`Block.alt`, from `travo_rag.bilingual.separate`) rides along into the
same clause as `heading_alt` / `text_alt`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from travo_rag.parsing import Block

# "1.", "1.2", "12.1.3)", "Article 5", "Clause 3", "Section 4", "Điều 7", "Pasal 2", "Fasal 9"
NUMBERED = re.compile(
    r"^(?P<num>(?:\d{1,3}(?:\.\d{1,3})*)[.)]?|(?P<kw>article|clause|section|điều|pasal|fasal)"
    r"\s+\d{1,3}[.:]?)\s+(?P<rest>\S.*)$",
    re.IGNORECASE,
)
_MAX_HEADING_LEN = 90


@dataclass
class Segment:
    number: str | None
    heading: str
    text: str
    index: int
    parts: list[str] = field(default_factory=list, repr=False)
    heading_alt: str = ""
    text_alt: str = ""
    parts_alt: list[str] = field(default_factory=list, repr=False)


def split_heading(rest: str) -> tuple[str, str]:
    """Split "Confidentiality. The Recipient shall..." into heading and body."""
    m = re.match(rf"^(?P<h>[^.:\n]{{2,{_MAX_HEADING_LEN}}})[.:]\s+(?P<b>.+)$", rest, re.S)
    if m and m.group("h")[:1].isupper():
        return m.group("h").strip(), m.group("b").strip()
    if len(rest) <= _MAX_HEADING_LEN and not rest.endswith((".", ";", ",")) and "\n" not in rest:
        return rest.strip(), ""
    return "", rest.strip()


def _alt_heading(alt: str) -> tuple[str, str]:
    """Other-language text of a clause's first block → (heading, body)."""
    first, _, more = alt.partition("\n")
    m = NUMBERED.match(first.strip())
    heading, body = split_heading(m.group("rest") if m else first.strip())
    return heading, "\n".join(x for x in (body, more.strip()) if x)


def segment(blocks: list[Block]) -> list[Segment]:
    # Contracts numbered "Điều N" / "Article N" use bare "1." / "1.1" for sub-clauses (khoản).
    keyword_mode = sum(1 for b in blocks if (m := NUMBERED.match(b.text)) and m.group("kw")) >= 2
    segments: list[Segment] = []
    preamble: list[str] = []
    preamble_alt: list[str] = []
    current: Segment | None = None

    for b in blocks:
        m = NUMBERED.match(b.text) if b.text else None
        top_level = m is not None and "." not in m.group("num").rstrip(".)")
        starts = m is not None and (
            (bool(m.group("kw")) if keyword_mode else top_level) or b.is_heading
        )
        if m and starts:
            heading, body = split_heading(m.group("rest"))
            current = Segment(
                number=m.group("num").rstrip(".):").strip(),
                heading=heading,
                text="",
                index=len(segments),
            )
            if body:
                current.parts.append(body)
            if b.alt:
                current.heading_alt, alt_body = _alt_heading(b.alt)
                if alt_body:
                    current.parts_alt.append(alt_body)
            segments.append(current)
        elif b.is_heading and not m:
            current = Segment(number=None, heading=b.text, text="", index=len(segments))
            if b.alt:
                current.heading_alt, alt_body = _alt_heading(b.alt)
                if alt_body:
                    current.parts_alt.append(alt_body)
            segments.append(current)
        elif current is None:
            if b.text:
                preamble.append(b.text)
            if b.alt:
                preamble_alt.append(b.alt)
        else:
            if b.text:
                current.parts.append(b.text)
            if b.alt and not b.text and not current.heading_alt and not current.parts_alt:
                # Alternating paragraphs: "Article 1. Definitions" right after "Điều 1. …".
                current.heading_alt, alt_body = _alt_heading(b.alt)
                if alt_body:
                    current.parts_alt.append(alt_body)
            elif b.alt:
                current.parts_alt.append(b.alt)

    for s in segments:
        s.text = "\n".join(s.parts).strip()
        s.text_alt = "\n".join(s.parts_alt).strip()
    if preamble or preamble_alt:
        for s in segments:
            s.index += 1
        segments.insert(
            0,
            Segment(
                number=None,
                heading="Preamble",
                text="\n".join(preamble),
                index=0,
                text_alt="\n".join(preamble_alt),
            ),
        )
    return segments
