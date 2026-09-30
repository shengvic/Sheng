"""Run the manifest: fetch (or reuse snapshots) → parse → JSONL + review report."""

from __future__ import annotations

from pathlib import Path

from travo_rag.legal_index import UnitIn, dump_jsonl
from travo_rag.sources.fetch import FetchError, PoliteFetcher, SnapshotStore
from travo_rag.sources.manifest import Manifest
from travo_rag.sources.parsers import ParseError, parse_snapshot
from travo_rag.sources.report import InstrumentOutcome, render


def run(
    manifest: Manifest,
    store: SnapshotStore,
    fetcher: PoliteFetcher | None,
    *,
    only: set[str] | None = None,
) -> list[InstrumentOutcome]:
    """`fetcher=None` = offline: parse the latest stored snapshot of each instrument."""
    outcomes: list[InstrumentOutcome] = []
    for inst in manifest.instruments:
        if only and inst.id not in only:
            continue
        out = InstrumentOutcome(id=inst.id, title=inst.title, status="skipped", url=inst.url)
        outcomes.append(out)
        try:
            if fetcher is not None:
                if not inst.url:
                    out.status, out.detail = "needs_url", "no official URL in the manifest"
                    continue
                content, ctype = fetcher.get(inst.url)
                snap = store.save(inst, inst.url, content, ctype)
            else:
                latest = store.latest(inst)
                if latest is None:
                    out.status = "needs_url" if not inst.url else "skipped"
                    out.detail = "no snapshot yet (run without --offline on a machine with access)"
                    continue
                snap = latest
            result = parse_snapshot(inst, snap, manifest.issuing_body)
        except FetchError as exc:
            out.status, out.detail = "fetch_failed", str(exc)
            continue
        except ParseError as exc:
            out.status, out.detail = "parse_failed", str(exc)
            continue
        out.status, out.url, out.sha256 = "parsed", snap.url, snap.sha256
        out.units, out.warnings = result.units, result.warnings
    return outcomes


def write_outputs(
    outcomes: list[InstrumentOutcome], jurisdiction: str, out_dir: Path
) -> tuple[Path, Path, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    units: list[UnitIn] = [u for o in outcomes for u in o.units]
    jsonl = out_dir / f"{jurisdiction.lower()}.jsonl"
    report = out_dir / f"{jurisdiction.lower()}-review.md"
    jsonl.write_text(dump_jsonl(units) + ("\n" if units else ""), encoding="utf-8")
    report.write_text(render(outcomes, jurisdiction), encoding="utf-8")
    return jsonl, report, len(units)
