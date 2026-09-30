"""Official-source pipeline (ADR-019), exercised on synthetic pages — never real law."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from travo_rag.legal_index import dump_jsonl, read_jsonl, upsert_units
from travo_rag.sources.fetch import FetchError, PoliteFetcher, SnapshotStore
from travo_rag.sources.manifest import Instrument, Manifest, load_manifests
from travo_rag.sources.parsers import (
    ParseError,
    parse_snapshot,
    split_document,
    split_sections,
    version_date,
)
from travo_rag.sources.pipeline import run, write_outputs

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(__file__).parent / "fixtures" / "legal_samples"
HTML = (SAMPLES / "sso_like.html").read_bytes()


def inst(**kw) -> Instrument:
    base = {
        "id": "SG/FIXTURE2099",
        "title": "FIXTURE Contract Terms Act 2099",
        "url": "https://statutes.example.test/Act/FIXTURE2099",
        "format": "sso_html",
        "expect_title": "FIXTURE Contract Terms Act",
    }
    return Instrument.model_validate({**base, **kw})


def manifest(*instruments: Instrument) -> Manifest:
    return Manifest(jurisdiction="SG", issuing_body="FIXTURE issuer", instruments=list(instruments))


class Clock:
    def __init__(self) -> None:
        self.t = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(round(s, 2))
        self.t += s


def fetcher(handler, clock: Clock | None = None, **kw) -> PoliteFetcher:
    clock = clock or Clock()
    return PoliteFetcher(
        httpx.Client(transport=httpx.MockTransport(handler)),
        user_agent="TravoTest/1",
        clock=clock.now,
        sleep=clock.sleep,
        **kw,
    )


def site(pages: dict[str, tuple[int, bytes]], robots: tuple[int, str] = (200, "")):
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.path)
        if req.url.path == "/robots.txt":
            return httpx.Response(robots[0], text=robots[1])
        status, body = pages.get(req.url.path, (404, b""))
        return httpx.Response(status, content=body, headers={"content-type": "text/html"})

    return handler, calls


# ---------------------------------------------------------------- manifest


def test_shipped_manifests_are_valid():
    ms = load_manifests(ROOT / "config" / "legal_sources")
    assert set(ms) == {"SG", "MY", "VN"}
    assert all(i.url for i in ms["SG"].instruments)
    assert all(i.url is None for i in ms["MY"].instruments)  # never guessed
    assert all(i.url is None for i in ms["VN"].instruments)  # until vbpl.vn is reachable


def test_manifest_rejects_duplicates_and_wrong_prefix():
    with pytest.raises(ValidationError):
        manifest(inst(), inst())
    with pytest.raises(ValidationError):
        manifest(inst(id="MY/X1"))


# ---------------------------------------------------------------- fetch


def test_robots_disallow_and_unavailable_robots_block_fetching():
    handler, calls = site(
        {"/Act/FIXTURE2099": (200, HTML)}, robots=(200, "User-agent: *\nDisallow: /Act/")
    )
    with pytest.raises(FetchError, match="robots"):
        fetcher(handler).get("https://statutes.example.test/Act/FIXTURE2099")
    assert "/Act/FIXTURE2099" not in calls
    handler, _ = site({"/Act/FIXTURE2099": (200, HTML)}, robots=(503, ""))
    with pytest.raises(FetchError, match="robots"):
        fetcher(handler).get("https://statutes.example.test/Act/FIXTURE2099")
    handler, _ = site({"/Act/FIXTURE2099": (200, HTML)}, robots=(404, ""))
    body, _ = fetcher(handler).get("https://statutes.example.test/Act/FIXTURE2099")
    assert body == HTML


def test_rate_limit_retry_and_size_cap():
    attempts = {"n": 0}

    def flaky(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.path == "/big":
            return httpx.Response(200, content=b"x" * 50)
        attempts["n"] += 1
        return httpx.Response(503) if attempts["n"] == 1 else httpx.Response(200, content=b"ok")

    clock = Clock()
    f = fetcher(flaky, clock, min_interval=2.0, max_bytes=10)
    assert f.get("https://a.test/page")[0] == b"ok"
    # robots → page (wait 2s) → 503 backoff 2s → retry (already spaced)
    assert clock.sleeps[0] == 2.0 and 2.0 in clock.sleeps[1:]
    with pytest.raises(FetchError, match="larger"):
        f.get("https://a.test/big")

    def gone(req):
        return httpx.Response(404) if req.url.path != "/robots.txt" else httpx.Response(404)

    with pytest.raises(FetchError, match="404"):
        fetcher(gone).get("https://a.test/x")


def test_snapshots_are_immutable_and_checked(tmp_path):
    store = SnapshotStore(tmp_path)
    i = inst()
    snap = store.save(i, i.url, HTML, "text/html", now=datetime(2026, 9, 30, tzinfo=UTC))
    assert store.latest(i) == snap
    snap.path.write_bytes(HTML + b"tampered")
    with pytest.raises(FetchError, match="altered"):
        store.latest(i)


# ---------------------------------------------------------------- parse


def test_sso_like_html_parses_sections_headings_and_version(tmp_path):
    snap = SnapshotStore(tmp_path).save(
        inst(), "https://statutes.example.test/x", HTML, "text/html"
    )
    r = parse_snapshot(inst(), snap, "FIXTURE issuer")
    paths = [u.unit_path for u in r.units]
    assert paths == ["s 1", "s 2", "s 2A", "s 3"]  # TOC, nav, footer and schedule excluded
    by = {u.unit_path: u for u in r.units}
    assert by["s 2"].heading == "Exclusion of liability"
    assert by["s 2"].text.splitlines() == [
        "(1) A FIXTURE term excluding liability is effective only if it is reasonable.",
        "(2) Reasonableness is judged at the FIXTURE time of contracting.",
    ]
    assert "amendment note" not in by["s 2"].text
    assert by["s 2A"].heading == "Agreed sums"
    assert all(u.effective_from == date(2026, 3, 15) for u in r.units)
    src = r.units[0].source
    assert src.snapshot_sha256 == snap.sha256 and not src.is_fixture
    assert src.official_url == "https://statutes.example.test/x"


def test_title_mismatch_and_too_few_sections_are_refused(tmp_path):
    store = SnapshotStore(tmp_path)
    wrong = inst(expect_title="Personal Data Protection Act")
    with pytest.raises(ParseError, match="expected title"):
        parse_snapshot(wrong, store.save(wrong, "u", HTML, "text/html"), "x")
    thin = b"<html><title>FIXTURE Contract Terms Act</title><p>1. Only one.</p></html>"
    with pytest.raises(ParseError, match="only 1 sections"):
        parse_snapshot(inst(), store.save(inst(), "u", thin, "text/html"), "x")


def _pdf(pages: list[list[str]]) -> bytes:
    """Minimal text PDF (Helvetica), enough for pypdf's extractor. Synthetic content only."""
    objs: list[bytes] = []
    kids = []
    font_id = 3 + 2 * len(pages)
    for i, lines in enumerate(pages):
        page_id, content_id = 3 + 2 * i, 4 + 2 * i
        kids.append(f"{page_id} 0 R")
        ops = ["BT", "/F1 11 Tf", "14 TL", "50 780 Td"]
        for ln in lines:
            safe = ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"({safe}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>".encode()
        )
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    all_objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>".encode(),
        *objs,
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(all_objs, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(all_objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += (
        f"trailer\n<< /Size {len(all_objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return bytes(out)


def test_act_style_pdf_drops_running_headers_and_toc(tmp_path):
    header = "LAWS OF FIXTURELAND"
    pdf = _pdf(
        [
            [
                header,
                "FIXTURE Agreements Act 2099",
                "Reprint as at 1 June 2025",
                "ARRANGEMENT OF SECTIONS",
                "1. Short title",
                "2. Agreed sums",
                "1",
            ],
            [
                header,
                "Short title",
                "1. This is the FIXTURE Agreements Act 2099 (not law).",
                "Agreed sums",
                "2. (1) A FIXTURE agreed sum is recoverable as reasonable",
                "compensation not exceeding the amount named.",
                "(2) FIXTURE proof of loss is not needed.",
                "2",
            ],
            [
                header,
                "Interpretation",
                "3. In this FIXTURE Act words have FIXTURE meanings.",
                "FIRST SCHEDULE",
                "1. FIXTURE schedule entry.",
                "3",
            ],
        ]
    )
    i = inst(id="SG/FIXTUREPDF", format="pdf", expect_title="FIXTURE Agreements Act 2099")
    r = parse_snapshot(i, SnapshotStore(tmp_path).save(i, "u", pdf, "application/pdf"), "x")
    assert [u.unit_path for u in r.units] == ["s 1", "s 2", "s 3"]
    s2 = r.units[1]
    assert s2.heading == "Agreed sums"
    assert s2.text.splitlines()[0].endswith("not exceeding the amount named.")
    assert header not in " ".join(u.text for u in r.units)
    assert r.units[0].effective_from == date(2025, 6, 1)


def test_splitter_warns_on_duplicates():
    secs, warns = split_sections(["1. First body text here.", "1. First body text here, longer."])
    assert len(secs) == 1 and secs[0].text.endswith("longer.") and warns


# Real AGC reprints (ADR-020) showed these layouts; the pages below imitate them with FIXTURE text.

HEAD_ODD, HEAD_EVEN = "FIXTURE Agreements {n}", "{n} Laws of Fixtureland ACT 999"


def _act_pages() -> list[list[str]]:
    """An AGC-style reprint: cover, contents with Parts and wrapped headings, running headers."""
    return [
        ["FIXTURE Agreements 1", "LAWS OF FIXTURELAND", "REPRINT", "Act 999",
         "FIXTURE AGREEMENTS ACT 2099", "Incorporating all amendments up", "to 1 January 2006"],
        ["2 Laws of Fixtureland ACT 999", "LAWS OF FIXTURELAND", "Act 999",
         "FIXTURE AGREEMENTS ACT 2099", "ARRANGEMENT OF SECTIONS", "PART I", "PRELIMINARY",
         "Section", "1. Short title", "2. Interpretation", "PART II", "OF FIXTURE PROMISES",
         "3. FIXTURE promises made by persons of", "sound mind", "4. (1) FIXTURE wagers void",
         "(2) Exception in favour of certain FIXTURE", "prizes"],
        ["FIXTURE Agreements 3", "Division 1", "Fixture Remedies", "5. Remedy for FIXTURE breach",
         "LAWS OF FIXTURELAND", "Act 999", "FIXTURE AGREEMENTS ACT 2099",
         "An Act relating to FIXTURE agreements (not law).", "PART I", "PRELIMINARY",
         "Short title", "1. This Act may be cited as the *FIXTURE Agreements Act 2099.",
         "*NOTE—FIXTURE editorial note about the short title,", "continued on this line."],
        ["4 Laws of Fixtureland ACT 999", "Interpretation",
         "2. In this FIXTURE Act the following words are used in the",
         "following senses, unless a contrary intention appears from the",
         "context", "(a) a FIXTURE promise is a promise;"],
        ["FIXTURE Agreements 5", "PART II", "OF FIXTURE PROMISES",
         "FIXTURE promises made by persons of", "sound mind",
         "3. Every FIXTURE promise by a person of sound mind binds him.", "ILLUSTRATION",
         "A promises B a FIXTURE horse. A is bound.", "FIXTURE wagers void",
         "4. (1) FIXTURE wagers are void.", "Exception in favour of certain FIXTURE prizes",
         "(2) FIXTURE prizes for races are not wagers."],
        ["6 Laws of Fixtureland ACT 999", "Division 1", "Fixture Remedies",
         "Remedy for FIXTURE breaches", "5. A party injured by a FIXTURE breach may recover.",
         "LIST OF AMENDMENTS", "Amending law Short title In force from", "- NIL -"],
    ]  # fmt: skip


def test_contents_driven_split_keeps_every_line():
    split = split_document(_act_pages(), title_hints=("FIXTURE Agreements Act 2099",))
    secs = {s.number: s for s in split.sections}
    assert list(secs) == ["1", "2", "3", "4", "5"]
    # Regression: a wrapped line without final punctuation ("context") used to be dropped.
    assert "unless a contrary intention appears from the context" in " ".join(
        secs["2"].text.split()
    )
    # Multi-line heading and Part lines are matched against the contents table.
    assert secs["3"].heading == "FIXTURE promises made by persons of sound mind"
    assert secs["3"].part == "PART II OF FIXTURE PROMISES"
    assert "PART II" not in secs["2"].text and "Fixture Remedies" not in secs["4"].text
    assert secs["5"].part == "Division 1 Fixture Remedies"
    # Contents typo ("breach" vs "breaches"): body wording kept, difference reported.
    assert secs["5"].heading == "Remedy for FIXTURE breaches"
    assert any("heading differs from contents" in w and "s 5" in w for w in split.warnings)
    # Side note of a subsection and an ILLUSTRATION label stay on their own lines.
    assert "Exception in favour of certain FIXTURE prizes" in secs["4"].text.splitlines()
    assert secs["3"].text.splitlines()[1:] == [
        "ILLUSTRATION",
        "A promises B a FIXTURE horse. A is bound.",
    ]
    # Running headers with page numbers and the footnote are not statute text.
    body = " ".join(s.text for s in split.sections)
    assert "Laws of Fixtureland ACT" not in body and "FIXTURE Agreements 5" not in body
    assert "editorial note" not in body
    assert secs["1"].notes[0].startswith("*NOTE—FIXTURE editorial note")  # the "*" marker
    assert split.stopped_at == "LIST OF AMENDMENTS"
    assert not [w for w in split.warnings if "accounting" in w or "not parsed" in w]


def test_numbered_lines_out_of_contents_order_stay_text():
    pages = _act_pages()
    pages[3].insert(5, "1. a FIXTURE list item inside section 2;")
    split = split_document(pages)
    secs = {s.number: s for s in split.sections}
    assert list(secs) == ["1", "2", "3", "4", "5"]
    assert "1. a FIXTURE list item inside section 2;" in secs["2"].text


def test_malay_layout_and_version_dates():
    pages = [
        ["UNDANG-UNDANG FIXTURELAND", "Akta 998", "AKTA FIXTURE (SARAAN) 2099",
         "Sebagaimana pada 1 Ogos 2015"],
        ["FIXTURE (Saraan) 2", "SUSUNAN SEKSYEN", "Seksyen", "1. Tajuk ringkas",
         "2. Tafsiran FIXTURE", "3. Saraan FIXTURE", "JADUAL PERTAMA"],
        ["FIXTURE (Saraan) 3", "Suatu Akta FIXTURE (bukan undang-undang).", "Tajuk ringkas",
         "1. Akta ini bolehlah dinamakan Akta FIXTURE 2099.", "Tafsiran FIXTURE",
         "2. Dalam Akta ini FIXTURE ertinya FIXTURE.", "Saraan FIXTURE",
         "3. Saraan FIXTURE hendaklah berupa elaun.", "Jadual ini terpakai bagi FIXTURE"],
        ["FIXTURE (Saraan) 4", "JADUAL PERTAMA", "1. Perenggan FIXTURE jadual."],
    ]  # fmt: skip
    split = split_document(pages)
    assert [s.number for s in split.sections] == ["1", "2", "3"]
    assert split.sections[2].text.endswith("Jadual ini terpakai bagi FIXTURE")  # not an end
    assert split.stopped_at == "JADUAL PERTAMA"
    assert version_date([ln for p in pages for ln in p]) == date(2015, 8, 1)
    assert version_date(["Incorporating all amendments up", "to 1 January 2006"]) == date(
        2006, 1, 1
    )
    assert version_date(["As at 1 July 2023"]) == date(2023, 7, 1)


def test_supplied_snapshot_without_url_is_parsed_and_reported(tmp_path):
    from travo_rag.sources.fetch import SnapshotStore

    store = SnapshotStore(tmp_path / "snaps")
    supplied = inst(id="SG/SUPPLIED", url=None)
    store.save(supplied, None, HTML, "text/html", origin="supplied", filename="act.html")
    m = manifest(supplied, inst(id="SG/NOURL", url=None))
    for fetch in (None, fetcher(site({}, robots=(404, ""))[0])):
        outcomes = {o.id: o for o in run(m, store, fetch)}
        assert outcomes["SG/SUPPLIED"].status == "parsed"
        assert outcomes["SG/SUPPLIED"].origin == "supplied"
        assert outcomes["SG/NOURL"].status == "needs_url"
        assert outcomes["SG/SUPPLIED"].units[0].source.official_url is None
    _, report, _ = write_outputs(list(outcomes.values()), "SG", tmp_path / "out")
    assert "supplied file `act.html`" in report.read_text()


def test_snapshots_are_never_overwritten(tmp_path):
    store = SnapshotStore(tmp_path)
    now = datetime(2026, 9, 30, tzinfo=UTC)
    a = store.save(inst(), "u", b"<p>a</p>", "text/html", now)
    b = store.save(inst(), "u", b"<p>b</p>", "text/html", now)
    assert a.path != b.path and a.read() == b"<p>a</p>"
    assert store.latest(inst()).sha256 == b.sha256


# ---------------------------------------------------------------- pipeline


def test_pipeline_fetch_then_offline_and_outputs(tmp_path):
    handler, calls = site({"/Act/FIXTURE2099": (200, HTML)}, robots=(404, ""))
    store = SnapshotStore(tmp_path / "snaps")
    m = manifest(
        inst(),
        inst(id="SG/NOURL", url=None),
        inst(id="SG/GONE", url="https://statutes.example.test/Act/GONE"),
    )
    outcomes = run(m, store, fetcher(handler))
    status = {o.id: o.status for o in outcomes}
    assert status == {
        "SG/FIXTURE2099": "parsed",
        "SG/NOURL": "needs_url",
        "SG/GONE": "fetch_failed",
    }
    jsonl, report, n = write_outputs(outcomes, "SG", tmp_path / "out")
    assert n == 4 and len(read_jsonl(jsonl)) == 4
    text = report.read_text()
    assert "needs_url" in text and "s 2A" in text and "Before running `legal-verify`" in text

    offline = run(m, store, None, only={"SG/FIXTURE2099"})
    assert [o.status for o in offline] == ["parsed"]
    assert calls.count("/Act/FIXTURE2099") == 1  # offline did not refetch


# ---------------------------------------------------------------- ingest + verification


def test_verification_lifecycle_and_verified_only_retrieval(tmp_path, client, make_tenant):
    from travo_api.cli import legal_verify
    from travo_api.db import get_admin_engine, tenant_session
    from travo_rag import retrieval

    store = SnapshotStore(tmp_path)
    i = inst(id="SG/VERIFYME")
    units = parse_snapshot(i, store.save(i, "https://x.test/a", HTML, "text/html"), "x").units
    with get_admin_engine().begin() as c:
        upsert_units(c, units)
    t = make_tenant()
    uid = "SG/VERIFYME#s 2A"
    from urllib.parse import quote

    info = client.get(f"/v1/legal-units/{quote(uid, safe='')}", headers=t.headers()).json()
    assert info["review_status"] == "unverified" and info["snapshot_sha256"]

    def found(require: bool) -> bool:
        with tenant_session(t.tenant_id) as s:
            hits = retrieval.search(
                s,
                "FIXTURE agreed sum genuine pre-estimate",
                jurisdictions=["SG"],
                as_of=date(2026, 9, 30),
                k=10,
                require_verified=require,
            )
        return any(h.id == uid for h in hits)

    assert found(False) and not found(True)
    assert legal_verify("SG/VERIFYME", "lawyer@lionpartners.test", "spot-checked s 1–3")
    assert found(True)
    assert (
        client.get(f"/v1/legal-units/{quote(uid, safe='')}", headers=t.headers()).json()[
            "review_status"
        ]
        == "verified"
    )

    # Same snapshot re-ingested: stays verified. New snapshot: needs a fresh check.
    with get_admin_engine().begin() as c:
        upsert_units(c, units)
    assert found(True)
    changed = parse_snapshot(
        i, store.save(i, "https://x.test/a", HTML + b"<!-- v2 -->", "text/html"), "x"
    ).units
    with get_admin_engine().begin() as c:
        upsert_units(c, changed)
    assert not found(True)
    assert not legal_verify("SG/NOPE", "x@y.test", None)
    assert dump_jsonl(units)  # serialisable for the ingestion hand-off
