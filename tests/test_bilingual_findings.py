"""Bilingual discrepancy findings (R2, ADR-023). Synthetic FIXTURE contracts only."""

from __future__ import annotations

from travo_agents.base import AgentContext
from travo_agents.bilingual import ClausePair, check_bilingual, deterministic_diffs

from evals import vn_fixtures as vn

LANGS = ("vi", "en")


def pair(vb: str, eb: str, key: str = "other", i: int = 1) -> ClausePair:
    return ClausePair(i, key, "", vb, eb)


def kinds(vb: str, eb: str, key: str = "other") -> set[str]:
    return {d.kind for d in deterministic_diffs(pair(vb, eb, key), LANGS)}


def test_matching_versions_have_no_differences():
    for _vh, vb, _eh, eb, key in vn.NDA_CLAUSES:
        assert deterministic_diffs(pair(vb, eb, key), LANGS) == [], (key, vb, eb)


def test_each_seeded_discrepancy_is_found():
    assert "duration" in kinds("thời hạn hai (02) năm", "for three (3) years")
    assert "figure_words" in kinds(
        "phạt 200.000.000 đồng (Bằng chữ: Một trăm triệu đồng)", "a penalty of VND 200,000,000"
    )
    assert "amount" in kinds("giá 100.000.000 VND", "price VND 150,000,000")
    assert "percent" in kinds("phạt 8% giá trị", "a penalty of 10% of the value")
    assert "date" in kinds("từ ngày 01 tháng 02 năm 2026", "from 2 January 2026")
    assert "number" in kinds("trong vòng 30 ngày", "within 45 days")
    assert "negation" in kinds("Bên Nhận không được tiết lộ.", "The Recipient may disclose.")
    assert "tax_code" in kinds("Mã số thuế: 0101234567", "Tax code: 0101234568")
    assert kinds("Bên Nhận phải bảo mật.", "", "confidentiality_obligations") == {
        "missing_counterpart"
    }


class _Router:
    """Stands in for the router: returns one grounded and one invented semantic difference."""

    def complete(self, descriptor, messages, ctx):  # type: ignore[no-untyped-def]
        import json
        from types import SimpleNamespace

        assert descriptor.task_type == "bilingual_check"
        pairs = json.loads(messages[1].content)["pairs"]
        first = pairs[0]
        diffs = [
            {"i": first["i"], "severity": "high", "summary": "Scope differs.",
             "a_span": first["a"][:12], "b_span": first["b"][:12]},
            {"i": first["i"], "severity": "high", "summary": "Invented.",
             "a_span": "không có trong văn bản", "b_span": "not in the text"},
        ]  # fmt: skip
        return SimpleNamespace(
            completion=SimpleNamespace(text=json.dumps({"differences": diffs})),
            record=SimpleNamespace(chosen_endpoint="fake-t1", chosen_tier="T1"),
        )


def test_check_bilingual_reports_seeded_issues_and_grounds_model_output():
    pairs = [
        ClausePair(i, key, vh, vb, eb)
        for i, (vh, vb, eh, eb, key) in enumerate(vn.seeded_clauses(), 1)
    ]
    ctx = AgentContext(router=_Router(), router_ctx=None, tenant_id="t", matter_id="m")
    drafts = check_bilingual(ctx, pairs, LANGS)
    found = {(d.clause_key, d.evidence["type"]) for d in drafts}
    for key, kind in vn.SEEDED.items():
        assert (key, kind) in found, (key, kind, found)
    semantic = [d for d in drafts if d.evidence["type"] == "semantic"]
    assert [d.summary for d in semantic] == ["Scope differs."]  # the invented one is dropped
    assert all(d.kind == "bilingual" and d.classification == "discrepancy" for d in drafts)
    contradiction = next(d for d in drafts if d.evidence["type"] == "prevailing_language")
    assert contradiction.severity == "high"


def test_bilingual_review_step_end_to_end(client, make_tenant):
    from tests.conftest import DOCX_MIME, create_matter, run_reviews

    t = make_tenant()
    matter = create_matter(client, t, jurisdictions=["VN"])
    doc = client.post(
        f"/v1/matters/{matter['id']}/documents",
        files={"file": ("nda.docx", vn.table_docx(vn.seeded_clauses()), DOCX_MIME)},
        headers=t.headers(),
    ).json()
    r = client.post(f"/v1/documents/{doc['id']}/reviews", json={}, headers=t.headers())
    assert r.status_code == 202, r.text
    run_reviews()
    review = client.get(f"/v1/reviews/{r.json()['id']}", headers=t.headers()).json()
    assert review["status"] == "completed", review
    assert review["playbook_key"] == "nda_vn"  # chosen from contract type + governing law
    assert [s["name"] for s in review["steps"]][:2] == ["prepare", "bilingual"]
    findings = client.get(f"/v1/reviews/{review['id']}/findings", headers=t.headers()).json()
    bilingual = [f for f in findings if f["kind"] == "bilingual"]
    types = {(f["clause_key"], f["evidence"]["type"]) for f in bilingual}
    for key, kind in vn.SEEDED.items():
        assert (key, kind) in types, (key, kind, types)
    fw = next(f for f in bilingual if f["evidence"]["type"] == "figure_words")
    assert "200.000.000" in fw["evidence"]["primary_span"] and fw["severity"] == "high"


def test_bilingual_review_writes_both_languages(client, make_tenant):
    from tests.conftest import DOCX_MIME, create_matter, run_reviews

    t = make_tenant()
    matter = create_matter(client, t, jurisdictions=["VN"])
    doc = client.post(
        f"/v1/matters/{matter['id']}/documents",
        files={"file": ("nda.docx", vn.table_docx(), DOCX_MIME)},
        headers=t.headers(),
    ).json()
    run = client.post(f"/v1/documents/{doc['id']}/reviews", json={}, headers=t.headers()).json()
    assert run["options"] == {"output_language": "both"}
    run_reviews()
    review = client.get(f"/v1/reviews/{run['id']}", headers=t.headers()).json()
    assert review["summary"]["executive_summary"].startswith("Phát hiện")
    assert "issue(s) identified" in review["summary"]["executive_summary_en"]
    findings = client.get(f"/v1/reviews/{run['id']}/findings", headers=t.headers()).json()
    excl = next(f for f in findings if f["rule_key"] == "exclusions_present")
    assert excl["classification"] == "missing"
    assert excl["suggested_redline"].startswith("Nghĩa vụ bảo mật không áp dụng")
    assert excl["suggested_redline_alt"].startswith("The obligations in this Agreement")
    law = [f for f in findings if f["kind"] == "law"]
    assert law and all(any(ch in f["summary"] for ch in "ểệạ") for f in law)  # Vietnamese


def test_output_language_can_be_chosen(client, make_tenant):
    from tests.conftest import DOCX_MIME, create_matter

    t = make_tenant()
    matter = create_matter(client, t, jurisdictions=["VN"])
    doc = client.post(
        f"/v1/matters/{matter['id']}/documents",
        files={"file": ("nda.docx", vn.table_docx(), DOCX_MIME)},
        headers=t.headers(),
    ).json()
    run = client.post(
        f"/v1/documents/{doc['id']}/reviews", json={"output_language": "en"}, headers=t.headers()
    ).json()
    assert run["options"] == {"output_language": "en"}
