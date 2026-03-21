"""SQLAlchemy ORM models."""

import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class VideoStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(1024))
    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus), default=VideoStatus.PENDING
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    segments: Mapped[list["Segment"]] = relationship(
        "Segment", back_populates="video", cascade="all, delete-orphan"
    )


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"))
    timestamp_ms: Mapped[int] = mapped_column(Integer, index=True)
    timestamp_str: Mapped[str] = mapped_column(String(20))
    transcript: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    frame_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    video: Mapped["Video"] = relationship("Video", back_populates="segments")
    extractions: Mapped[list["Extraction"]] = relationship(
        "Extraction", back_populates="segment", cascade="all, delete-orphan"
    )


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("segments.id"), index=True)
    model_name: Mapped[str] = mapped_column(String(100), index=True)
    topic: Mapped[str] = mapped_column(String(255))
    sentiment: Mapped[str] = mapped_column(String(50))
    risk: Mapped[str] = mapped_column(String(50))
    risk_score: Mapped[float] = mapped_column(Float)
    objections: Mapped[list] = mapped_column(JSON, default=list)
    decision_signals: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    segment: Mapped["Segment"] = relationship("Segment", back_populates="extractions")


# ── Phase 2: Observatory ───────────────────────────────────────────────────────

class ObservatorySession(Base):
    __tablename__ = "observatory_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    status: Mapped[str] = mapped_column(String(50), default="pending")
    model_names: Mapped[list] = mapped_column(JSON, default=list)
    segments_analyzed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_agreement: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    runs: Mapped[list["ModelRunRecord"]] = relationship(
        "ModelRunRecord", back_populates="session", cascade="all, delete-orphan"
    )


class ModelRunRecord(Base):
    __tablename__ = "model_run_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("observatory_sessions.id"), index=True)
    segment_timestamp_ms: Mapped[int] = mapped_column(Integer, index=True)
    model_name: Mapped[str] = mapped_column(String(100), index=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    objections: Mapped[list] = mapped_column(JSON, default=list)
    decision_signals: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["ObservatorySession"] = relationship(
        "ObservatorySession", back_populates="runs"
    )


# ── Phase 3: Portfolios ────────────────────────────────────────────────────────

class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    portfolio_videos: Mapped[list["PortfolioVideo"]] = relationship(
        "PortfolioVideo", back_populates="portfolio", cascade="all, delete-orphan"
    )


class PortfolioVideo(Base):
    __tablename__ = "portfolio_videos"

    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id"), primary_key=True
    )
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    portfolio: Mapped["Portfolio"] = relationship(
        "Portfolio", back_populates="portfolio_videos"
    )
    video: Mapped["Video"] = relationship("Video")


# ── Phase E: Persistent State Layer ────────────────────────────────────────────

class RiskEvent(Base):
    """Persisted risk alert/event from the risk agent."""
    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company: Mapped[str] = mapped_column(String(255), index=True)
    deal_id: Mapped[str] = mapped_column(String(255), index=True, default="")
    job_id: Mapped[str] = mapped_column(String(255), index=True)
    alert_type: Mapped[str] = mapped_column(String(100))  # threshold | spike | persist
    risk_score: Mapped[float] = mapped_column(Float)
    message: Mapped[str] = mapped_column(String(2048))
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KGNodeRecord(Base):
    """Persisted knowledge graph node."""
    __tablename__ = "kg_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), index=True)
    label: Mapped[str] = mapped_column(String(255))
    frequency: Mapped[int] = mapped_column(Integer, default=0)
    jobs: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class KGEdgeRecord(Base):
    """Persisted knowledge graph edge."""
    __tablename__ = "kg_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(255), index=True)
    target: Mapped[str] = mapped_column(String(255), index=True)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SummaryCache(Base):
    """Cached generated summaries."""
    __tablename__ = "summary_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(255), index=True)
    summary_type: Mapped[str] = mapped_column(String(100), index=True)
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CoachingRecord(Base):
    """Persisted coaching history per rep."""
    __tablename__ = "coaching_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rep_id: Mapped[str] = mapped_column(String(255), index=True)
    calls_analyzed: Mapped[int] = mapped_column(Integer)
    overall_score: Mapped[float] = mapped_column(Float)
    grade: Mapped[str] = mapped_column(String(5))
    dimensions: Mapped[list] = mapped_column(JSON, default=list)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SpeakerLabel(Base):
    """Manual speaker label mapping: SPEAKER_A → 'John Smith'."""
    __tablename__ = "speaker_labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True)
    speaker_tag: Mapped[str] = mapped_column(String(50))  # SPEAKER_A
    speaker_name: Mapped[str] = mapped_column(String(255))  # John Smith
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Phase H: Enterprise Models ─────────────────────────────────────────────────

class Tenant(Base):
    """Multi-tenant isolation."""
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(50), default="free")  # free | pro | enterprise
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    """User accounts with auth."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(50), default="analyst")  # admin | manager | analyst | viewer
    tier: Mapped[str] = mapped_column(String(50), default="free")  # free | pro | enterprise
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    api_key: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Immutable audit trail for all user actions."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), index=True)  # upload | view | export | settings
    resource_type: Mapped[str] = mapped_column(String(100))  # video | report | setting
    resource_id: Mapped[str] = mapped_column(String(255))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Notification(Base):
    """User notification entries."""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(100))  # risk_alert | batch_complete | drift | digest
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AnnotationRecord(Base):
    """Collaborative annotations on transcript segments."""
    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    job_id: Mapped[str] = mapped_column(String(255), index=True)
    user_id: Mapped[str] = mapped_column(String(255))
    segment_index: Mapped[int] = mapped_column(Integer)
    start_word: Mapped[int] = mapped_column(Integer)
    end_word: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(100), index=True)
    comment: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[dict] = mapped_column(JSON, default=list)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReviewItemRecord(Base):
    """Active learning review queue items."""
    __tablename__ = "review_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    job_id: Mapped[str] = mapped_column(String(255), index=True)
    segment_index: Mapped[int] = mapped_column(Integer)
    extraction: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    reviewer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    corrected_extraction: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    review_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# ── Phase N: Persistent Job Queue + Search Index ───────────────────────────────

class JobRecord(Base):
    """Persistent job queue — survives server restarts."""
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    video_path: Mapped[str] = mapped_column(String(1024), default="")
    frames_dir: Mapped[str] = mapped_column(String(1024), default="")
    stages_done: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class SearchDocRecord(Base):
    """Persistent search index documents — rebuilt into TF-IDF on startup."""
    __tablename__ = "search_docs"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # video_id:timestamp_ms
    video_id: Mapped[str] = mapped_column(String(255), index=True)
    timestamp_ms: Mapped[int] = mapped_column(Integer)
    timestamp_str: Mapped[str] = mapped_column(String(20), default="")
    topic: Mapped[str] = mapped_column(String(255))
    risk: Mapped[str] = mapped_column(String(50))
    risk_score: Mapped[float] = mapped_column(Float)
    objections: Mapped[list] = mapped_column(JSON, default=list)
    decision_signals: Mapped[list] = mapped_column(JSON, default=list)
    transcript: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
