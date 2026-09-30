"""Vietnam pilot gold set: synthetic bilingual contracts for the four launch types (ADR-023).

Everything is invented (FIXTURE parties; terms are not advice). Each spec has a clean version
and a seeded version: `seeded` maps a clause key to replacement (vi_body, en_body) and the
discrepancy type a reviewer must catch. `expected_findings` are playbook classifications on
the seeded version (rule key -> classification).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from evals.vn_fixtures import NDA_CLAUSES, PARTIES, TITLE, Clause, seeded_clauses


@dataclass
class Spec:
    name: str
    contract_type: str
    playbook: str
    title: tuple[str, str]
    clauses: list[Clause]
    seeded: dict[str, tuple[str, str, str]] = field(default_factory=dict)
    expected_findings: dict[str, str] = field(default_factory=dict)
    parties: tuple[str, str] = PARTIES

    def seeded_clauses(self) -> list[Clause]:
        out = []
        for vh, vb, eh, eb, key in self.clauses:
            if key in self.seeded:
                vb, eb, _ = self.seeded[key]
            out.append((vh, vb, eh, eb, key))
        return out

    def expected_kinds(self) -> dict[str, str]:
        return {k: v[2] for k, v in self.seeded.items()}


_LAW = (
    "Luật áp dụng",
    "Hợp đồng này được điều chỉnh bởi pháp luật Việt Nam.",
    "Governing Law",
    "This Contract is governed by the laws of Vietnam.",
    "governing_law",
)
_DISPUTES = (
    "Giải quyết tranh chấp",
    "Tranh chấp được giải quyết tại Trung tâm Trọng tài Quốc tế Việt Nam (VIAC).",
    "Dispute Resolution",
    "Disputes shall be settled by arbitration at the Vietnam International Arbitration "
    "Centre (VIAC).",
    "dispute_resolution",
)
_LANGUAGE = (
    "Ngôn ngữ",
    "Hợp đồng được lập bằng tiếng Việt và tiếng Anh; bản tiếng Việt được ưu tiên áp dụng.",
    "Language",
    "This Contract is made in Vietnamese and English; the Vietnamese version prevails.",
    "language",
)
_FORCE_MAJEURE = (
    "Bất khả kháng",
    "Bên bị ảnh hưởng bởi sự kiện bất khả kháng phải thông báo cho bên kia trong vòng 7 ngày.",
    "Force Majeure",
    "The party affected by a force majeure event shall notify the other party within 7 days.",
    "force_majeure",
)

_NDA_VI, _NDA_EN, _ = zip(*[(c[1], c[3], c[4]) for c in seeded_clauses()], strict=True)
NDA = Spec(
    name="vn_nda",
    contract_type="NDA",
    playbook="nda_vn",
    title=TITLE,
    clauses=NDA_CLAUSES,
    seeded={
        "term_and_termination": (NDA_CLAUSES[2][1], _NDA_EN[2], "duration"),
        "penalty": (_NDA_VI[3], _NDA_EN[3], "figure_words"),
        "confidentiality_obligations": (NDA_CLAUSES[1][1], _NDA_EN[1], "negation"),
        "language": (NDA_CLAUSES[6][1], _NDA_EN[6], "prevailing_language"),
    },
    expected_findings={"term_length": "standard", "governing_law_vn": "standard"},
)

SALE = Spec(
    name="vn_sale",
    contract_type="SALE",
    playbook="commercial_vn",
    title=("HỢP ĐỒNG MUA BÁN HÀNG HÓA", "SALES CONTRACT"),
    parties=(
        "Bên Bán: Công ty TNHH FIXTURE Hà Nội. Bên Mua: Công ty Cổ phần FIXTURE Đà Nẵng.",
        "Seller: FIXTURE Ha Noi Co., Ltd. Buyer: FIXTURE Da Nang JSC.",
    ),
    clauses=[
        (
            "Giá và thanh toán",
            "Tổng giá trị hợp đồng là 500.000.000 VND. Bên Mua thanh toán trong vòng 30 ngày "
            "kể từ ngày nhận hóa đơn.",
            "Price and Payment",
            "The total contract price is VND 500,000,000. The Buyer shall pay within 30 days "
            "of receiving the invoice.",
            "price_payment",
        ),
        (
            "Giao hàng và nghiệm thu",
            "Bên Bán giao hàng tại kho của Bên Mua trước ngày 15 tháng 03 năm 2026.",
            "Delivery and Acceptance",
            "The Seller shall deliver the goods to the Buyer's warehouse by 15 March 2026.",
            "delivery_acceptance",
        ),
        (
            "Bảo hành",
            "Bên Bán bảo hành hàng hóa trong thời hạn mười hai (12) tháng kể từ ngày giao hàng.",
            "Warranty",
            "The Seller warrants the goods for twelve (12) months from delivery.",
            "warranties",
        ),
        (
            "Phạt vi phạm",
            "Bên vi phạm phải chịu phạt 8% giá trị phần nghĩa vụ bị vi phạm.",
            "Penalty",
            "The breaching party shall pay a penalty of 8% of the value of the breached "
            "obligation.",
            "penalty",
        ),
        _FORCE_MAJEURE,
        _LAW,
        _DISPUTES,
        _LANGUAGE,
    ],
    seeded={
        "price_payment": (
            "Tổng giá trị hợp đồng là 500.000.000 VND. Bên Mua thanh toán trong vòng 30 ngày "
            "kể từ ngày nhận hóa đơn.",
            "The total contract price is VND 550,000,000. The Buyer shall pay within 30 days "
            "of receiving the invoice.",
            "amount",
        ),
        "delivery_acceptance": (
            "Bên Bán giao hàng tại kho của Bên Mua trước ngày 15 tháng 03 năm 2026.",
            "The Seller shall deliver the goods to the Buyer's warehouse by 15 April 2026.",
            "date",
        ),
        "penalty": (
            "Bên vi phạm phải chịu phạt 12% giá trị phần nghĩa vụ bị vi phạm.",
            "The breaching party shall pay a penalty of 8% of the value of the breached "
            "obligation.",
            "percent",
        ),
    },
    expected_findings={"penalty_cap": "non_standard", "governing_law_vn": "standard"},
)

SERVICES = Spec(
    name="vn_services",
    contract_type="MSA",
    playbook="services_vn",
    title=("HỢP ĐỒNG DỊCH VỤ", "SERVICES AGREEMENT"),
    parties=(
        "Bên Cung cấp: Công ty TNHH FIXTURE Cần Thơ. Khách hàng: Công ty Cổ phần FIXTURE Huế.",
        "Provider: FIXTURE Can Tho Co., Ltd. Customer: FIXTURE Hue JSC.",
    ),
    clauses=[
        (
            "Mức dịch vụ",
            "Bên Cung cấp bảo đảm thời gian hoạt động của dịch vụ đạt 99,5% mỗi tháng.",
            "Service Levels",
            "The Provider guarantees service uptime of 99.5% each month.",
            "service_levels",
        ),
        (
            "Phí dịch vụ và thanh toán",
            "Phí dịch vụ là 40.000.000 VND mỗi tháng, thanh toán trong vòng 15 ngày kể từ ngày "
            "nhận hóa đơn.",
            "Fees and Payment",
            "The service fee is VND 40,000,000 per month, payable within 15 days of receiving "
            "the invoice.",
            "price_payment",
        ),
        (
            "Bảo mật",
            "Mỗi bên phải giữ bí mật và không tiết lộ thông tin mật của bên kia cho bên thứ ba.",
            "Confidentiality",
            "Each party shall keep the other party's confidential information secret and shall "
            "not disclose it to any third party.",
            "confidentiality_obligations",
        ),
        (
            "Thời hạn và chấm dứt",
            "Hợp đồng có hiệu lực trong thời hạn một (01) năm; mỗi bên có thể chấm dứt bằng "
            "thông báo trước 30 ngày.",
            "Term and Termination",
            "This Agreement is in force for one (1) year; either party may terminate on 30 "
            "days' notice.",
            "term_and_termination",
        ),
        _FORCE_MAJEURE,
        _LAW,
        _DISPUTES,
        _LANGUAGE,
    ],
    seeded={
        "service_levels": (
            "Bên Cung cấp bảo đảm thời gian hoạt động của dịch vụ đạt 99,5% mỗi tháng.",
            "The Provider guarantees service uptime of 99.9% each month.",
            "percent",
        ),
        "price_payment": (
            "Phí dịch vụ là 40.000.000 VND (Bằng chữ: Bốn mươi lăm triệu đồng) mỗi tháng, thanh "
            "toán trong vòng 15 ngày kể từ ngày nhận hóa đơn.",
            "The service fee is VND 40,000,000 per month, payable within 15 days of receiving "
            "the invoice.",
            "figure_words",
        ),
        "term_and_termination": (
            "Hợp đồng có hiệu lực trong thời hạn một (01) năm; mỗi bên có thể chấm dứt bằng "
            "thông báo trước 30 ngày.",
            "This Agreement is in force for one (1) year; either party may terminate on 60 "
            "days' notice.",
            "duration",
        ),
    },
    expected_findings={"confidentiality": "standard", "governing_law_vn": "standard"},
)

DPA = Spec(
    name="vn_dpa",
    contract_type="DPA",
    playbook="dpa_vn",
    title=("THỎA THUẬN XỬ LÝ DỮ LIỆU CÁ NHÂN", "DATA PROCESSING AGREEMENT"),
    parties=(
        "Bên Kiểm soát: Công ty Cổ phần FIXTURE Hải Phòng. Bên Xử lý: Công ty TNHH FIXTURE "
        "Vũng Tàu.",
        "Controller: FIXTURE Hai Phong JSC. Processor: FIXTURE Vung Tau Co., Ltd.",
    ),
    clauses=[
        (
            "Phạm vi xử lý",
            "Bên Xử lý chỉ xử lý dữ liệu cá nhân của khách hàng theo chỉ dẫn bằng văn bản của "
            "Bên Kiểm soát.",
            "Scope of Processing",
            "The Processor shall process customer personal data only on the Controller's "
            "documented instructions.",
            "processing_scope",
        ),
        (
            "Biện pháp bảo mật",
            "Bên Xử lý áp dụng các biện pháp kỹ thuật và tổ chức để bảo vệ dữ liệu cá nhân.",
            "Security Measures",
            "The Processor shall apply technical and organisational measures to protect "
            "personal data.",
            "security_measures",
        ),
        (
            "Bên xử lý phụ",
            "Bên Xử lý không được sử dụng bên xử lý phụ khi chưa có sự đồng ý trước bằng văn "
            "bản của Bên Kiểm soát.",
            "Sub-processors",
            "The Processor shall not engage a sub-processor without the Controller's prior "
            "written consent.",
            "subprocessors",
        ),
        (
            "Chuyển dữ liệu ra nước ngoài",
            "Bên Xử lý không được chuyển dữ liệu cá nhân ra nước ngoài khi chưa có sự đồng ý "
            "của Bên Kiểm soát.",
            "Cross-border Transfer",
            "The Processor shall not transfer personal data abroad without the Controller's "
            "consent.",
            "cross_border_transfer",
        ),
        (
            "Thông báo vi phạm",
            "Bên Xử lý thông báo cho Bên Kiểm soát trong vòng 24 giờ kể từ khi phát hiện sự cố "
            "dữ liệu cá nhân.",
            "Breach Notification",
            "The Processor shall notify the Controller within 24 hours of discovering a personal "
            "data breach.",
            "breach_notification",
        ),
        (
            "Hoàn trả hoặc tiêu hủy",
            "Khi kết thúc việc xử lý, Bên Xử lý hoàn trả hoặc xóa toàn bộ dữ liệu cá nhân.",
            "Return or Deletion",
            "At the end of processing, the Processor shall return or delete all personal data.",
            "return_or_destruction",
        ),
        _LAW,
        _DISPUTES,
        _LANGUAGE,
    ],
    seeded={
        "breach_notification": (
            "Bên Xử lý thông báo cho Bên Kiểm soát trong vòng 24 giờ kể từ khi phát hiện sự cố "
            "dữ liệu cá nhân.",
            "The Processor shall notify the Controller within 72 hours of discovering a personal "
            "data breach.",
            "duration",
        ),
        "subprocessors": (
            "Bên Xử lý không được sử dụng bên xử lý phụ khi chưa có sự đồng ý trước bằng văn "
            "bản của Bên Kiểm soát.",
            "The Processor may engage sub-processors and shall inform the Controller.",
            "negation",
        ),
        "cross_border_transfer": (
            "Bên Xử lý không được chuyển dữ liệu cá nhân ra nước ngoài khi chưa có sự đồng ý "
            "của Bên Kiểm soát.",
            "",
            "missing_counterpart",
        ),
    },
    expected_findings={"subprocessors_consent": "standard", "governing_law_vn": "standard"},
)

SPECS: list[Spec] = [NDA, SALE, SERVICES, DPA]
