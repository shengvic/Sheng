"""Review options (output language) and the other-language redline (ADR-023).

Revision ID: 0007
Revises: 0006
"""

from alembic import op

revision = "0007"
down_revision = "0006"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE review_runs ADD COLUMN options jsonb NOT NULL DEFAULT '{}'::jsonb;
        ALTER TABLE findings ADD COLUMN suggested_redline_alt text;
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE review_runs DROP COLUMN options; "
        "ALTER TABLE findings DROP COLUMN suggested_redline_alt"
    )
