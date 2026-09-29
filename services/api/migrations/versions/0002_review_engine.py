"""Review engine: durable runs, playbooks, findings, citations, telemetry, exports, legal index.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"

TENANT_TABLES = [
    "playbooks",
    "review_runs",
    "review_steps",
    "findings",
    "citations",
    "telemetry_events",
    "exports",
]

SCHEMA = """
-- Shared public-law index (no tenant data). Read-only for the app; loaded by the owner CLI.
CREATE TABLE legal_sources (
  id varchar(160) PRIMARY KEY,
  jurisdiction varchar(8) NOT NULL,
  instrument_type varchar(40) NOT NULL,
  number varchar(80),
  title text NOT NULL,
  issuing_body text,
  language varchar(8) NOT NULL DEFAULT 'en',
  official_url text,
  is_fixture boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE legal_units (
  id varchar(240) PRIMARY KEY,
  source_id varchar(160) NOT NULL REFERENCES legal_sources(id),
  unit_path varchar(160) NOT NULL,
  heading text NOT NULL DEFAULT '',
  text text NOT NULL,
  effective_from date,
  effective_to date,
  status varchar(16) NOT NULL DEFAULT 'in_force'
    CHECK (status IN ('in_force','amended','repealed')),
  version_hash varchar(64) NOT NULL,
  tsv tsvector GENERATED ALWAYS AS
    (to_tsvector('simple', coalesce(heading,'') || ' ' || text)) STORED,
  UNIQUE (source_id, unit_path)
);
CREATE INDEX legal_units_tsv ON legal_units USING gin (tsv);

CREATE TABLE playbooks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  key varchar(80) NOT NULL,
  version integer NOT NULL,
  name varchar(200) NOT NULL,
  contract_types varchar(32)[] NOT NULL DEFAULT '{}',
  governing_laws varchar(8)[] NOT NULL DEFAULT '{}',
  spec jsonb NOT NULL,
  status varchar(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active','draft','retired')),
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, key, version),
  FOREIGN KEY (created_by, tenant_id) REFERENCES users(id, tenant_id)
);

CREATE TABLE review_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  matter_id uuid NOT NULL,
  document_id uuid NOT NULL,
  playbook_key varchar(80) NOT NULL,
  playbook_version integer NOT NULL,
  playbook_source varchar(10) NOT NULL CHECK (playbook_source IN ('tenant','starter')),
  playbook_spec jsonb NOT NULL,
  status varchar(16) NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued','running','completed','failed')),
  initiated_by uuid NOT NULL,
  lease_owner varchar(80),
  lease_expires timestamptz,
  not_before timestamptz NOT NULL DEFAULT now(),
  attempts integer NOT NULL DEFAULT 0,
  error text,
  cost_usd numeric(12,6) NOT NULL DEFAULT 0,
  summary jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  finished_at timestamptz,
  UNIQUE (id, tenant_id),
  FOREIGN KEY (matter_id, tenant_id) REFERENCES matters(id, tenant_id),
  FOREIGN KEY (document_id, tenant_id) REFERENCES documents(id, tenant_id),
  FOREIGN KEY (initiated_by, tenant_id) REFERENCES users(id, tenant_id)
);
CREATE INDEX review_runs_claim ON review_runs (status, not_before, created_at);

CREATE TABLE review_steps (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  run_id uuid NOT NULL,
  idx integer NOT NULL,
  name varchar(32) NOT NULL,
  status varchar(16) NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','completed','failed')),
  output jsonb NOT NULL DEFAULT '{}',
  attempts integer NOT NULL DEFAULT 0,
  error text,
  started_at timestamptz,
  finished_at timestamptz,
  UNIQUE (run_id, name),
  FOREIGN KEY (run_id, tenant_id) REFERENCES review_runs(id, tenant_id)
);

CREATE TABLE findings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  matter_id uuid NOT NULL,
  run_id uuid NOT NULL,
  clause_id uuid,
  clause_key varchar(64) NOT NULL,
  rule_key varchar(80) NOT NULL,
  kind varchar(10) NOT NULL CHECK (kind IN ('playbook','law')),
  classification varchar(16) NOT NULL
    CHECK (classification IN ('standard','fallback','non_standard','missing','legal_note')),
  severity varchar(8) NOT NULL CHECK (severity IN ('high','medium','low','info')),
  summary text NOT NULL,
  rationale text NOT NULL DEFAULT '',
  suggested_redline text,
  confidence double precision NOT NULL,
  model_tier varchar(4),
  escalated boolean NOT NULL DEFAULT false,
  status varchar(16) NOT NULL DEFAULT 'needs_review'
    CHECK (status IN ('needs_review','needs_human')),
  disposition varchar(10) CHECK (disposition IN ('accepted','edited','rejected','deferred')),
  edited_text text,
  reason_code varchar(40),
  note text,
  disposition_by uuid,
  disposition_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, tenant_id),
  FOREIGN KEY (run_id, tenant_id) REFERENCES review_runs(id, tenant_id),
  FOREIGN KEY (matter_id, tenant_id) REFERENCES matters(id, tenant_id)
);
CREATE INDEX findings_run ON findings (run_id);
CREATE INDEX findings_clause_key ON findings (tenant_id, clause_key, disposition);

CREATE TABLE citations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  matter_id uuid NOT NULL,
  finding_id uuid NOT NULL,
  claim_text text NOT NULL,
  source_unit_id varchar(240),
  pinpoint text,
  status varchar(16) NOT NULL CHECK (status IN
    ('supported','partial','contradicted','not_found','uncited','invalid_source',
     'not_in_force','misquoted')),
  score double precision NOT NULL DEFAULT 0,
  checker varchar(128) NOT NULL,
  override_reason text,
  overridden_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (finding_id, tenant_id) REFERENCES findings(id, tenant_id)
);
CREATE INDEX citations_finding ON citations (finding_id);

CREATE TABLE telemetry_events (
  id bigserial PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  matter_id uuid,
  event_type varchar(48) NOT NULL,
  actor_id uuid,
  subject_id varchar(64),
  payload jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX telemetry_events_type ON telemetry_events (tenant_id, event_type, created_at);
CREATE TRIGGER telemetry_events_append_only BEFORE UPDATE OR DELETE ON telemetry_events
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

CREATE TABLE exports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  matter_id uuid NOT NULL,
  run_id uuid NOT NULL,
  format varchar(16) NOT NULL CHECK (format IN ('redline_docx','memo_docx')),
  filename varchar(300) NOT NULL,
  storage_ref varchar(300) NOT NULL,
  sha256 varchar(64) NOT NULL,
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (run_id, tenant_id) REFERENCES review_runs(id, tenant_id)
);

GRANT SELECT ON legal_sources, legal_units TO travo_app;
GRANT SELECT, INSERT, UPDATE ON playbooks, review_runs, review_steps, findings, citations,
  exports TO travo_app;
GRANT SELECT, INSERT ON telemetry_events TO travo_app;
GRANT USAGE ON SEQUENCE telemetry_events_id_seq TO travo_app;

-- Workers claim runs across tenants through this one function; it returns only ids, and all
-- further work happens in a tenant-scoped session where RLS applies (ADR-013).
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'travo_claimer') THEN
    CREATE ROLE travo_claimer NOLOGIN BYPASSRLS;
  END IF;
END $$;
GRANT USAGE ON SCHEMA public TO travo_claimer;
GRANT SELECT, UPDATE ON review_runs TO travo_claimer;

CREATE FUNCTION claim_review_run(p_worker text, p_lease_seconds integer, p_max_attempts integer)
RETURNS TABLE (run_id uuid, tenant_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  RETURN QUERY
  UPDATE review_runs r
     SET status = 'running',
         lease_owner = p_worker,
         lease_expires = now() + make_interval(secs => p_lease_seconds),
         attempts = r.attempts + 1,
         started_at = coalesce(r.started_at, now())
   WHERE r.id = (
     SELECT q.id FROM review_runs q
      WHERE q.attempts < p_max_attempts
        AND q.not_before <= now()
        AND (q.status = 'queued' OR (q.status = 'running' AND q.lease_expires < now()))
      ORDER BY q.created_at
      FOR UPDATE SKIP LOCKED
      LIMIT 1)
  RETURNING r.id, r.tenant_id;
END $$;
ALTER FUNCTION claim_review_run(text, integer, integer) OWNER TO travo_claimer;
REVOKE ALL ON FUNCTION claim_review_run(text, integer, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION claim_review_run(text, integer, integer) TO travo_app;
"""


def upgrade() -> None:
    op.execute(SCHEMA)
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
            "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
        )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS claim_review_run(text, integer, integer)")
    for table in [*reversed(TENANT_TABLES), "legal_units", "legal_sources"]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
