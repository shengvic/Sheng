from travo_agents.rules_model import classify_rules, extract_rule
from travo_rag.parsing import Block, detect_languages, parse, sniff_mime
from travo_rag.segmentation import segment


def blocks(*lines):
    return [Block(text=ln) for ln in lines]


def test_segment_numbered_and_subclauses():
    segs = segment(
        blocks(
            "THIS AGREEMENT is made between A Pte. Ltd. and B Sdn. Bhd.",
            "1. Definitions",
            '1.1 "Affiliate" means ...',
            "2. Confidentiality. The Recipient shall keep all information secret.",
            "3.",  # stray number: not a heading
            "Article 4 Governing Law",
            "This Agreement is governed by the laws of Singapore.",
        )
    )
    assert [(s.number, s.heading) for s in segs] == [
        (None, "Preamble"),
        ("1", "Definitions"),
        ("2", "Confidentiality"),
        ("Article 4", "Governing Law"),
    ]
    assert "Affiliate" in segs[1].text
    assert segs[2].text.startswith("The Recipient")
    assert [s.index for s in segs] == [0, 1, 2, 3]


def test_segment_vietnamese_and_indonesian_markers():
    segs = segment(blocks("Điều 1. Định nghĩa", "nội dung", "Pasal 2 Kerahasiaan", "isi"))
    assert [s.number for s in segs] == ["Điều 1", "Pasal 2"]


def test_detect_languages():
    assert detect_languages("This Agreement shall be governed by the laws of Singapore") == ["en"]
    assert detect_languages("Các bên đồng ý rằng thông tin mật phải được bảo vệ") == ["vi"]
    assert detect_languages(
        "Perjanjian ini dibuat oleh dan antara para pihak yang tersebut "
        "dengan ketentuan dalam pasal"
    ) == ["id"]
    assert detect_languages("Perjanjian ini hendaklah ditafsirkan mengikut fasal yang") == ["ms"]


def test_sniff_and_parse_text():
    assert sniff_mime("a.txt", None, b"hello") == "text/plain"
    assert sniff_mime("a.pdf", "text/plain", b"%PDF-1.7") == "application/pdf"
    assert [b.text for b in parse(b"a\n\n b ", "text/plain")] == ["a", "b"]


def test_rules_classify_and_extract():
    c = classify_rules(
        "NON-DISCLOSURE AGREEMENT between Acme Pte. Ltd. and Beta Sdn. Bhd. "
        "governed by the laws of Malaysia"
    )
    assert c["contract_type"] == "NDA" and c["governing_law"] == "MY"
    assert c["parties"] == ["Acme Pte. Ltd.", "Beta Sdn. Bhd."]
    assert extract_rule({"i": 3, "heading": "Governing Law", "text": ""})["key"] == "governing_law"
    assert extract_rule({"i": 4, "heading": "Luật áp dụng", "text": ""})["key"] == "governing_law"
    assert extract_rule({"i": 5, "heading": "Xyz", "text": "lorem"})["key"] == "other"
