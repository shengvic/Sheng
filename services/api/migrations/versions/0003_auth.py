"""Per-tenant OIDC sign-in and revocable sessions (ADR-018).

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"

SCHEMA = """
ALTER TABLE users ADD COLUMN idp_subject varchar(255);
CREATE UNIQUE INDEX users_idp_subject ON users (tenant_id, idp_subject)
  WHERE idp_subject IS NOT NULL;

CREATE TABLE tenant_idps (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL UNIQUE REFERENCES tenants(id),
  issuer text NOT NULL,
  client_id text NOT NULL,
  client_secret_ciphertext bytea,
  enabled boolean NOT NULL DEFAULT true,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, tenant_id)
);

-- One firm per email domain, enforced globally by the primary key even though each firm only
-- sees its own rows. (Domain ownership verification, e.g. DNS TXT, is a pre-GA item.)
CREATE TABLE idp_domains (
  domain varchar(253) PRIMARY KEY CHECK (domain = lower(domain)),
  idp_id uuid NOT NULL,
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  FOREIGN KEY (idp_id, tenant_id) REFERENCES tenant_idps(id, tenant_id) ON DELETE CASCADE
);

CREATE TABLE auth_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  user_id uuid NOT NULL,
  method varchar(8) NOT NULL CHECK (method IN ('oidc','dev')),
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  user_agent varchar(300),
  FOREIGN KEY (user_id, tenant_id) REFERENCES users(id, tenant_id)
);
CREATE INDEX auth_sessions_user ON auth_sessions (tenant_id, user_id, created_at);

GRANT SELECT, INSERT, UPDATE ON tenant_idps, auth_sessions TO travo_app;
GRANT SELECT, INSERT, DELETE ON idp_domains TO travo_app;

-- Sign-in happens before we know the tenant. These two functions are the only cross-tenant
-- read path; they return ids and public IdP coordinates, never secrets (ADR-018).
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'travo_idp_lookup') THEN
    CREATE ROLE travo_idp_lookup NOLOGIN BYPASSRLS;
  END IF;
END $$;
GRANT USAGE ON SCHEMA public TO travo_idp_lookup;
GRANT SELECT (id, tenant_id, issuer, client_id, enabled) ON tenant_idps TO travo_idp_lookup;
GRANT SELECT ON idp_domains TO travo_idp_lookup;

CREATE FUNCTION idp_for_email_domain(p_domain text)
RETURNS TABLE (idp_id uuid, tenant_id uuid, issuer text, client_id text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT i.id, i.tenant_id, i.issuer, i.client_id
    FROM idp_domains d JOIN tenant_idps i ON i.id = d.idp_id
   WHERE i.enabled AND d.domain = lower(p_domain)
$$;

CREATE FUNCTION idp_by_id(p_id uuid)
RETURNS TABLE (idp_id uuid, tenant_id uuid, issuer text, client_id text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT i.id, i.tenant_id, i.issuer, i.client_id FROM tenant_idps i
   WHERE i.enabled AND i.id = p_id
$$;

ALTER FUNCTION idp_for_email_domain(text) OWNER TO travo_idp_lookup;
ALTER FUNCTION idp_by_id(uuid) OWNER TO travo_idp_lookup;
REVOKE ALL ON FUNCTION idp_for_email_domain(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION idp_by_id(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION idp_for_email_domain(text) TO travo_app;
GRANT EXECUTE ON FUNCTION idp_by_id(uuid) TO travo_app;
"""


def upgrade() -> None:
    op.execute(SCHEMA)
    for table in ("tenant_idps", "idp_domains", "auth_sessions"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
            "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
        )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS idp_for_email_domain(text)")
    op.execute("DROP FUNCTION IF EXISTS idp_by_id(uuid)")
    op.execute("DROP TABLE IF EXISTS auth_sessions, idp_domains, tenant_idps CASCADE")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS idp_subject")
