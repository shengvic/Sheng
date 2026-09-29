"""Generate synthetic gold NDAs (DOCX + labels). Real annotated NDAs replace these in P1.

uv run python -m evals.make_gold
"""

from __future__ import annotations

import json
from pathlib import Path

from docx import Document

OUT = Path(__file__).parent / "gold" / "nda"

# Each doc: title, preamble lines, [(heading line, body, gold taxonomy key)], meta.
DOCS: dict[str, dict] = {
    "sg_mutual_nda": {
        "meta": {"contract_type": "NDA", "governing_law": "SG", "languages": ["en"]},
        "playbook": "nda_sg",
        "expected_findings": {
            "confidentiality_core": "standard",
            "term_length": "fallback",
            "exclusions_present": "standard",
            "permitted_disclosure_present": "standard",
            "return_destroy": "standard",
            "governing_law_sg": "standard",
            "forum": "standard",
            "personal_data": "standard",
        },
        "title": "MUTUAL NON-DISCLOSURE AGREEMENT",
        "preamble": [
            'This Agreement is made between Lion City Robotics Pte. Ltd. ("Company A") and '
            'Merlion Analytics Pte. Ltd. ("Company B").',
        ],
        "clauses": [
            (
                "1. Definitions",
                '"Confidential Information" means all information disclosed by a party.',
                "definitions",
            ),
            ("2. Purpose", "The parties wish to evaluate a potential joint venture.", "purpose"),
            (
                "3. Confidentiality Obligations",
                "The Recipient shall keep the Confidential Information strictly confidential and use it only for the Purpose.",
                "confidentiality_obligations",
            ),
            (
                "4. Exclusions",
                "Obligations do not apply to information that is publicly available.",
                "exclusions",
            ),
            (
                "5. Permitted Disclosure",
                "A party may disclose information required by law or court order.",
                "permitted_disclosure",
            ),
            (
                "6. Return or Destruction",
                "On request, the Recipient shall return or destroy all Confidential Information.",
                "return_or_destruction",
            ),
            (
                "7. Term and Termination",
                "This Agreement continues for 2 years from the Effective Date.",
                "term_and_termination",
            ),
            (
                "8. Remedies",
                "Damages may be inadequate and injunctive relief may be sought. The Recipient shall pay liquidated damages of S$50,000 for each breach.",
                "remedies",
            ),
            (
                "9. Personal Data",
                "Each party shall comply with the Personal Data Protection Act 2012 (PDPA).",
                "data_protection",
            ),
            (
                "10. Governing Law",
                "This Agreement is governed by the laws of Singapore.",
                "governing_law",
            ),
            (
                "11. Dispute Resolution",
                "Any dispute shall be referred to arbitration administered by SIAC.",
                "dispute_resolution",
            ),
            (
                "12. Notices",
                "Notices shall be in writing and delivered to the addresses above.",
                "notices",
            ),
            (
                "13. Entire Agreement",
                "This Agreement is the entire agreement between the parties.",
                "entire_agreement",
            ),
        ],
    },
    "my_one_way_nda": {
        "meta": {"contract_type": "NDA", "governing_law": "MY", "languages": ["en"]},
        "playbook": "nda_my",
        "expected_findings": {
            "confidentiality_core": "standard",
            "term_length": "missing",
            "exclusions_present": "missing",
            "permitted_disclosure_present": "missing",
            "return_destroy": "missing",
            "governing_law_my": "standard",
            "forum": "missing",
            "liability_not_unlimited": "standard",
            "liability_cap_floor": "non_standard",
            "non_solicit_max": "standard",
            "personal_data": "missing",
        },
        "title": "CONFIDENTIALITY AGREEMENT",
        "preamble": [
            'Between Petaling Logistics Sdn. Bhd. (the "Discloser") and Klang Freight Sdn. Bhd. (the "Recipient").',
        ],
        "clauses": [
            (
                "1. Interpretation",
                "Words importing the singular include the plural.",
                "definitions",
            ),
            (
                "2. Obligations of the Recipient",
                "The Recipient shall not disclose Confidential Information to any third party.",
                "confidentiality_obligations",
            ),
            (
                "3. No Licence",
                "Nothing in this Agreement grants any licence to intellectual property.",
                "no_license",
            ),
            (
                "4. No Warranty",
                "All information is provided as is without warranty.",
                "no_warranty",
            ),
            (
                "5. Limitation of Liability",
                "The Discloser's aggregate liability shall not exceed RM10,000.",
                "limitation_of_liability",
            ),
            (
                "6. Non-Solicitation",
                "The Recipient shall not solicit employees of the Discloser for 12 months.",
                "non_solicitation",
            ),
            (
                "7. Assignment",
                "Neither party may assign this Agreement without consent.",
                "assignment",
            ),
            (
                "8. Governing Law and Jurisdiction",
                "This Agreement shall be governed by the laws of Malaysia and the courts of Kuala Lumpur shall have jurisdiction.",
                "governing_law",
            ),
            ("9. Counterparts", "This Agreement may be executed in counterparts.", "language"),
        ],
    },
    "vn_bilingual_nda": {
        "meta": {"contract_type": "NDA", "governing_law": "VN", "languages": ["vi", "en"]},
        "title": "THỎA THUẬN BẢO MẬT / NON-DISCLOSURE AGREEMENT",
        "preamble": [
            "Các bên: Công ty Cổ phần Sông Hồng JSC và Saigon Tech Co., Ltd.",
            "Parties: Song Hong JSC and Saigon Tech Co., Ltd.",
        ],
        "clauses": [
            (
                "Điều 1. Định nghĩa / Definitions",
                "Thông tin mật là mọi thông tin do một bên cung cấp. Confidential Information means any information disclosed.",
                "definitions",
            ),
            (
                "Điều 2. Nghĩa vụ bảo mật / Confidentiality",
                "Bên nhận phải giữ bí mật thông tin. The Recipient shall keep information confidential.",
                "confidentiality_obligations",
            ),
            (
                "Điều 3. Thời hạn / Term",
                "Thỏa thuận có hiệu lực trong 2 năm. This Agreement lasts 2 years.",
                "term_and_termination",
            ),
            (
                "Điều 4. Dữ liệu cá nhân / Personal Data",
                "Các bên tuân thủ quy định về bảo vệ dữ liệu cá nhân. The parties comply with personal data protection laws.",
                "data_protection",
            ),
            (
                "Điều 5. Luật áp dụng / Governing Law",
                "Thỏa thuận này được điều chỉnh bởi pháp luật Việt Nam. Governed by the laws of Vietnam.",
                "governing_law",
            ),
            (
                "Điều 6. Giải quyết tranh chấp / Dispute Resolution",
                "Tranh chấp được giải quyết tại Trung tâm Trọng tài Quốc tế Việt Nam (VIAC).",
                "dispute_resolution",
            ),
            (
                "Điều 7. Ngôn ngữ / Language",
                "Thỏa thuận được lập bằng tiếng Việt và tiếng Anh; bản tiếng Việt được ưu tiên.",
                "language",
            ),
        ],
    },
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, spec in DOCS.items():
        doc = Document()
        doc.add_heading(spec["title"], level=0)
        for line in spec["preamble"]:
            doc.add_paragraph(line)
        labels = [{"heading": "Preamble", "key": "parties"}]
        for heading, body, key in spec["clauses"]:
            doc.add_paragraph(heading)
            doc.add_paragraph(body)
            labels.append(
                {
                    "heading": heading.split(" ", 1)[1] if heading[0].isdigit() else heading,
                    "key": key,
                }
            )
        doc.save(OUT / f"{name}.docx")
        (OUT / f"{name}.json").write_text(
            json.dumps(
                {
                    **spec["meta"],
                    "playbook": spec.get("playbook"),
                    "expected_findings": spec.get("expected_findings", {}),
                    "clauses": labels,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        print(f"wrote {name}")


if __name__ == "__main__":
    main()
