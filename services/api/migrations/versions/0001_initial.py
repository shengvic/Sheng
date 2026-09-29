"""Initial schema: tenancy, matters, walls, documents, routing, audit — with RLS.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None

TENANT_TABLES = [
    "users",
    "clients",
    "matters",
    "matter_members",
    "documents",
    "clauses",
    "model_policies",
    "provider_credentials",
    "routing_decisions",
    "audit_events",
]

SCHEMA = """
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'travo_app') THEN
    CREATE ROLE travo_app NOLOGIN NOSUPERUSER NOBYPASSRLS;
  END IF;
END $$;

CREATE TABLE tenants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(200) NOT NULL,
  region_cell varchar(8) NOT NULL,
  wrapped_dek bytea NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  email varchar(320) NOT NULL,
  name varchar(200) NOT NULL,
  role varchar(20) NOT NULL CHECK (role IN ('partner','associate','km','admin')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, email),
  UNIQUE (id, tenant_id)
);

CREATE TABLE clients (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  name varchar(200) NOT NULL,
  ai_policy jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, tenant_id)
);

CREATE TABLE matters (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  client_id uuid,
  number varchar(64) NOT NULL,
  name varchar(300) NOT NULL,
  jurisdictions varchar(8)[] NOT NULL DEFAULT '{}',
  residency varchar(8),
  deny_providers varchar(64)[] NOT NULL DEFAULT '{}',
  allow_providers varchar(64)[],
  budget_usd numeric(12,2),
  status varchar(20) NOT NULL DEFAULT 'open',
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, number),
  UNIQUE (id, tenant_id),
  FOREIGN KEY (client_id, tenant_id) REFERENCES clients(id, tenant_id),
  FOREIGN KEY (created_by, tenant_id) REFERENCES users(id, tenant_id)
);

CREATE TABLE matter_members (
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  matter_id uuid NOT NULL,
  user_id uuid NOT NULL,
  access varchar(10) NOT NULL CHECK (access IN ('member','screened')),
  PRIMARY KEY (matter_id, user_id),
  FOREIGN KEY (matter_id, tenant_id) REFERENCES matters(id, tenant_id),
  FOREIGN KEY (user_id, tenant_id) REFERENCES users(id, tenant_id)
);

CREATE TABLE documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  matter_id uuid NOT NULL,
  filename varchar(300) NOT NULL,
  mime varchar(120) NOT NULL,
  size_bytes bigint NOT NULL,
  sha256 varchar(64) NOT NULL,
  storage_ref varchar(300) NOT NULL,
  languages varchar(8)[] NOT NULL DEFAULT '{}',
  contract_type varchar(32),
  contract_type_confidence double precision,
  governing_law varchar(8),
  parties jsonb NOT NULL DEFAULT '[]',
  parse_status varchar(20) NOT NULL DEFAULT 'uploaded',
  error text,
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, tenant_id),
  FOREIGN KEY (matter_id, tenant_id) REFERENCES matters(id, tenant_id),
  FOREIGN KEY (created_by, tenant_id) REFERENCES users(id, tenant_id)
);

CREATE TABLE clauses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  matter_id uuid NOT NULL,
  document_id uuid NOT NULL,
  idx integer NOT NULL,
  number varchar(32),
  heading text NOT NULL,
  text text NOT NULL,
  taxonomy_key varchar(64) NOT NULL,
  confidence double precision NOT NULL,
  UNIQUE (document_id, idx),
  FOREIGN KEY (matter_id, tenant_id) REFERENCES matters(id, tenant_id),
  FOREIGN KEY (document_id, tenant_id) REFERENCES documents(id, tenant_id)
);

CREATE TABLE model_policies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  version integer NOT NULL,
  yaml text NOT NULL,
  active boolean NOT NULL DEFAULT true,
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, version),
  FOREIGN KEY (created_by, tenant_id) REFERENCES users(id, tenant_id)
);
CREATE UNIQUE INDEX model_policies_one_active ON model_policies (tenant_id) WHERE active;

CREATE TABLE provider_credentials (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  provider varchar(64) NOT NULL,
  ciphertext bytea NOT NULL,
  last4 varchar(4) NOT NULL,
  status varchar(16) NOT NULL DEFAULT 'active',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, provider)
);

CREATE TABLE routing_decisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  matter_id uuid,
  document_id uuid,
  task_type varchar(32) NOT NULL,
  descriptor jsonb NOT NULL,
  candidates jsonb NOT NULL,
  filtered jsonb NOT NULL,
  attempts jsonb NOT NULL,
  chosen_endpoint varchar(128),
  chosen_tier varchar(4),
  outcome varchar(32) NOT NULL,
  tokens_in integer NOT NULL DEFAULT 0,
  tokens_out integer NOT NULL DEFAULT 0,
  cost_usd numeric(12,6) NOT NULL DEFAULT 0,
  latency_ms integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX routing_decisions_matter ON routing_decisions (tenant_id, matter_id, created_at);

CREATE TABLE audit_events (
  id bigserial PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  actor_id uuid,
  action varchar(64) NOT NULL,
  resource_type varchar(32) NOT NULL,
  resource_id varchar(64),
  matter_id uuid,
  result varchar(16) NOT NULL,
  details jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_events_tenant_time ON audit_events (tenant_id, created_at);

CREATE FUNCTION forbid_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END $$;
CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER routing_decisions_append_only BEFORE UPDATE OR DELETE ON routing_decisions
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- Tenant isolation. Unset app.tenant_id -> NULL -> no rows visible.
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tenants
  USING (id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

GRANT USAGE ON SCHEMA public TO travo_app;
GRANT SELECT ON tenants TO travo_app;
GRANT SELECT, INSERT, UPDATE ON users, clients, matters, documents, clauses,
  model_policies, provider_credentials TO travo_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON matter_members TO travo_app;
GRANT DELETE ON clauses TO travo_app;
GRANT SELECT, INSERT ON routing_decisions, audit_events TO travo_app;
GRANT USAGE ON SEQUENCE audit_events_id_seq TO travo_app;
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
    for table in [*reversed(TENANT_TABLES), "tenants"]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS forbid_mutation()")
