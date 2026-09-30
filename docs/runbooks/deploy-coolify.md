# Runbook — Deploy the Travo pilot on Coolify (Contabo VPS)

> **Status:** Draft v1 · **Last updated:** 2026-09-30 · **Related:** ADR-018, ADR-019, ADR-022, [14 §6, §12](../14-vietnam-launch-plan.md)

The VPS already runs Coolify. Travo is deployed as one **Docker Compose** application:

| Service | Image | Exposure |
|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | Private network only |
| `api` | `deploy/Dockerfile.api` — runs `travo migrate`, then uvicorn | Private (reached by `web`) |
| `worker` | Same image, `travo worker` | None |
| `web` | `deploy/Dockerfile.web` — Next.js standalone, port 3000 | **The only public service** (domain + TLS via Coolify) |

## 1. Pre-release checks (on a dev machine)
```
make check web-check e2e
make deploy-smoke          # builds both images, runs the Coolify compose stack + mock IdP
```
`deploy-smoke` runs the real compose file with test-only overrides (`deploy/smoke.override.yml`)
and checks the following:
- migrations run and the app role is created;
- pages carry the CSP nonce;
- writes without the CSRF header are refused;
- invalid sessions are rejected;
- SSO sign-in works (auth code + PKCE);
- matter → upload → review is completed by the separate worker container;
- the UI defaults to Vietnamese;
- a bilingual VI | EN NDA is reviewed with `nda_vn` and yields VI–EN discrepancy findings.

Also run `make eval`: it fails if the Vietnam pilot gates are not met (docs/11 §3).

## 2. First deployment
1. **Server basics**, if not already done:
   - SSH with keys only; firewall allows only 22/80/443.
   - Unattended security upgrades.
   - Coolify dashboard behind 2FA, and an IP allowlist where possible.
2. **Coolify → New resource → Docker Compose** from the Git repository.
   - Base directory `/`, compose file `/deploy/docker-compose.coolify.yml`.
   - Connect the repository with a deploy key or the Coolify GitHub App (read-only).
3. **Environment variables:** use `deploy/.env.example` as the list, and generate each secret
   separately.
   - `POSTGRES_PASSWORD` and `TRAVO_APP_DB_PASSWORD`: `openssl rand -hex 24`. Hex keeps the
     database URLs valid.
   - `TRAVO_MASTER_KEY`: `openssl rand -base64 32`. **Store a copy offline (password manager).
     Losing it makes every stored document unreadable.**
   - `TRAVO_JWT_SECRET`: `openssl rand -hex 32`.
   - `TRAVO_PUBLIC_URL`: the https origin, e.g. `https://app.example.vn`.
   - Model keys (`TRAVO_OPENROUTER_API_KEY`, …): set only for providers whose terms have been
     checked (no training; zero-retention where available).
4. **Domain:** assign the domain to the `web` service on port 3000. Coolify issues the TLS
   certificate. Do not assign a domain to `api` or `postgres`.
5. **Deploy.** The API refuses to start if production settings are unsafe:
   - dev tokens on;
   - inline reviews on;
   - `TRAVO_REQUIRE_VERIFIED_SOURCES` not true;
   - a bad master key or a short JWT secret;
   - default database passwords.

   The logs name the setting at fault.
6. **Legal index and first firm** (Coolify → `api` → Terminal):
   ```
   python -m travo_api.cli legal-fetch -j VN --out /data/legal       # then read /data/legal/vn-review.md
   python -m travo_api.cli ingest-legal /data/legal/vn.jsonl
   python -m travo_api.cli legal-verify VN/BLDS2015 --by lawyer@firm.vn --note "…"
   python -m travo_api.cli bootstrap-tenant "Firm name" admin@firm.vn
   python -m travo_api.cli configure-idp <tenant_id> https://login.microsoftonline.com/<tid>/v2.0 <client_id> \
       --client-secret <secret> --domain firm.vn
   ```
   The identity provider must use https in production. Register the redirect URI
   `https://<domain>/auth/callback` with the firm's IdP.

## 3. Backups (required before the first client document)
1. Copy `deploy/backup.sh` into the `backups` volume once:
   `docker cp deploy/backup.sh <postgres-container>:/backups/backup.sh`.
2. Coolify → Scheduled Tasks → container `postgres`, command `sh /backups/backup.sh`, daily at
   02:00 (UTC+7 → set the cron in UTC). The task writes a database dump and a documents archive
   and keeps 14 days.
3. **Off-site copy, encrypted:** on the host, an `rclone` **crypt** remote over S3-compatible
   storage (e.g. Contabo Object Storage or Backblaze B2). A cron job then syncs the `backups`
   volume directory there nightly. Keep the rclone crypt password with the master key.
4. **Restore drill** before go-live and quarterly:
   - Restore the latest dump into a scratch database with `pg_restore -d …` and untar the
     documents.
   - Start a copy of the stack against it and open a stored document. It must decrypt with the
     master key.

## 4. Updates and rollback
- **Update:** merge to the deploy branch, then Coolify → Redeploy. Migrations run automatically
  and are forward-only. Take a manual backup first (`sh /backups/backup.sh`).
- **Rollback:** redeploy the previous commit. If a migration must be undone, restore the
  pre-update dump. Alembic downgrades are not maintained.

## 5. Pilot guardrails (ADR-022)
- Data is processed outside Vietnam (VPS location and model APIs). Before a firm uploads real
  client documents:
  - a pilot agreement + DPA must be signed;
  - a cross-border transfer dossier must be prepared.
- Until then, use low-sensitivity or anonymised documents.
- Never set `TRAVO_OIDC_ALLOW_HTTP`, `TRAVO_INSECURE_COOKIES` or `TRAVO_DEV_LOGIN` on the VPS.
  They exist for local smoke tests only.
- Still open before paid launch: rate limiting on sign-in endpoints, SCIM, an external pen test.
