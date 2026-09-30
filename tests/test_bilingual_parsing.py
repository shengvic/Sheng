"""Reading Vietnamese and bilingual contracts (R1, ADR-023). Synthetic FIXTURE contracts only."""

from __future__ import annotations

import pytest
from travo_rag.bilingual import separate, split_block, text_lang
from travo_rag.parsing import DOCX_MIME, detect_languages, parse
from travo_rag.segmentation import segment

from evals import vn_fixtures as vn


def _segments(data: bytes):
    blocks = parse(data, DOCX_MIME)
    languages = detect_languages("\n".join(b.text for b in blocks))
    sep = separate(blocks, languages)
    segs = segment(sep.blocks)
    from travo_rag.bilingual import redistribute_halves

    if sep.other and redistribute_halves(segs):
        sep.layout = "halves"
    return sep, segs


def test_text_lang_and_block_split():
    assert text_lang("Bên Nhận phải giữ bí mật thông tin.") == "vi"
    assert text_lang("The Recipient shall keep it confidential.") == "en"
    assert text_lang("Definitions") == "en"
    assert split_block("Điều 1. Định nghĩa / Definitions", "vi", "en") == (
        "Điều 1. Định nghĩa",
        "Definitions",
    )
    vi, en = split_block(
        "Bên nhận phải giữ bí mật. The Recipient shall keep it confidential.", "vi", "en"
    )
    assert vi == "Bên nhận phải giữ bí mật." and en.startswith("The Recipient")


@pytest.mark.parametrize(
    ("builder", "layout"),
    [
        (vn.table_docx, "table"),
        (vn.inline_docx, "inline"),
        (vn.paragraphs_docx, "paragraphs"),
        (vn.halves_docx, "halves"),
    ],
)
def test_bilingual_layouts_pair_every_clause(builder, layout):
    sep, segs = _segments(builder())
    assert (sep.primary, sep.other, sep.layout) == ("vi", "en", layout)
    body = [s for s in segs if s.number]
    assert [s.number for s in body] == [f"Điều {n}" for n in range(1, len(vn.NDA_CLAUSES) + 1)]
    for s, (vh, vb, eh, eb, _) in zip(body, vn.NDA_CLAUSES, strict=True):
        assert s.heading == vh
        assert vb in s.text and eb not in s.text  # the primary text is Vietnamese only
        assert eb in s.text_alt, (layout, s.number, s.text_alt)
        assert s.heading_alt == eh


def test_table_keeps_document_order():
    data = vn.table_docx(trailer="Hai bên đã ký tên dưới đây.")
    blocks = parse(data, DOCX_MIME)
    texts = [b.text for b in blocks]
    assert texts[0].startswith("THỎA THUẬN") and texts[-1] == "Hai bên đã ký tên dưới đây."
    assert blocks[3].cells and blocks[3].cells[0].startswith("Điều 1.")


def test_vietnamese_only_keeps_khoan_inside_articles():
    sep, segs = _segments(vn.vietnamese_docx())
    assert sep.other is None and sep.layout == "single"
    body = [s for s in segs if s.number]
    assert len(body) == len(vn.NDA_CLAUSES)
    assert "2. Các bên cam kết" in body[0].text  # a khoản, not a new clause


def test_bilingual_document_through_the_api(client, make_tenant):
    from tests.conftest import DOCX_MIME as MIME
    from tests.conftest import create_matter

    t = make_tenant()
    matter = create_matter(client, t, jurisdictions=["VN"])
    r = client.post(
        f"/v1/matters/{matter['id']}/documents",
        files={"file": ("nda_vi_en.docx", vn.table_docx(), MIME)},
        headers=t.headers(),
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["governing_law"] == "VN" and doc["contract_type"] == "NDA"
    assert (doc["primary_language"], doc["bilingual_layout"]) == ("vi", "table")
    clauses = client.get(f"/v1/documents/{doc['id']}/clauses", headers=t.headers()).json()
    keys = {c["taxonomy_key"] for c in clauses}
    assert {"confidentiality_obligations", "penalty", "governing_law", "language"} <= keys
    penalty = next(c for c in clauses if c["taxonomy_key"] == "penalty")
    assert penalty["lang"] == "vi" and penalty["lang_alt"] == "en"
    assert "VND 100,000,000" in penalty["text_alt"] and "100.000.000 đồng" in penalty["text"]


def test_governing_law_prefers_the_governing_law_clause():
    from travo_agents.rules_model import classify_rules

    text = (
        "HỢP ĐỒNG MUA BÁN HÀNG HÓA. Hàng hóa đạt tiêu chuẩn theo laws of Singapore đã công bố.\n"
        "Điều 9. Luật áp dụng: Hợp đồng này được điều chỉnh bởi pháp luật Việt Nam."
    )
    out = classify_rules(text)
    assert out["governing_law"] == "VN" and out["contract_type"] == "SALE"
