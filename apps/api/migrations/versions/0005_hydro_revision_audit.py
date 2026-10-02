"""Keep prospective details of changed WSC observation fields."""

import sqlalchemy as sa
from alembic import op

revision = "0005_hydro_revision_audit"
down_revision = "0004_ingest_error_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hydro_revisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "observation_id",
            sa.Integer(),
            sa.ForeignKey("hydro_observations.id"),
            nullable=False,
        ),
        sa.Column("station_id", sa.String(length=12), sa.ForeignKey("stations.id"), nullable=False),
        sa.Column("observed_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("parameter", sa.String(length=20), nullable=False),
        sa.Column("detected_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("old_fields_json", sa.JSON(), nullable=False),
        sa.Column("new_fields_json", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_hydro_revision_station_time",
        "hydro_revisions",
        ["station_id", "detected_at_utc"],
    )


def downgrade() -> None:
    op.drop_index("ix_hydro_revision_station_time", table_name="hydro_revisions")
    op.drop_table("hydro_revisions")
