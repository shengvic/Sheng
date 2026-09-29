-- Login role for the API. Member of travo_app (created by migration 0001); not an owner or
-- superuser, so row-level security applies. Change the password outside local dev.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'travo_api') THEN
    CREATE ROLE travo_api LOGIN PASSWORD 'travo_api';
  END IF;
END $$;
GRANT travo_app TO travo_api;
