"""Legal sources: provenance of official snapshots and lawyer verification (ADR-019).

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE legal_sources
          ADD COLUMN review_status varchar(12) NOT NULL DEFAULT 'unverified'
            CHECK (review_status IN ('unverified', 'verified')),
          ADD COLUMN verified_by varchar(320),
          ADD COLUMN verified_at timestamptz,
          ADD COLUMN verification_note text,
          ADD COLUMN snapshot_sha256 varchar(64),
          ADD COLUMN retrieved_at timestamptz;
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE legal_sources DROP COLUMN review_status, DROP COLUMN verified_by, "
        "DROP COLUMN verified_at, DROP COLUMN verification_note, "
        "DROP COLUMN snapshot_sha256, DROP COLUMN retrieved_at"
    )
