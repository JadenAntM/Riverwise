"""Associate ingestion runs with an optional station."""

import sqlalchemy as sa
from alembic import op

revision = "0002_ingest_station"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ingest_runs") as batch_op:
        batch_op.add_column(sa.Column("station_id", sa.String(12), nullable=True))
        batch_op.create_foreign_key(
            "fk_ingest_runs_station",
            "stations",
            ["station_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_ingest_source_station_time",
            ["source", "station_id", "started_at_utc"],
        )


def downgrade() -> None:
    with op.batch_alter_table("ingest_runs") as batch_op:
        batch_op.drop_index("ix_ingest_source_station_time")
        batch_op.drop_constraint("fk_ingest_runs_station", type_="foreignkey")
        batch_op.drop_column("station_id")
