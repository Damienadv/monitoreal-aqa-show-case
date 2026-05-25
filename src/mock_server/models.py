"""SQLAlchemy ORM-модели mock-домена.

6 таблиц: cameras, rules, actions, detection_events, alert_events, archive_items.
UUID в TEXT через uuid.uuid4().hex (32 hex-символа). FK CASCADE где указано.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mock_server.db import Base


def new_uuid() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    rules: Mapped[list[Rule]] = relationship(back_populates="camera", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_cameras_active", "is_active"),)


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    camera_id: Mapped[str] = mapped_column(
        String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True
    )
    object_type: Mapped[str] = mapped_column(String, nullable=False)
    roi_polygon: Mapped[list[list[float]] | None] = mapped_column(JSON, nullable=True)
    schedule_cron: Mapped[str | None] = mapped_column(String, nullable=True)
    threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    action_mode: Mapped[str] = mapped_column(String, nullable=False, default="parallel")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    camera: Mapped[Camera] = relationship(back_populates="rules")
    actions: Mapped[list[Action]] = relationship(
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="Action.order_index",
    )


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    rule_id: Mapped[str] = mapped_column(
        String, ForeignKey("rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    rule: Mapped[Rule] = relationship(back_populates="actions")

    __table_args__ = (UniqueConstraint("rule_id", "order_index", name="uq_action_rule_order"),)


class DetectionEvent(Base):
    __tablename__ = "detection_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    camera_id: Mapped[str] = mapped_column(
        String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    object_type: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    bbox: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("external_id", "camera_id", name="uq_detection_external_camera"),
        Index("idx_det_camera_time", "camera_id", "occurred_at"),
    )


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    detection_event_id: Mapped[str] = mapped_column(
        String, ForeignKey("detection_events.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[str] = mapped_column(
        String, ForeignKey("rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    actions_executed: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class ArchiveItem(Base):
    __tablename__ = "archive_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    alert_event_id: Mapped[str] = mapped_column(
        String, ForeignKey("alert_events.id", ondelete="CASCADE"), nullable=False
    )
    camera_id: Mapped[str] = mapped_column(
        String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_url: Mapped[str | None] = mapped_column(String, nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("idx_archive_camera_time", "camera_id", "created_at"),
        Index("idx_archive_expires", "expires_at"),
    )
