"""Accent-insensitive legal search for Vietnamese (ADR-023).

Lawyers often type Vietnamese without tone marks ("phat vi pham"). A second tsvector holds the
unaccented text; queries match either column. `unaccent` is a trusted extension (PG13+).

Revision ID: 0008
Revises: 0007
"""

from alembic import op

revision = "0008"
down_revision = "0007"


def upgrade() -> None:
    op.execute(
        """
        CREATE EXTENSION IF NOT EXISTS unaccent;
        -- unaccent() is only STABLE; generated columns need an IMMUTABLE wrapper with a fixed
        -- dictionary.
        CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text
          LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
          AS $$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$;
        ALTER TABLE legal_units ADD COLUMN tsv_plain tsvector GENERATED ALWAYS AS
          (to_tsvector('simple', f_unaccent(coalesce(heading, '') || ' ' || text))) STORED;
        CREATE INDEX legal_units_tsv_plain ON legal_units USING gin (tsv_plain);
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX legal_units_tsv_plain; ALTER TABLE legal_units DROP COLUMN tsv_plain; "
        "DROP FUNCTION f_unaccent(text)"
    )
