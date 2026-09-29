"""Clause segmentation v0: split contract text into numbered clauses (docs/05 §2)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from travo_rag.parsing import Block

# "1.", "1.2", "12.1.3)", "Article 5", "Clause 3", "Section 4", "Điều 7", "Pasal 2", "Fasal 9"
_NUMBERED = re.compile(
    r"^(?P<num>(?:\d{1,3}(?:\.\d{1,3})*)[.)]?|(?:article|clause|section|điều|pasal|fasal)"
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


def _split_heading(rest: str) -> tuple[str, str]:
    """Split "Confidentiality. The Recipient shall..." into heading and body."""
    m = re.match(rf"^(?P<h>[^.:\n]{{2,{_MAX_HEADING_LEN}}})[.:]\s+(?P<b>.+)$", rest)
    if m and m.group("h")[:1].isupper():
        return m.group("h").strip(), m.group("b").strip()
    if len(rest) <= _MAX_HEADING_LEN and not rest.endswith((".", ";", ",")):
        return rest.strip(), ""
    return "", rest.strip()


def segment(blocks: list[Block]) -> list[Segment]:
    segments: list[Segment] = []
    preamble: list[str] = []
    current: Segment | None = None

    for b in blocks:
        m = _NUMBERED.match(b.text)
        top_level = m is not None and "." not in m.group("num").rstrip(".)")
        if m and (top_level or b.is_heading):
            heading, body = _split_heading(m.group("rest"))
            current = Segment(
                number=m.group("num").rstrip(".):").strip(),
                heading=heading,
                text="",
                index=len(segments),
            )
            if body:
                current.parts.append(body)
            segments.append(current)
        elif b.is_heading and not m:
            current = Segment(number=None, heading=b.text, text="", index=len(segments))
            segments.append(current)
        elif current is None:
            preamble.append(b.text)
        else:
            current.parts.append(b.text)

    for s in segments:
        s.text = "\n".join(s.parts).strip()
    if preamble:
        for s in segments:
            s.index += 1
        segments.insert(
            0, Segment(number=None, heading="Preamble", text="\n".join(preamble), index=0)
        )
    return segments
