"""P0 exit criterion: upload NDA → classify → extract clauses via router → visible."""

from tests.conftest import create_matter, upload


def test_upload_classify_extract(client, make_tenant):
    t = make_tenant()
    matter = create_matter(client, t)
    r = upload(client, t, matter["id"])
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["parse_status"] == "classified", doc
    assert doc["contract_type"] == "NDA"
    assert doc["governing_law"] == "SG"
    assert doc["languages"][0] == "en"
    assert any("Lion City Robotics" in p for p in doc["parties"])

    clauses = client.get(f"/v1/documents/{doc['id']}/clauses", headers=t.headers()).json()
    keys = [c["taxonomy_key"] for c in clauses]
    assert keys[0] == "parties"
    for expected in ("confidentiality_obligations", "governing_law", "dispute_resolution"):
        assert expected in keys

    decisions = client.get(
        "/v1/admin/routing-decisions", params={"matter_id": matter["id"]}, headers=t.headers()
    ).json()
    tasks = {d["task_type"] for d in decisions}
    assert tasks == {"classify", "clause_extraction"}
    for d in decisions:
        assert d["outcome"] == "ok"
        assert d["chosen_endpoint"] == "travo-rules-v0"
        reasons = {f["endpoint_id"]: f["reason"] for f in d["filtered"]}
        # No keys configured in tests: BYO endpoints lack credentials, Travo endpoints disabled.
        assert reasons["openai-byo-frontier"] in {"no_byo_credential", "tier_above_rule"}
        assert reasons["fireworks-t1-openweight"] == "endpoint_disabled"

    actions = [
        e["action"]
        for e in client.get(
            "/v1/admin/audit", params={"matter_id": matter["id"]}, headers=t.headers()
        ).json()
    ]
    assert {"matter.created", "document.uploaded", "document.classified"} <= set(actions)


def test_vietnamese_bilingual_nda(client, make_tenant):
    t = make_tenant()
    matter = create_matter(client, t, jurisdictions=["VN"])
    doc = upload(client, t, matter["id"], "vn_bilingual_nda").json()
    assert doc["contract_type"] == "NDA"
    assert doc["governing_law"] == "VN"
    assert set(doc["languages"]) >= {"vi", "en"}


def test_unsupported_upload_rejected(client, make_tenant):
    t = make_tenant()
    matter = create_matter(client, t)
    r = client.post(
        f"/v1/matters/{matter['id']}/documents",
        files={"file": ("x.exe", b"MZ\x90\x00binary", "application/octet-stream")},
        headers=t.headers(),
    )
    assert r.status_code == 415
