import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Integer, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ModelVersion(Base):
    __tablename__ = "model_versions"
    model_version_id: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    capabilities: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    status: Mapped[str] = mapped_column(Text, server_default="active")
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    registered_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    deactivated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class Battle(Base):
    __tablename__ = "battles"
    battle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(Text, nullable=False)
    model_a_hash: Mapped[str] = mapped_column(Text, nullable=False)
    model_b_hash: Mapped[str] = mapped_column(Text, nullable=False)
    position_order: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text)
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    style_a: Mapped[dict | None] = mapped_column(JSONB)
    style_b: Mapped[dict | None] = mapped_column(JSONB)
    is_invalid: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    model_a_version_id: Mapped[str | None] = mapped_column(Text, ForeignKey("model_versions.model_version_id"))
    model_b_version_id: Mapped[str | None] = mapped_column(Text, ForeignKey("model_versions.model_version_id"))
    de_anonymized_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    __table_args__ = (CheckConstraint("position_order IN ('a_first','b_first')"),)


class Vote(Base):
    __tablename__ = "votes"
    vote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    battle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("battles.battle_id"), unique=True)
    winner: Mapped[str] = mapped_column(Text, nullable=False)
    vote_duration_ms: Mapped[int | None] = mapped_column(Integer)
    quality_flag: Mapped[str] = mapped_column(Text, server_default="clean")
    voter_cluster_id: Mapped[str | None] = mapped_column(Text)
    response_length_a: Mapped[int | None] = mapped_column(Integer)
    response_length_b: Mapped[int | None] = mapped_column(Integer)
    latency_a_ms: Mapped[int | None] = mapped_column(Integer)
    latency_b_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    __table_args__ = (CheckConstraint("winner IN ('A','B','tie','both_bad')"),)


class RatingSnapshot(Base):
    __tablename__ = "rating_snapshots"
    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version_id: Mapped[str] = mapped_column(Text, ForeignKey("model_versions.model_version_id"))
    beta_hat: Mapped[float] = mapped_column(Float, nullable=False)
    rating_display: Mapped[float] = mapped_column(Float, nullable=False)
    ci_lower: Mapped[float] = mapped_column(Float, nullable=False)
    ci_upper: Mapped[float] = mapped_column(Float, nullable=False)
    rank_point: Mapped[int | None] = mapped_column(Integer)
    rank_ci_lower: Mapped[int] = mapped_column(Integer, nullable=False)
    rank_ci_upper: Mapped[int] = mapped_column(Integer, nullable=False)
    n_battles: Mapped[int] = mapped_column(Integer, nullable=False)
    provisional: Mapped[bool] = mapped_column(Boolean, server_default="true")
    gamma_len: Mapped[float | None] = mapped_column(Float)
    gamma_md: Mapped[float | None] = mapped_column(Float)
    gamma_pos: Mapped[float | None] = mapped_column(Float)
    fitted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, server_default="true")


class ProbeAudit(Base):
    __tablename__ = "probe_audit"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    normalized_hash: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
