"""Parser checks against real AGC Malaysia reprints (ADR-020).

The PDFs are not in git (printer's copyright notice). Point `TRAVO_REAL_LEGAL_DIR` at a folder
holding `MY_ACT136.pdf`, `MY_ACT709.pdf`, `MY_ACT347.pdf` and `MY_ACT237.pdf` to run these.
No statute text is typed here: every expectation is derived from the PDF itself (its contents
table and its own numbered lines) or is a count/date.
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

import pytest
from travo_rag.sources.parsers import norm, pdf_pages, split_document, version_date

REAL = os.environ.get("TRAVO_REAL_LEGAL_DIR")
pytestmark = pytest.mark.skipif(not REAL, reason="TRAVO_REAL_LEGAL_DIR not set")

# file stem → (sections in the contents table, version date on the cover)
ACTS = {
    "MY_ACT136": (191, date(2006, 1, 1)),  # Contracts Act 1950
    "MY_ACT709": (146, date(2023, 7, 1)),  # Personal Data Protection Act 2010
    "MY_ACT347": (34, date(2006, 1, 1)),  # Houses of Parliament (Privileges and Powers) Act 1952
    "MY_ACT237": (14, date(2015, 8, 1)),  # Akta Ahli Parlimen (Saraan) 1980 (Malay)
}


@pytest.mark.parametrize("stem", sorted(ACTS))
def test_real_reprint_parses_completely(stem):
    path = Path(REAL or "") / f"{stem}.pdf"
    if not path.exists():
        pytest.skip(f"{path} missing")
    count, as_at = ACTS[stem]
    _, pages = pdf_pages(path.read_bytes())
    split = split_document(pages)

    numbers = [s.number for s in split.sections]
    assert numbers == [e.number for e in split.toc] and len(numbers) == count
    assert version_date([ln for p in pages for ln in p]) == as_at
    bad = [w for w in split.warnings if re.match(r"(accounting|in contents but|parsed but|sec)", w)]
    assert not bad, bad
    assert not [w for w in split.warnings if w.startswith("heading not found")]

    # Headings equal the contents table, apart from contents typos that are reported.
    differs = next((w for w in split.warnings if w.startswith("heading differs")), "")
    toc = {e.number: e for e in split.toc}
    for s in split.sections:
        entry = toc[s.number]
        if f"s {s.number}:" not in differs:
            options = {norm(" ".join(entry.lines[:b])) for b in range(1, len(entry.lines) + 1)}
            assert norm(s.heading) in options, s.number

    # Each section's text starts with the rest of its own numbered line in the PDF.
    flat = [ln for p in pages for ln in p]
    body_from = next(i for i, ln in enumerate(flat) if re.match(r"^(An|Suatu) (Act|Akta)\b", ln))
    for s in split.sections[:5] + split.sections[-3:]:
        line = next(ln for ln in flat[body_from:] if re.match(rf"^{s.number}\s*\.\s", ln))
        rest = re.sub(rf"^{s.number}\s*\.\s*", "", line)
        assert " ".join(s.text.split()).startswith(" ".join(rest.split())), s.number

    # No running header survives inside section text.
    for shape in split.chrome:
        if shape != "#" and not shape.startswith("<"):
            pattern = re.compile("^" + re.escape(shape).replace("\\#", r"\d+") + "$", re.I)
            assert not any(pattern.match(ln) for s in split.sections for ln in s.lines), shape


def test_real_contracts_act_ingests_unverified_and_is_retrievable(tmp_path, client, make_tenant):
    from urllib.parse import quote

    from travo_api.db import get_admin_engine, tenant_session
    from travo_rag import retrieval
    from travo_rag.legal_index import upsert_units
    from travo_rag.sources.fetch import SnapshotStore
    from travo_rag.sources.manifest import load_manifests
    from travo_rag.sources.parsers import parse_snapshot

    path = Path(REAL or "") / "MY_ACT136.pdf"
    if not path.exists():
        pytest.skip(f"{path} missing")
    manifest = load_manifests(Path(__file__).resolve().parents[1] / "config/legal_sources")["MY"]
    inst = next(i for i in manifest.instruments if i.id == "MY/ACT136")
    snap = SnapshotStore(tmp_path).save(
        inst, None, path.read_bytes(), "application/pdf", origin="supplied", filename=path.name
    )
    result = parse_snapshot(inst, snap, manifest.issuing_body)
    with get_admin_engine().begin() as c:
        assert upsert_units(c, result.units) == 191

    t = make_tenant()
    target = next(u for u in result.units if u.unit_path == "s 74")
    with tenant_session(t.tenant_id) as s:
        hits = retrieval.search(
            s, target.heading, jurisdictions=["MY"], as_of=date(2026, 9, 30), k=5
        )
        assert target.unit_id in [h.id for h in hits]
        gated = retrieval.search(
            s, target.heading, jurisdictions=["MY"], as_of=date(2026, 9, 30), k=5,
            require_verified=True,
        )  # fmt: skip
        assert target.unit_id not in [h.id for h in gated]  # unverified until a lawyer checks

    info = client.get(
        f"/v1/legal-units/{quote(target.unit_id, safe='')}", headers=t.headers()
    ).json()
    assert info["review_status"] == "unverified" and info["official_url"] is None
    assert info["issuing_body"] == manifest.issuing_body and not info["is_fixture"]
