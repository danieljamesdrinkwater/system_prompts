"""Pydantic schemas for automation API requests and responses."""

from pydantic import BaseModel


class RuleCreate(BaseModel):
    name: str
    trigger_type: str
    trigger_config: dict = {}
    conditions: list[dict] = []
    actions: list[dict] = []


class RuleUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    trigger_type: str | None = None
    trigger_config: dict | None = None
    conditions: list[dict] | None = None
    actions: list[dict] | None = None


class SceneCreate(BaseModel):
    name: str
    actions: list[dict] = []


class SceneUpdate(BaseModel):
    name: str | None = None
    actions: list[dict] | None = None


class ScheduleCreate(BaseModel):
    name: str
    cron_expr: str
    action_type: str
    action_config: dict = {}


class ScheduleUpdate(BaseModel):
    name: str | None = None
    cron_expr: str | None = None
    action_type: str | None = None
    action_config: dict | None = None
    enabled: bool | None = None
