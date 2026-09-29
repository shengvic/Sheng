from datetime import date

from travo_api.db import tenant_session
from travo_rag import citations as cite
from travo_rag import retrieval


def test_search_filters_jurisdiction_and_validity(make_tenant):
    t = make_tenant()
    with tenant_session(t.tenant_id) as s:
        hits = retrieval.search(
            s,
            "liquidated damages penalty genuine pre-estimate",
            jurisdictions=["SG"],
            as_of=date(2026, 9, 1),
            k=5,
        )
        ids = [h.id for h in hits]
        assert ids[0] == "SG/FIXTURE-CONTRACT-TERMS#s 3"
        assert "SG/FIXTURE-OLD#s 1" not in ids  # repealed
        assert "SG/FIXTURE-CONTRACT-TERMS#s 9" not in ids  # not yet in force
        assert all(not i.startswith("MY/") for i in ids)
        old = retrieval.search(
            s, "liquidated damages penalty", jurisdictions=["SG"], as_of=date(1995, 1, 1), k=5
        )
        assert [h.id for h in old] == []  # the repealed unit stays excluded by status
        assert retrieval.search(s, "the and of", jurisdictions=["SG"], as_of=date.today()) == []


def _lookup(session):
    return lambda uid: retrieval.get_unit(session, uid)


def test_validator_statuses(make_tenant):
    t = make_tenant()
    as_of = date(2026, 9, 1)
    good = (
        'A liquidated damages provision is enforceable where it is "a genuine pre-estimate '
        'of the loss caused by breach" [[src:SG/FIXTURE-CONTRACT-TERMS#s 3]].'
    )
    cases = {
        good: "supported",
        "Penalties are always enforceable [[src:SG/FIXTURE-MISSING#s 1]].": "invalid_source",
        "Agreed damages are fine [[src:SG/FIXTURE-OLD#s 1]].": "not_in_force",
        'It says "penalties are always enforceable" [[src:SG/FIXTURE-CONTRACT-TERMS#s 3]].': (
            "misquoted"
        ),
        "Unrelated marine insurance subrogation doctrine applies "
        "[[src:SG/FIXTURE-CONTRACT-TERMS#s 3]].": "not_found",
        "This clause is enforceable.": "uncited",
    }
    with tenant_session(t.tenant_id) as s:
        for textv, expected in cases.items():
            results = cite.validate(textv, lookup=_lookup(s), as_of=as_of)
            assert [r.status for r in results] == [expected], textv
    assert cite.validate(good, lookup=lambda _: None, as_of=as_of)[0].status == "invalid_source"


def test_split_claims_keeps_markers_per_sentence():
    claims = cite.split_claims("First claim [[src:a#1]]. Second claim [[src:b#2]] [[src:c#3]].")
    assert [c.cites for c in claims] == [["a#1"], ["b#2", "c#3"]]
