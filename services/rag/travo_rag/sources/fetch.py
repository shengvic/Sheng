"""Polite fetching of official pages with raw snapshots and provenance.

- Identifies itself (User-Agent with a contact), honours robots.txt (unreachable robots.txt or
  5xx → treated as disallow), waits at least `min_interval` seconds between requests per host,
  retries transient failures with backoff, and caps response size.
- Every successful download is stored as an immutable snapshot with `meta.json`, so parsing can
  happen later, elsewhere, and be re-run without re-fetching.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.robotparser
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from travo_rag.sources.manifest import Instrument

EXT = {"sso_html": "html", "pdf": "pdf", "text": "txt"}


class FetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class Snapshot:
    path: Path
    url: str | None  # None for a supplied file with no known official URL
    sha256: str
    retrieved_at: datetime
    content_type: str
    origin: str = "fetched"  # fetched | supplied (a file given to us, e.g. a PDF from AGC)
    filename: str | None = None  # original name of a supplied file

    def read(self) -> bytes:
        return self.path.read_bytes()


class PoliteFetcher:
    def __init__(
        self,
        client: httpx.Client,
        *,
        user_agent: str,
        min_interval: float = 2.0,
        retries: int = 3,
        max_bytes: int = 30 * 1024 * 1024,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.client = client
        self.user_agent = user_agent
        self.min_interval = min_interval
        self.retries = retries
        self.max_bytes = max_bytes
        self._clock = clock
        self._sleep = sleep
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _wait(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            gap = self._clock() - last
            if gap < self.min_interval:
                self._sleep(self.min_interval - gap)
        self._last[host] = self._clock()

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            self._wait(parts.netloc)
            rp: urllib.robotparser.RobotFileParser | None = urllib.robotparser.RobotFileParser()
            try:
                r = self.client.get(f"{origin}/robots.txt", headers={"User-Agent": self.user_agent})
                if r.status_code >= 500:
                    rp = None  # can't tell → don't crawl
                elif r.status_code >= 400:
                    assert rp is not None
                    rp.parse([])  # no robots.txt → allowed
                else:
                    assert rp is not None
                    rp.parse(r.text.splitlines())
            except httpx.HTTPError:
                rp = None
            self._robots[origin] = rp
        rp = self._robots[origin]
        return rp is not None and rp.can_fetch(self.user_agent, url)

    def get(self, url: str) -> tuple[bytes, str]:
        if not self.allowed(url):
            raise FetchError(f"robots.txt disallows or is unavailable for {url}")
        host = urlsplit(url).netloc
        delay = 2.0
        for attempt in range(1, self.retries + 1):
            self._wait(host)
            try:
                r = self.client.get(
                    url, headers={"User-Agent": self.user_agent}, follow_redirects=True
                )
            except httpx.HTTPError as exc:
                err = f"{type(exc).__name__}"
            else:
                if r.status_code == 200:
                    if len(r.content) > self.max_bytes:
                        raise FetchError(f"{url}: response larger than {self.max_bytes} bytes")
                    return r.content, r.headers.get("content-type", "")
                if r.status_code < 500 and r.status_code != 429:
                    raise FetchError(f"{url}: HTTP {r.status_code}")
                err = f"HTTP {r.status_code}"
            if attempt < self.retries:
                self._sleep(delay)
                delay *= 2
        raise FetchError(f"{url}: gave up after {self.retries} attempts ({err})")


def _stamp_order(meta: Path) -> tuple[str, int]:
    """`20260930T043803Z-2.meta.json` → ("20260930T043803Z", 2): same-second saves sort after."""
    base, _, n = meta.name.removesuffix(".meta.json").partition("-")
    return base, int(n or 0)


class SnapshotStore:
    """`<root>/<JUR>_<name>/<timestamp>.<ext>` + `<timestamp>.meta.json`. Never overwritten."""

    def __init__(self, root: Path):
        self.root = root

    def _dir(self, inst: Instrument) -> Path:
        return self.root / inst.id.replace("/", "_")

    def save(
        self,
        inst: Instrument,
        url: str | None,
        content: bytes,
        content_type: str,
        now: datetime | None = None,
        *,
        origin: str = "fetched",
        filename: str | None = None,
    ) -> Snapshot:
        now = now or datetime.now(UTC)
        d = self._dir(inst)
        d.mkdir(parents=True, exist_ok=True)
        base = now.strftime("%Y%m%dT%H%M%SZ")
        stamp, n = base, 1
        while (d / f"{stamp}.meta.json").exists():  # never overwrite a snapshot
            stamp, n = f"{base}-{n}", n + 1
        path = d / f"{stamp}.{EXT[inst.format]}"
        sha = hashlib.sha256(content).hexdigest()
        path.write_bytes(content)
        (d / f"{stamp}.meta.json").write_text(
            json.dumps(
                {
                    "instrument": inst.id,
                    "url": url,
                    "sha256": sha,
                    "bytes": len(content),
                    "content_type": content_type,
                    "retrieved_at": now.isoformat(),
                    "origin": origin,
                    "filename": filename,
                },
                indent=2,
            )
        )
        return Snapshot(path, url, sha, now, content_type, origin, filename)

    def latest(self, inst: Instrument) -> Snapshot | None:
        d = self._dir(inst)
        metas = sorted(d.glob("*.meta.json"), key=_stamp_order) if d.exists() else []
        if not metas:
            return None
        meta = json.loads(metas[-1].read_text())
        path = metas[-1].with_name(metas[-1].name.replace(".meta.json", f".{EXT[inst.format]}"))
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
            raise FetchError(f"snapshot for {inst.id} is missing or altered: {path}")
        return Snapshot(
            path,
            meta["url"],
            meta["sha256"],
            datetime.fromisoformat(meta["retrieved_at"]),
            meta["content_type"],
            meta.get("origin", "fetched"),
            meta.get("filename"),
        )
