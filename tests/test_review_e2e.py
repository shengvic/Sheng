"""P1 review engine end-to-end: upload → durable review → findings → dispositions → gate →
redline/memo DOCX exports."""

import io
import zipfile

from tests.conftest import review_document


def _findings(client, t, review_id, who="admin"):
    return client.get(f"/v1/reviews/{review_id}/findings", headers=t.headers(who)).json()


def test_sg_review_end_to_end(client, make_tenant):
    t = make_tenant()
    matter, doc, review = review_document(client, t, "sg_mutual_nda")
    assert review["status"] == "completed", review
    assert [s["name"] for s in review["steps"]] == [
        "prepare",
        "bilingual",  # runs, but skips an English-only contract
        "compare",
        "lawcheck",
        "redline",
        "memo",
    ]
    assert review["playbook_key"] == "nda_sg" and review["playbook_source"] == "starter"
    assert "issue" in review["summary"]["executive_summary"]

    findings = _findings(client, t, review["id"])
    by_rule = {f["rule_key"]: f for f in findings}
    assert by_rule["term_length"]["classification"] == "fallback"
    assert by_rule["term_length"]["severity"] == "high"
    assert by_rule["governing_law_sg"]["severity"] == "info"

    law = [f for f in findings if f["kind"] == "law"]
    assert {f["rule_key"] for f in law} >= {
        "law:SG:agreed_damages",
        "law:SG:personal_data_transfer",
    }
    for f in law:
        assert f["citations"], f
        assert all(c["status"] == "supported" for c in f["citations"]), f
        assert all("FIXTURE" in (c["pinpoint"] or "") for c in f["citations"])
        assert "[[src:" in f["summary"]
    # Repealed / not-yet-in-force fixture units never cited.
    cited = {c["source_unit_id"] for f in law for c in f["citations"]}
    assert not any("FIXTURE-OLD" in u or u.endswith("#s 9") for u in cited)

    # Gate closed until every non-info finding is dispositioned.
    gate = client.get(f"/v1/reviews/{review['id']}/export-gate", headers=t.headers()).json()
    assert not gate["open"]
    r = client.post(
        f"/v1/reviews/{review['id']}/exports", json={"format": "memo_docx"}, headers=t.headers()
    )
    assert r.status_code == 409
    for f in findings:
        if f["severity"] == "info":
            continue
        body = {"action": "accept"}
        if f["rule_key"] == "term_length":
            body = {"action": "edit", "edited_text": "This Agreement continues for five (5) years."}
        assert (
            client.patch(f"/v1/findings/{f['id']}", json=body, headers=t.headers()).status_code
            == 200
        )
    gate = client.get(f"/v1/reviews/{review['id']}/export-gate", headers=t.headers()).json()
    assert gate == {"open": True, "blocking": []}

    red = client.post(
        f"/v1/reviews/{review['id']}/exports", json={"format": "redline_docx"}, headers=t.headers()
    )
    assert red.status_code == 201, red.text
    data = client.get(f"/v1/exports/{red.json()['id']}", headers=t.headers()).content
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode()
    assert "<w:ins" in xml and "<w:del " in xml and "Travo (draft)" in xml
    assert "five (5) years" in xml
    assert "continues for 2 years" in xml  # original kept as tracked deletion

    memo = client.post(
        f"/v1/reviews/{review['id']}/exports", json={"format": "memo_docx"}, headers=t.headers()
    )
    assert memo.status_code == 201
    mxml = (
        zipfile.ZipFile(
            io.BytesIO(client.get(f"/v1/exports/{memo.json()['id']}", headers=t.headers()).content)
        )
        .read("word/document.xml")
        .decode()
    )
    assert "Issues list" in mxml and "FIXTURE" in mxml


def test_my_review_missing_clauses_and_redlines(client, make_tenant):
    t = make_tenant()
    _, _, review = review_document(client, t, "my_one_way_nda")
    assert review["status"] == "completed", review
    by_rule = {
        f["rule_key"]: f
        for f in _findings(
            client,
            t,
            review["id"],
        )
    }
    assert by_rule["term_length"]["classification"] == "missing"
    assert by_rule["liability_cap_floor"]["classification"] == "non_standard"
    assert "RM500,000" in by_rule["liability_cap_floor"]["suggested_redline"]
    assert by_rule["term_length"]["suggested_redline"].startswith("This Agreement continues")
    assert by_rule["term_length"]["clause_id"] is None


def test_review_requires_matching_playbook(client, make_tenant):
    from tests.conftest import create_matter, upload

    t = make_tenant()
    m = create_matter(client, t, jurisdictions=["VN"])
    doc = upload(client, t, m["id"], "vn_bilingual_nda").json()
    r = client.post(f"/v1/documents/{doc['id']}/reviews", json={}, headers=t.headers())
    assert r.status_code == 422
    r = client.post(
        f"/v1/documents/{doc['id']}/reviews", json={"playbook_key": "nda_sg"}, headers=t.headers()
    )
    assert r.status_code == 202
