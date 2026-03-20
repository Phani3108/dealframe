"""SQLAlchemy ORM models."""

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String
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
