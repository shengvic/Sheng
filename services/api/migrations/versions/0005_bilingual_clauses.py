"""Bilingual contracts: each clause keeps its other-language version (ADR-023).

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE documents
          ADD COLUMN primary_language varchar(8),
          ADD COLUMN bilingual_layout varchar(12) NOT NULL DEFAULT 'single'
            CHECK (bilingual_layout IN ('single', 'table', 'inline', 'paragraphs', 'halves'));
        ALTER TABLE clauses
          ADD COLUMN lang varchar(8),
          ADD COLUMN heading_alt text NOT NULL DEFAULT '',
          ADD COLUMN text_alt text NOT NULL DEFAULT '',
          ADD COLUMN lang_alt varchar(8);
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE clauses DROP COLUMN lang, DROP COLUMN heading_alt, DROP COLUMN text_alt, "
        "DROP COLUMN lang_alt; "
        "ALTER TABLE documents DROP COLUMN primary_language, DROP COLUMN bilingual_layout"
    )
