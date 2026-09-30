"""Bilingual discrepancy findings (ADR-023).

Revision ID: 0006
Revises: 0005
"""

from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE findings
          DROP CONSTRAINT findings_kind_check,
          ADD CONSTRAINT findings_kind_check CHECK (kind IN ('playbook', 'law', 'bilingual')),
          DROP CONSTRAINT findings_classification_check,
          ADD CONSTRAINT findings_classification_check CHECK (classification IN
            ('standard', 'fallback', 'non_standard', 'missing', 'legal_note', 'discrepancy')),
          ADD COLUMN evidence jsonb;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM findings WHERE kind = 'bilingual';
        ALTER TABLE findings
          DROP COLUMN evidence,
          DROP CONSTRAINT findings_kind_check,
          ADD CONSTRAINT findings_kind_check CHECK (kind IN ('playbook', 'law')),
          DROP CONSTRAINT findings_classification_check,
          ADD CONSTRAINT findings_classification_check CHECK (classification IN
            ('standard', 'fallback', 'non_standard', 'missing', 'legal_note'));
        """
    )
