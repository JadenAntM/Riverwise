"""Support score history and explicit ingestion metrics."""

import sqlalchemy as sa
from alembic import op

revision = "0003_score_history_reliability"
down_revision = "0002_ingest_station"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "score_snapshots",
        "hydro_observed_at_utc",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
    op.create_unique_constraint(
        "uq_score_snapshot_station_time_version",
        "score_snapshots",
        ["station_id", "computed_at_utc", "rules_version"],
    )
    op.create_index(
        "ix_score_station_time_version",
        "score_snapshots",
        ["station_id", "computed_at_utc", "rules_version"],
    )
    for column in ("inserted_count", "updated_count", "revision_count"):
        op.add_column(
            "ingest_runs",
            sa.Column(column, sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    for column in ("revision_count", "updated_count", "inserted_count"):
        op.drop_column("ingest_runs", column)
    op.drop_index("ix_score_station_time_version", table_name="score_snapshots")
    op.drop_constraint(
        "uq_score_snapshot_station_time_version",
        "score_snapshots",
        type_="unique",
    )
    op.alter_column(
        "score_snapshots",
        "hydro_observed_at_utc",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
