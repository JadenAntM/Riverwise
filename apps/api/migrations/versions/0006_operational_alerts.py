"""Persist deduplicated operator alerts and their delivery state."""

import sqlalchemy as sa
from alembic import op

revision = "0006_operational_alerts"
down_revision = "0005_hydro_revision_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operational_alerts",
        sa.Column("key", sa.String(length=120), primary_key=True),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("station_id", sa.String(length=12), sa.ForeignKey("stations.id"), nullable=True),
        sa.Column("message", sa.String(length=240), nullable=False),
        sa.Column("first_seen_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_notified_at_utc", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("operational_alerts")
