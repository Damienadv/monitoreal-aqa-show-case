"""Pydantic-схемы для request/response. Источник правды — docs/api_contract.yaml."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ObjectType = Literal["person", "vehicle", "animal", "unknown"]
ActionType = Literal["relay", "audio", "mobile_push", "webhook"]
ActionMode = Literal["parallel", "sequential"]
AlertStatus = Literal["pending", "processing", "done", "failed"]
ActionExecStatus = Literal["done", "failed", "skipped"]


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Camera ----


class CameraRead(ORMBase):
    id: str
    code: str
    name: str
    location: str | None = None
    is_active: bool
    created_at: datetime


# ---- Action ----


class ActionCreate(BaseModel):
    type: ActionType
    order_index: int = Field(ge=0)
    config: dict[str, Any] | None = None


class ActionRead(ORMBase):
    id: str
    type: ActionType
    order_index: int
    config: dict[str, Any] | None = None


# ---- Rule ----


class RuleCreate(BaseModel):
    name: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    object_type: ObjectType
    roi_polygon: list[list[float]] | None = None
    schedule_cron: str | None = None
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    action_mode: ActionMode
    actions: list[ActionCreate] = Field(min_length=1)


class RuleUpdate(BaseModel):
    name: str | None = None
    object_type: ObjectType | None = None
    roi_polygon: list[list[float]] | None = None
    schedule_cron: str | None = None
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    is_enabled: bool | None = None
    action_mode: ActionMode | None = None


class RuleRead(ORMBase):
    id: str
    name: str
    camera_id: str
    object_type: ObjectType
    roi_polygon: list[list[float]] | None = None
    schedule_cron: str | None = None
    threshold: float
    is_enabled: bool
    action_mode: ActionMode
    actions: list[ActionRead]
    created_at: datetime


# ---- DetectionEvent ----


class DetectionEventCreate(BaseModel):
    external_id: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    object_type: ObjectType
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: list[int] | None = None
    occurred_at: datetime


class DetectionAccepted(BaseModel):
    detection_event_id: str
    matched_rule_ids: list[str]
    alert_event_ids: list[str]
    duplicate: bool = False


# ---- AlertEvent ----


class AlertActionExecuted(BaseModel):
    action_id: str
    type: ActionType
    status: ActionExecStatus
    executed_at: datetime
    error: str | None = None


class AlertEventRead(ORMBase):
    id: str
    detection_event_id: str
    rule_id: str
    status: AlertStatus
    actions_executed: list[dict[str, Any]] | None = None
    created_at: datetime


class PaginatedAlertEvents(BaseModel):
    items: list[AlertEventRead]
    total: int
    page: int
    per_page: int


# ---- Archive ----


class ArchiveItemRead(ORMBase):
    id: str
    alert_event_id: str
    camera_id: str
    snapshot_url: str | None = None
    meta: dict[str, Any] | None = None
    expires_at: datetime
    created_at: datetime


class PaginatedArchive(BaseModel):
    items: list[ArchiveItemRead]
    total: int
    page: int
    per_page: int


# ---- Actions test ----


class ActionsTestRequest(BaseModel):
    rule_id: str


class ActionsTestResponse(BaseModel):
    rule_id: str
    actions_executed: list[AlertActionExecuted]


# ---- Retention ----


class RetentionResponse(BaseModel):
    deleted_count: int = Field(ge=0)


# ---- Errors (RFC 7807) ----


class ProblemDetail(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
