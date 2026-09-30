"""Numbers, amounts, percentages, durations and dates in Vietnamese and English contract text.

Used by the playbook checks (`checks.py`) and the bilingual discrepancy checks (`bilingual.py`).
Vietnamese contracts write amounts both in figures and in words ("100.000.000 đồng (Bằng chữ:
Một trăm triệu đồng)"), use "." as the thousands separator, and write dates as
"ngày 01 tháng 02 năm 2025".
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date

# ---------------------------------------------------------------- number words

_VI_DIGITS = {
    "không": 0, "một": 1, "mốt": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, "năm": 5, "lăm": 5,
    "nhăm": 5, "sáu": 6, "bảy": 7, "bẩy": 7, "tám": 8, "chín": 9,
}  # fmt: skip
_VI_SCALES = {"nghìn": 1_000, "ngàn": 1_000, "triệu": 1_000_000, "tỷ": 10**9, "tỉ": 10**9}
_VI_WORDS = set(_VI_DIGITS) | set(_VI_SCALES) | {"mười", "mươi", "trăm", "linh", "lẻ"}

_EN_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}  # fmt: skip
_EN_SCALES = {"thousand": 1_000, "million": 1_000_000, "billion": 10**9}
_EN_WORDS = set(_EN_UNITS) | set(_EN_SCALES) | {"hundred", "and"}


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def vi_words_to_int(text: str) -> int | None:
    """ "một trăm hai mươi lăm triệu" → 125_000_000. None if the text is not a number."""
    words = [w for w in re.findall(r"[^\W\d_]+", _nfc(text).lower()) if w != "đồng"]
    if not words or any(w not in _VI_WORDS for w in words):
        return None
    total = 0
    hundreds = tens = 0
    pending: int | None = None
    for w in words:
        if w in _VI_DIGITS:
            pending = _VI_DIGITS[w]
        elif w == "mười":
            tens = 1
        elif w == "mươi":
            tens, pending = pending or 1, None
        elif w == "trăm":
            hundreds, pending = pending if pending is not None else 1, None
        elif w in ("linh", "lẻ"):
            tens = 0
        else:  # scale
            group = hundreds * 100 + tens * 10 + (pending or 0)
            total += (group or 1) * _VI_SCALES[w]
            hundreds = tens = 0
            pending = None
    return total + hundreds * 100 + tens * 10 + (pending or 0)


def en_words_to_int(text: str) -> int | None:
    """ "one hundred and twenty-five million" → 125_000_000. None if not a number."""
    words = [w for w in re.split(r"[\s\-,]+", text.lower()) if w and w not in ("dong", "vnd")]
    if not words or any(w not in _EN_WORDS for w in words):
        return None
    total = group = 0
    for w in words:
        if w == "and":
            continue
        if w in _EN_UNITS:
            group += _EN_UNITS[w]
        elif w == "hundred":
            group = (group or 1) * 100
        else:
            total += (group or 1) * _EN_SCALES[w]
            group = 0
    return total + group


def words_to_int(text: str) -> int | None:
    return vi_words_to_int(text) if vi_words_to_int(text) is not None else en_words_to_int(text)


# ---------------------------------------------------------------- figures

_CURRENCY = r"(?:VNĐ|VND|đồng|USD|US\$|EUR|SGD|S\$|MYR|RM|IDR|Rp\.?|\$|€)"
_FIGURE = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
_AMOUNT = re.compile(
    rf"(?P<c1>{_CURRENCY})\s?(?P<n1>{_FIGURE})|(?P<n2>{_FIGURE})\s?(?P<c2>{_CURRENCY})",
    re.IGNORECASE,
)


def parse_figure(figure: str) -> float:
    """ "100.000.000" / "100,000,000" / "1.250,50" / "1,250.50" → a number."""
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", figure):
        return float(re.sub(r"[.,]", "", figure))
    m = re.fullmatch(r"(\d{1,3}(?:[.,]\d{3})*)([.,])(\d{1,2})", figure)
    if m:
        return float(re.sub(r"[.,]", "", m.group(1)) + "." + m.group(3))
    return float(figure.replace(",", "."))


@dataclass(frozen=True)
class Amount:
    value: float
    currency: str  # normalised: VND, USD, EUR, SGD, MYR, IDR, or "" when only "$"
    span: str


def _currency(raw: str) -> str:
    c = raw.upper().rstrip(".")
    return {
        "VNĐ": "VND", "ĐỒNG": "VND", "US$": "USD", "S$": "SGD", "RM": "MYR", "RP": "IDR",
        "€": "EUR", "$": "",
    }.get(c, c)  # fmt: skip


def parse_amounts(text: str) -> list[Amount]:
    out = []
    for m in _AMOUNT.finditer(_nfc(text)):
        figure = m.group("n1") or m.group("n2")
        cur = m.group("c1") or m.group("c2")
        out.append(Amount(parse_figure(figure), _currency(cur), m.group(0)))
    return out


def amounts(text: str) -> list[float]:
    return [a.value for a in parse_amounts(text)]


_WORDS_AFTER = re.compile(
    rf"(?P<fig>{_FIGURE})\s?(?P<cur>{_CURRENCY})?\s*\(\s*(?:bằng chữ|in words|viết bằng chữ)?"
    r"\s*:?\s*(?P<words>[^\d()]{3,200}?)\s*\)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FigureWords:
    figure: float
    words_value: int | None  # None when the words could not be read as a number
    words: str
    span: str


def figures_with_words(text: str) -> list[FigureWords]:
    """Amounts written in figures followed by the same amount in words."""
    out = []
    for m in _WORDS_AFTER.finditer(_nfc(text)):
        words = m.group("words")
        cleaned = re.sub(
            r"\b(đồng|việt nam|vietnam|dong|vnd|us dollars?|dollars?|euros?)\b", "", words,
            flags=re.I,
        )  # fmt: skip
        if not re.search(r"[^\W\d_]", cleaned):
            continue
        value = words_to_int(cleaned)
        # Only keep text that looks like number words in some language.
        tokens = set(re.findall(r"[^\W\d_]+", cleaned.lower()))
        if value is None and not tokens & (_VI_WORDS | _EN_WORDS):
            continue
        out.append(FigureWords(parse_figure(m.group("fig")), value, words.strip(), m.group(0)))
    return out


_PERCENT = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:%|phần trăm|per ?cent)", re.IGNORECASE)


def percents(text: str) -> list[float]:
    return [float(p.replace(",", ".")) for p in _PERCENT.findall(_nfc(text))]


# ---------------------------------------------------------------- durations

_VI_NUM_PHRASE = (
    "(?:(?:" + "|".join(sorted(_VI_WORDS - set(_VI_SCALES), key=len, reverse=True)) + r")\s+){1,4}"
)
_EN_NUM_PHRASE = (
    "(?:(?:" + "|".join(sorted(_EN_WORDS - {"and"}, key=len, reverse=True)) + r")[\s-]+){1,3}"
)
_DURATION = re.compile(
    rf"(?:(?P<digits>\d{{1,3}})(?:\s*\([^)]{{1,40}}\))?|(?P<words>{_VI_NUM_PHRASE}|{_EN_NUM_PHRASE})"
    r"(?:\(\s*(?P<paren>\d{1,3})\s*\)\s*)?)\s*(?P<unit>years?|months?|năm|tháng|tahun|bulan)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Duration:
    months: int
    span: str


def parse_durations(text: str) -> list[Duration]:
    text = _nfc(text)
    for d in parse_dates(text):  # "ngày 01 tháng 02 năm 2026" is a date, not durations
        text = text.replace(d.span, " " * len(d.span))
    out = []
    for m in _DURATION.finditer(text):
        if m.group("digits"):
            n: int | None = int(m.group("digits"))
        elif m.group("paren"):
            n = int(m.group("paren"))
        else:
            n = words_to_int(m.group("words"))
        if not n:
            continue
        yearly = m.group("unit").lower().startswith(("year", "năm", "tahun"))
        out.append(Duration(n * 12 if yearly else n, m.group(0).strip()))
    return out


_PERIOD = re.compile(
    rf"(?:(?P<digits>\d{{1,4}})(?:\s*\([^)]{{1,40}}\))?|(?P<words>{_VI_NUM_PHRASE}|{_EN_NUM_PHRASE})"
    r"(?:\(\s*(?P<paren>\d{1,4})\s*\)\s*)?)\s*(?P<unit>ngày làm việc|business days?|working "
    r"days?|hours?|giờ|days?|ngày|weeks?|tuần|hari kerja|hari|jam|minggu)\b",
    re.IGNORECASE,
)
_PERIOD_UNIT = {
    "ngày làm việc": "bd", "business day": "bd", "working day": "bd", "hari kerja": "bd",
    "hour": "h", "giờ": "h", "jam": "h", "day": "d", "ngày": "d", "hari": "d",
    "week": "w", "tuần": "w", "minggu": "w",
}  # fmt: skip


@dataclass(frozen=True)
class Period:
    value: int
    unit: str  # h | d | bd (working days) | w | mo (months; years are converted)
    span: str


def parse_periods(text: str) -> list[Period]:
    """Every stated period, months-scale and short ("24 giờ", "within 30 days")."""
    out = [Period(d.months, "mo", d.span) for d in parse_durations(text)]
    text = _nfc(text)
    for d in parse_dates(text):  # "ngày 01 tháng 02" is a date
        text = text.replace(d.span, " " * len(d.span))
    for m in _PERIOD.finditer(text):
        if m.group("digits"):
            n: int | None = int(m.group("digits"))
        elif m.group("paren"):
            n = int(m.group("paren"))
        else:
            n = words_to_int(m.group("words"))
        if not n:
            continue
        unit = m.group("unit").lower()
        out.append(
            Period(n, _PERIOD_UNIT[unit[:-1] if unit.endswith("s") else unit], m.group(0).strip())
        )
    return out


def durations_months(text: str) -> list[int]:
    return [d.months for d in parse_durations(text)]


# ---------------------------------------------------------------- dates

_EN_MONTHS = {
    m: i
    for i, names in enumerate(
        [("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"),
         ("may",), ("jun", "june"), ("jul", "july"), ("aug", "august"),
         ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"),
         ("dec", "december")],
        start=1,
    )
    for m in names
}  # fmt: skip
_DATE_PATTERNS = [
    (re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.I), "dmy"),
    (re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b"), "dmy"),
    (re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b"), "d_mon_y"),
    (re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b"), "mon_d_y"),
]


@dataclass(frozen=True)
class DateRef:
    value: date
    span: str


def parse_dates(text: str) -> list[DateRef]:
    """Dates in VN ("ngày 01 tháng 02 năm 2025", "01/02/2025" = 1 Feb) and EN formats."""
    found: list[tuple[int, DateRef]] = []
    taken: list[range] = []
    for pattern, kind in _DATE_PATTERNS:
        for m in pattern.finditer(_nfc(text)):
            if any(m.start() in r for r in taken):
                continue
            a, b, y = m.group(1), m.group(2), int(m.group(3))
            try:
                if kind == "dmy":
                    d = date(y, int(b), int(a))
                elif kind == "d_mon_y":
                    d = date(y, _EN_MONTHS[b.lower()], int(a))
                else:
                    d = date(y, _EN_MONTHS[a.lower()], int(b))
            except (KeyError, ValueError):
                continue
            found.append((m.start(), DateRef(d, m.group(0))))
            taken.append(range(m.start(), m.end()))
    return [d for _, d in sorted(found, key=lambda x: x[0])]
