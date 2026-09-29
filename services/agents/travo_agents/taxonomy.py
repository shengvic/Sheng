"""Clause taxonomy v0 (NDA-focused) with multilingual keyword hints (en/vi/id/ms)."""

from __future__ import annotations

# key -> (description, heading/body keywords). Keywords are lowercase substrings.
CLAUSE_TAXONOMY: dict[str, tuple[str, list[str]]] = {
    "parties": (
        "Identification of the parties",
        ["parties", "các bên", "para pihak", "pihak-pihak"],
    ),
    "definitions": (
        "Defined terms",
        ["definition", "interpretation", "định nghĩa", "giải thích từ ngữ", "definisi", "tafsiran"],
    ),
    "purpose": ("Purpose of disclosure", ["purpose", "mục đích", "tujuan"]),
    "confidentiality_obligations": (
        "Recipient's duties to keep information confidential",
        [
            "confidentiality",
            "obligations of",
            "non-disclosure",
            "bảo mật",
            "kerahasiaan",
            "kerahsiaan",
        ],
    ),
    "exclusions": (
        "Information excluded from confidentiality",
        ["exclusion", "exception", "loại trừ", "ngoại lệ", "pengecualian"],
    ),
    "permitted_disclosure": (
        "Disclosures permitted by law or to representatives",
        [
            "permitted disclosure",
            "required by law",
            "compelled",
            "tiết lộ được phép",
            "pengungkapan yang diizinkan",
        ],
    ),
    "term_and_termination": (
        "Duration and termination",
        [
            "term",
            "termination",
            "duration",
            "thời hạn",
            "chấm dứt",
            "jangka waktu",
            "pengakhiran",
            "tempoh",
            "penamatan",
        ],
    ),
    "return_or_destruction": (
        "Return or destruction of information",
        ["return", "destruction", "hoàn trả", "tiêu hủy", "pengembalian", "pemusnahan"],
    ),
    "no_license": (
        "No licence or IP transfer",
        [
            "no licen",
            "intellectual property",
            "sở hữu trí tuệ",
            "kekayaan intelektual",
            "harta intelek",
        ],
    ),
    "no_warranty": ("Information provided as-is", ["warrant", "as is", "bảo đảm", "jaminan"]),
    "remedies": (
        "Injunctive relief and remedies",
        ["remed", "injunct", "biện pháp", "ganti rugi", "pemulihan", "relief"],
    ),
    "limitation_of_liability": (
        "Caps and exclusions of liability",
        ["limitation of liability", "liability", "trách nhiệm", "tanggung jawab", "liabiliti"],
    ),
    "non_solicitation": (
        "No poaching of employees/clients",
        ["non-solicit", "solicitation", "không lôi kéo", "larangan"],
    ),
    "data_protection": (
        "Personal data protection",
        [
            "data protection",
            "personal data",
            "pdpa",
            "dữ liệu cá nhân",
            "pelindungan data",
            "data peribadi",
        ],
    ),
    "governing_law": (
        "Governing law",
        [
            "governing law",
            "applicable law",
            "luật áp dụng",
            "luật điều chỉnh",
            "hukum yang berlaku",
            "undang-undang yang mentadbir",
        ],
    ),
    "dispute_resolution": (
        "Courts / arbitration",
        [
            "dispute",
            "arbitration",
            "jurisdiction",
            "tranh chấp",
            "trọng tài",
            "sengketa",
            "arbitrase",
            "pertikaian",
            "timbang tara",
        ],
    ),
    "notices": ("Notices", ["notice", "thông báo", "pemberitahuan", "notis"]),
    "assignment": (
        "Assignment / transfer",
        ["assignment", "assign", "chuyển nhượng", "pengalihan", "penyerahhakan"],
    ),
    "entire_agreement": (
        "Entire agreement / boilerplate",
        [
            "entire agreement",
            "miscellaneous",
            "general",
            "toàn bộ thỏa thuận",
            "điều khoản chung",
            "lain-lain",
            "am",
        ],
    ),
    "language": (
        "Prevailing language / counterparts",
        ["language", "counterpart", "ngôn ngữ", "bahasa"],
    ),
    "signatures": (
        "Execution blocks",
        [
            "signature",
            "signed",
            "in witness",
            "ký tên",
            "đại diện",
            "tanda tangan",
            "ditandatangani",
        ],
    ),
    "other": ("Not in taxonomy", []),
}

CLAUSE_KEYS = list(CLAUSE_TAXONOMY)

CONTRACT_TYPES: dict[str, list[str]] = {
    "NDA": [
        "non-disclosure",
        "confidentiality agreement",
        "nda",
        "thỏa thuận bảo mật",
        "perjanjian kerahasiaan",
        "perjanjian kerahsiaan",
    ],
    "MSA": [
        "master services agreement",
        "services agreement",
        "hợp đồng dịch vụ",
        "perjanjian layanan",
        "perjanjian perkhidmatan",
    ],
    "SPA": [
        "share purchase agreement",
        "sale and purchase of shares",
        "hợp đồng mua bán cổ phần",
        "perjanjian jual beli saham",
    ],
    "SHA": [
        "shareholders agreement",
        "shareholders' agreement",
        "thỏa thuận cổ đông",
        "perjanjian pemegang saham",
    ],
    "LEASE": ["lease agreement", "tenancy agreement", "hợp đồng thuê", "perjanjian sewa"],
    "EMPLOYMENT": [
        "employment agreement",
        "employment contract",
        "hợp đồng lao động",
        "perjanjian kerja",
    ],
    "DISTRIBUTION": [
        "distribution agreement",
        "distributor",
        "hợp đồng phân phối",
        "perjanjian distribusi",
    ],
    "LOAN": ["facility agreement", "loan agreement", "hợp đồng vay", "perjanjian pinjaman"],
    "DPA": ["data processing agreement", "data processing addendum"],
}

GOVERNING_LAW_HINTS: dict[str, list[str]] = {
    "SG": ["laws of singapore", "laws of the republic of singapore", "singapore law"],
    "MY": ["laws of malaysia", "malaysian law", "undang-undang malaysia"],
    "VN": [
        "laws of vietnam",
        "laws of viet nam",
        "laws of the socialist republic of vietnam",
        "pháp luật việt nam",
        "vietnamese law",
    ],
    "ID": [
        "laws of indonesia",
        "laws of the republic of indonesia",
        "hukum negara republik indonesia",
        "hukum republik indonesia",
        "indonesian law",
    ],
}
