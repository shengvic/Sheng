# Runbook — Ingesting official SG/MY statutes

> **Status:** Draft v1 · **Last updated:** 2026-09-30 · **Related:** [04 §9](../04-legal-rag-and-citation-validation.md), ADR-014, ADR-019, [13 Q11](../13-open-questions.md)

Run this on a machine that can reach the official portals (Singapore Statutes Online,
AGC Malaysia). The dev container used to build Travo could not reach them.

## 0. Before the first run
- Confirm the portals' terms of use permit this use (Q11). Keep snapshots private.
- Check each instrument in `config/legal_sources/sg.yaml` and `my.yaml` against the portal:
  - the title and number;
  - the URL. Every MY entry is `url: null` until someone fills in the official PDF link from
    the AGC site. Do not use third-party mirrors.
  - `expect_title`: text that must appear on the real page.
- Set a contact for the User-Agent: `export TRAVO_FETCH_CONTACT=legal-eng@yourfirm.example`.

## 1. Fetch and parse
```
make legal-fetch JUR=SG          # or JUR=MY, or omit for all
```
- This writes raw snapshots to `.data/legal_snapshots/` (or `TRAVO_LEGAL_SNAPSHOT_DIR`).
- It writes `out/legal/SG.jsonl` and `out/legal/SG-review.md`.
- Each instrument ends in one of these statuses:
  - `parsed`
  - `needs_url`: fill in the manifest.
  - `fetch_failed`: robots.txt disallows the page, an HTTP error, or the file is too large.
  - `parse_failed`: the title is not found, or too few sections were parsed.
- To re-parse without downloading again (for example after a parser fix), run
  `make legal-fetch JUR=SG OFFLINE=1`.

## 2. Check the review report (legal engineer)
Open `out/legal/SG-review.md`. For each parsed instrument:
- Compare the section count with the portal's table of contents.
- Open the official URL and compare the sample sections word for word, including the
  heading, the subsection labels (1), (2), (a), and where each section ends.
- Read the warnings: duplicates, and a missing "as at" date, which means the units get no
  `effective_from`.
- If a parse is wrong, fix the parser or the manifest (never the text) and re-run offline.

## 3. Ingest (unverified)
```
make ingest-legal FILE=out/legal/SG.jsonl
```
Sources arrive `unverified`. The sources drawer labels them "Not yet checked by a lawyer".

## 4. Lawyer verification
A qualified lawyer for that jurisdiction does the following for each source:
1. Spot-checks the sections in the app (sources drawer) against the official portal:
   - at least the sections the jurisdiction pack queries;
   - plus a random sample.
2. Records the check:
```
uv run python -m travo_api.cli legal-verify SG/UCTA1977 --by lawyer@firm.sg --note "ss 1-13 checked vs SSO 2026-10-01"
```
Re-ingesting a source whose snapshot changed resets it to `unverified`. Repeat steps 2–4.

## 5. Turn on the gate
In every pilot and production deployment, set `TRAVO_REQUIRE_VERIFIED_SOURCES=true`. Law
checks then cite only verified sources. With no verified source, a finding goes to a lawyer
(`no_sources`).

## Refresh
Re-run monthly or when the portal shows a new version date. A byte-identical download keeps the same
sha256 and stays verified. Any change to the downloaded file resets the source to `unverified`
for re-check. That includes page-chrome changes on HTML pages, so expect some re-checks that
only need a quick diff.
