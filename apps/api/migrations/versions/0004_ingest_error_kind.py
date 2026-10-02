"""Classify provider failures for operational diagnosis."""

import sqlalchemy as sa
from alembic import op

revision = "0004_ingest_error_kind"
down_revision = "0003_score_history_reliability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ingest_runs", sa.Column("error_kind", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("ingest_runs", "error_kind")
