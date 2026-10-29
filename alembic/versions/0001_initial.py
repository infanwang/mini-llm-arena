"""initial schema

Revision ID: 0001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "model_versions",
        sa.Column("model_version_id", sa.Text, primary_key=True),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("capabilities", postgresql.JSONB, server_default="{}"),
        sa.Column("status", sa.Text, server_default="active"),
        sa.Column("last_heartbeat_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("registered_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("deactivated_at", sa.TIMESTAMP(timezone=True)),
    )

    op.create_table(
        "battles",
        sa.Column("battle_id", postgresql.UUID, primary_key=True),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("prompt_hash", sa.Text, nullable=False),
        sa.Column("model_a_hash", sa.Text, nullable=False),
        sa.Column("model_b_hash", sa.Text, nullable=False),
        sa.Column("position_order", sa.Text, nullable=False),
        sa.Column("domain", sa.Text),
        sa.Column("session_id", sa.Text, nullable=False),
        sa.Column("style_a", postgresql.JSONB),
        sa.Column("style_b", postgresql.JSONB),
        sa.Column("is_invalid", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("model_a_version_id", sa.Text, sa.ForeignKey("model_versions.model_version_id")),
        sa.Column("model_b_version_id", sa.Text, sa.ForeignKey("model_versions.model_version_id")),
        sa.Column("de_anonymized_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint("position_order IN ('a_first','b_first')"),
    )
    op.create_index("idx_battles_created", "battles", ["created_at"])
    op.create_index("idx_battles_prompt_hash", "battles", ["prompt_hash"])

    op.create_table(
        "votes",
        sa.Column("vote_id", postgresql.UUID, primary_key=True),
        sa.Column("battle_id", postgresql.UUID, sa.ForeignKey("battles.battle_id"), unique=True),
        sa.Column("winner", sa.Text, nullable=False),
        sa.Column("vote_duration_ms", sa.Integer),
        sa.Column("quality_flag", sa.Text, server_default="clean"),
        sa.Column("voter_cluster_id", sa.Text),
        sa.Column("response_length_a", sa.Integer),
        sa.Column("response_length_b", sa.Integer),
        sa.Column("latency_a_ms", sa.Integer),
        sa.Column("latency_b_ms", sa.Integer),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("winner IN ('A','B','tie','both_bad')"),
    )
    op.create_index(
        "idx_votes_quality", "votes", ["quality_flag"],
        postgresql_where=sa.text("quality_flag <> 'clean'"),
    )

    op.create_table(
        "rating_snapshots",
        sa.Column("snapshot_id", postgresql.UUID, primary_key=True),
        sa.Column("model_version_id", sa.Text, sa.ForeignKey("model_versions.model_version_id")),
        sa.Column("beta_hat", sa.Float, nullable=False),
        sa.Column("rating_display", sa.Float, nullable=False),
        sa.Column("ci_lower", sa.Float, nullable=False),
        sa.Column("ci_upper", sa.Float, nullable=False),
        sa.Column("rank_point", sa.Integer, nullable=True),
        sa.Column("rank_ci_lower", sa.Integer, nullable=False),
        sa.Column("rank_ci_upper", sa.Integer, nullable=False),
        sa.Column("n_battles", sa.Integer, nullable=False),
        sa.Column("provisional", sa.Boolean, server_default="true"),
        sa.Column("gamma_len", sa.Float),
        sa.Column("gamma_md", sa.Float),
        sa.Column("gamma_pos", sa.Float),
        sa.Column("fitted_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("is_current", sa.Boolean, server_default="true"),
    )
    op.create_index(
        "idx_rating_current", "rating_snapshots", ["model_version_id"],
        unique=True, postgresql_where=sa.text("is_current"),
    )

    op.create_table(
        "probe_audit",
        sa.Column("id", postgresql.UUID, primary_key=True),
        sa.Column("normalized_hash", sa.Text, nullable=False),
        sa.Column("classification", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table("probe_audit")
    op.drop_table("rating_snapshots")
    op.drop_table("votes")
    op.drop_table("battles")
    op.drop_table("model_versions")
