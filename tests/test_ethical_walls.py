"""Ethical walls: only matter members reach matter content — admins included."""

from tests.conftest import create_matter, upload


def test_non_member_and_screened_cannot_access(client, make_tenant):
    t = make_tenant(roles={"partner": "partner", "associate": "associate", "lateral": "associate"})
    matter = create_matter(client, t, who="partner")
    doc = upload(client, t, matter["id"], who="partner").json()

    r = client.put(
        f"/v1/matters/{matter['id']}/members",
        json={
            "members": [
                {"user_id": t.users["partner"], "access": "member"},
                {"user_id": t.users["associate"], "access": "member"},
                {"user_id": t.users["lateral"], "access": "screened"},
            ]
        },
        headers=t.headers("partner"),
    )
    assert r.status_code == 204, r.text

    assert (
        client.get(f"/v1/documents/{doc['id']}/clauses", headers=t.headers("associate")).status_code
        == 200
    )
    for who in ("lateral", "admin"):
        h = t.headers(who)
        assert client.get(f"/v1/matters/{matter['id']}", headers=h).status_code == 404
        assert client.get(f"/v1/documents/{doc['id']}", headers=h).status_code == 404
        assert client.get(f"/v1/documents/{doc['id']}/clauses", headers=h).status_code == 404
        assert upload(client, t, matter["id"], who=who).status_code == 404
        assert matter["id"] not in [m["id"] for m in client.get("/v1/matters", headers=h).json()]

    denials = client.get(
        "/v1/admin/audit", params={"action": "matter.access_denied"}, headers=t.headers()
    ).json()
    assert len(denials) >= 8
    assert all(d["result"] == "denied" for d in denials)


def test_associate_cannot_change_wall(client, make_tenant):
    t = make_tenant()
    matter = create_matter(client, t, who="associate")
    r = client.put(
        f"/v1/matters/{matter['id']}/members",
        json={"members": [{"user_id": t.users["associate"], "access": "member"}]},
        headers=t.headers("associate"),
    )
    assert r.status_code == 403


def test_wall_rejects_users_from_other_tenant(client, make_tenant):
    a, b = make_tenant("A"), make_tenant("B")
    matter = create_matter(client, a, who="partner")
    r = client.put(
        f"/v1/matters/{matter['id']}/members",
        json={
            "members": [
                {"user_id": a.users["partner"], "access": "member"},
                {"user_id": b.users["partner"], "access": "member"},
            ]
        },
        headers=a.headers("partner"),
    )
    assert r.status_code == 422


def test_admin_endpoints_require_admin(client, make_tenant):
    t = make_tenant()
    assert client.get("/v1/admin/audit", headers=t.headers("partner")).status_code == 403
    assert client.get("/v1/admin/model-policy", headers=t.headers("associate")).status_code == 403
