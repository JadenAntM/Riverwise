"""Initial Riverwise schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stations",
        sa.Column("id", sa.String(12), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("province", sa.String(2), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("has_discharge", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
    )
    op.create_table(
        "hydro_observations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("station_id", sa.String(12), sa.ForeignKey("stations.id"), nullable=False),
        sa.Column("observed_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("parameter", sa.String(20), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("qualifier", sa.String(120)),
        sa.Column("approval", sa.String(80)),
        sa.Column("ingested_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("station_id", "observed_at_utc", "parameter"),
    )
    op.create_index(
        "ix_hydro_station_parameter_time",
        "hydro_observations",
        ["station_id", "parameter", "observed_at_utc"],
    )
    op.create_table(
        "weather_hours",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("station_id", sa.String(12), sa.ForeignKey("stations.id"), nullable=False),
        sa.Column("valid_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("air_temp_c", sa.Float()),
        sa.Column("precip_mm", sa.Float()),
        sa.Column("cloud_cover_pct", sa.Float()),
        sa.Column("pressure_hpa", sa.Float()),
        sa.Column("ingested_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("station_id", "valid_at_utc", "kind"),
    )
    op.create_index("ix_weather_station_time", "weather_hours", ["station_id", "valid_at_utc"])
    op.create_table(
        "score_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("station_id", sa.String(12), sa.ForeignKey("stations.id"), nullable=False),
        sa.Column("computed_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hydro_observed_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Float()),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("confidence", sa.String(40), nullable=False),
        sa.Column("available_points", sa.Integer(), nullable=False),
        sa.Column("earned_points", sa.Integer(), nullable=False),
        sa.Column("components_json", sa.JSON(), nullable=False),
        sa.Column("rules_version", sa.String(32), nullable=False),
    )
    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at_utc", sa.DateTime(timezone=True)),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("fetched_count", sa.Integer(), nullable=False),
        sa.Column("upserted_count", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("error", sa.String(500)),
    )


def downgrade() -> None:
    op.drop_table("ingest_runs")
    op.drop_table("score_snapshots")
    op.drop_index("ix_weather_station_time", table_name="weather_hours")
    op.drop_table("weather_hours")
    op.drop_index("ix_hydro_station_parameter_time", table_name="hydro_observations")
    op.drop_table("hydro_observations")
    op.drop_table("stations")
