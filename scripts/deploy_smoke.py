"""Smoke-test the Coolify compose stack locally before a release (ADR-022).

Starts deploy/docker-compose.coolify.yml + deploy/smoke.override.yml (mock IdP, published ports)
from prebuilt images, then checks, as a browser would through the web BFF:
- migrations ran and the API serves as the non-owner role (`/healthz`, sign-in works under RLS);
- CSP nonce header on pages; writes without the CSRF header are refused;
- SSO sign-in (auth code + PKCE) against the mock IdP;
- matter → upload → review, processed by the separate worker container;
- the Vietnam pilot defaults: Vietnamese UI, and a bilingual VI | EN contract reviewed with the
  VN starter playbook and VI–EN discrepancy findings.

    API_IMAGE=travo-api:smoke WEB_IMAGE=travo-web:smoke uv run python scripts/deploy_smoke.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx

ROOT = Path(__file__).resolve().parents[1]
WEB = "http://localhost:3000"
ENV = {
    **os.environ,
    "POSTGRES_PASSWORD": "smoke" + "a1" * 12,
    "TRAVO_APP_DB_PASSWORD": "smokeapp" + "b2" * 12,
    "TRAVO_MASTER_KEY": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",  # test-only key
    "TRAVO_JWT_SECRET": "smoke-jwt-" + "c3" * 20,
    "TRAVO_PUBLIC_URL": WEB,
    "COMPOSE_PROJECT_NAME": "travo-smoke",
}
COMPOSE = [
    "docker", "compose",
    "-f", str(ROOT / "deploy/docker-compose.coolify.yml"),
    "-f", str(ROOT / "deploy/smoke.override.yml"),
]  # fmt: skip


def sh(*args: str, check: bool = True) -> str:
    out = subprocess.run(  # noqa: S603 — fixed docker compose argv
        [*COMPOSE, *args], env=ENV, capture_output=True, text=True, check=False, cwd=ROOT
    )
    if check and out.returncode:
        raise SystemExit(f"{' '.join(args)} failed:\n{out.stdout}\n{out.stderr}")
    return out.stdout


def cli(*args: str) -> str:
    return sh("exec", "-T", "api", "python", "-m", "travo_api.cli", *args).strip()


def browser_get(client: httpx.Client, url: str) -> httpx.Response:
    """Follow redirects like a browser; `idp:8791` (the IdP's in-network name) → localhost."""
    for _ in range(10):
        parts = urlsplit(url)
        if parts.hostname == "idp":
            url = urlunsplit(parts._replace(netloc=f"localhost:{parts.port}"))
        r = client.get(url)
        if r.status_code not in (301, 302, 303, 307, 308):
            return r
        url = str(httpx.URL(url).join(r.headers["location"]))
    raise AssertionError("too many redirects")


def main() -> None:
    sh("up", "-d", "--no-build", "--wait")
    try:
        run_checks()
    except BaseException:
        print(sh("logs", "--tail", "80", check=False))
        raise
    finally:
        if "--keep" not in sys.argv:
            sh("down", "-v", check=False)
    print("deploy smoke test passed")


def review(
    c: httpx.Client, write: dict[str, str], matter_id: str, name: str, data: bytes, **opts: str
) -> tuple[dict, dict, list[dict]]:
    """Upload, start a review, wait for the worker; return (document, run, findings)."""
    doc = (
        c.post(
            f"{WEB}/api/v1/matters/{matter_id}/documents",
            files={"file": (name, data)},
            headers=write,
        )
        .raise_for_status()
        .json()
    )
    run = (
        c.post(f"{WEB}/api/v1/documents/{doc['id']}/reviews", json=opts, headers=write)
        .raise_for_status()
        .json()
    )
    for _ in range(90):
        run = c.get(f"{WEB}/api/v1/reviews/{run['id']}").raise_for_status().json()
        if run["status"] in ("completed", "failed", "needs_human"):
            break
        time.sleep(1)
    assert run["status"] == "completed", (name, run["status"], run.get("error"))
    findings = c.get(f"{WEB}/api/v1/reviews/{run['id']}/findings").raise_for_status().json()
    return doc, run, findings


def run_checks() -> None:
    page = httpx.get(f"{WEB}/login")
    assert page.status_code == 200, page.status_code
    assert "nonce-" in page.headers.get("content-security-policy", ""), "missing CSP nonce"
    assert '<html lang="vi"' in page.text, "the pilot UI should default to Vietnamese"

    tenant = cli("bootstrap-tenant", "Smoke Firm", "admin@smoke.test")
    tid = next(ln.split("=", 1)[1] for ln in tenant.splitlines() if ln.startswith("tenant_id="))
    cli(
        "configure-idp", tid, "http://idp:8791", "travo-web",
        "--client-secret", "smoke-secret", "--domain", "smoke.test",
    )  # fmt: skip
    # Dev tokens must be refused in production.
    denied = httpx.get(f"{WEB}/api/v1/me", headers={"cookie": "travo_session=not-a-session"})
    assert denied.status_code == 401, denied.status_code

    with httpx.Client(follow_redirects=False, timeout=30) as c:
        landing = browser_get(c, f"{WEB}/auth/login?email=admin@smoke.test")
        assert landing.status_code == 200, (landing.status_code, landing.url)
        assert "travo_session" in c.cookies, "no session cookie after SSO"
        me = c.get(f"{WEB}/api/v1/me").raise_for_status().json()
        assert me["email"] == "admin@smoke.test", me

        write = {"x-travo-csrf": "1", "origin": WEB}
        assert c.post(f"{WEB}/api/v1/matters", json={}).status_code == 403  # no CSRF header
        matter = (
            c.post(
                f"{WEB}/api/v1/matters",
                json={"number": "SMOKE-1", "name": "Smoke NDA", "jurisdictions": ["SG"]},
                headers=write,
            )
            .raise_for_status()
            .json()
        )
        nda = ROOT / "evals/gold/nda/sg_mutual_nda.docx"
        _, _, findings = review(c, write, matter["id"], nda.name, nda.read_bytes())
        assert findings, "review produced no findings"
        print(f"review completed by the worker with {len(findings)} findings")

        sys.path.insert(0, str(ROOT))
        from evals import vn_fixtures  # synthetic FIXTURE contract, never client data

        vn_matter = (
            c.post(
                f"{WEB}/api/v1/matters",
                json={"number": "SMOKE-VN", "name": "Thỏa thuận bảo mật", "jurisdictions": ["VN"]},
                headers=write,
            )
            .raise_for_status()
            .json()
        )
        data = vn_fixtures.table_docx(vn_fixtures.seeded_clauses())
        doc, run, findings = review(
            c, write, vn_matter["id"], "nda_vi_en.docx", data, output_language="vi"
        )
        assert doc["bilingual_layout"] == "table", doc["bilingual_layout"]
        assert run["playbook_key"] == "nda_vn", run["playbook_key"]
        bilingual = [f for f in findings if f["kind"] == "bilingual"]
        assert len(bilingual) >= len(vn_fixtures.SEEDED), [f["summary"] for f in bilingual]
        print(f"VN bilingual review: {len(findings)} findings, {len(bilingual)} VI–EN mismatches")


if __name__ == "__main__":
    main()
