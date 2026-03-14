"""FastAPI router for automation rules, scenes, and schedules."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.auth import verify_api_key
from app.database import get_db
from app.automation.schemas import (
    RuleCreate,
    RuleUpdate,
    SceneCreate,
    SceneUpdate,
    ScheduleCreate,
    ScheduleUpdate,
)
from app.automation.engine import automation_engine
from app.automation.scheduler import scheduler_manager

router = APIRouter()

# ──────────────────────────────────────────────────────────────────────
# Rules
# ──────────────────────────────────────────────────────────────────────


@router.get("/rules")
async def list_rules(_key: str = Depends(verify_api_key)):
    """Return all automation rules."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, name, enabled, trigger_type, trigger_config, "
            "conditions, actions, created_at FROM automation_rules ORDER BY name"
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "enabled": bool(row["enabled"]),
                "trigger_type": row["trigger_type"],
                "trigger_config": json.loads(row["trigger_config"]),
                "conditions": json.loads(row["conditions"]),
                "actions": json.loads(row["actions"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


@router.post("/rules", status_code=201)
async def create_rule(rule: RuleCreate, _key: str = Depends(verify_api_key)):
    """Create a new automation rule."""
    rule_id = str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            "INSERT INTO automation_rules "
            "(id, name, trigger_type, trigger_config, conditions, actions) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                rule_id,
                rule.name,
                rule.trigger_type,
                json.dumps(rule.trigger_config),
                json.dumps(rule.conditions),
                json.dumps(rule.actions),
            ),
        )
        await db.commit()

        # Reload rules into the engine so the new rule is active immediately.
        await automation_engine.load_rules(db)

    return {
        "id": rule_id,
        "name": rule.name,
        "enabled": True,
        "trigger_type": rule.trigger_type,
        "trigger_config": rule.trigger_config,
        "conditions": rule.conditions,
        "actions": rule.actions,
    }


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    updates: RuleUpdate,
    _key: str = Depends(verify_api_key),
):
    """Update an existing automation rule."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM automation_rules WHERE id = ?", (rule_id,)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Rule not found")

        fields = updates.model_dump(exclude_unset=True)
        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Serialise JSON columns before writing.
        for col in ("trigger_config", "conditions", "actions"):
            if col in fields:
                fields[col] = json.dumps(fields[col])

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [rule_id]
        await db.execute(
            f"UPDATE automation_rules SET {set_clause} WHERE id = ?", values
        )
        await db.commit()
        await automation_engine.load_rules(db)

        cursor = await db.execute(
            "SELECT id, name, enabled, trigger_type, trigger_config, "
            "conditions, actions, created_at FROM automation_rules WHERE id = ?",
            (rule_id,),
        )
        row = await cursor.fetchone()
        return {
            "id": row["id"],
            "name": row["name"],
            "enabled": bool(row["enabled"]),
            "trigger_type": row["trigger_type"],
            "trigger_config": json.loads(row["trigger_config"]),
            "conditions": json.loads(row["conditions"]),
            "actions": json.loads(row["actions"]),
            "created_at": row["created_at"],
        }


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, _key: str = Depends(verify_api_key)):
    """Delete an automation rule."""
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM automation_rules WHERE id = ?", (rule_id,)
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Rule not found")
        await automation_engine.load_rules(db)
    return {"status": "deleted", "rule_id": rule_id}


# ──────────────────────────────────────────────────────────────────────
# Scenes
# ──────────────────────────────────────────────────────────────────────


@router.get("/scenes")
async def list_scenes(_key: str = Depends(verify_api_key)):
    """Return all scenes."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, name, actions, created_at FROM scenes ORDER BY name"
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "actions": json.loads(row["actions"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


@router.post("/scenes", status_code=201)
async def create_scene(scene: SceneCreate, _key: str = Depends(verify_api_key)):
    """Create a new scene."""
    scene_id = str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            "INSERT INTO scenes (id, name, actions) VALUES (?, ?, ?)",
            (scene_id, scene.name, json.dumps(scene.actions)),
        )
        await db.commit()
    return {
        "id": scene_id,
        "name": scene.name,
        "actions": scene.actions,
    }


@router.post("/scenes/{scene_id}/activate")
async def activate_scene(scene_id: str, _key: str = Depends(verify_api_key)):
    """Execute all actions defined in a scene."""
    async with get_db() as db:
        cursor = await db.execute("SELECT id FROM scenes WHERE id = ?", (scene_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Scene not found")
        await automation_engine.execute_scene(db, scene_id)
    return {"status": "activated", "scene_id": scene_id}


@router.delete("/scenes/{scene_id}")
async def delete_scene(scene_id: str, _key: str = Depends(verify_api_key)):
    """Delete a scene."""
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Scene not found")
    return {"status": "deleted", "scene_id": scene_id}


# ──────────────────────────────────────────────────────────────────────
# Schedules
# ──────────────────────────────────────────────────────────────────────


@router.get("/schedules")
async def list_schedules(_key: str = Depends(verify_api_key)):
    """Return all schedules."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, name, cron_expr, action_type, action_config, "
            "enabled, created_at FROM schedules ORDER BY name"
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "cron_expr": row["cron_expr"],
                "action_type": row["action_type"],
                "action_config": json.loads(row["action_config"]),
                "enabled": bool(row["enabled"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


@router.post("/schedules", status_code=201)
async def create_schedule(
    schedule: ScheduleCreate, _key: str = Depends(verify_api_key)
):
    """Create a new cron schedule."""
    schedule_id = str(uuid.uuid4())
    schedule_dict = {
        "id": schedule_id,
        "name": schedule.name,
        "cron_expr": schedule.cron_expr,
        "action_type": schedule.action_type,
        "action_config": schedule.action_config,
    }
    async with get_db() as db:
        await scheduler_manager.add_schedule(db, schedule_dict)
    return {
        "id": schedule_id,
        "name": schedule.name,
        "cron_expr": schedule.cron_expr,
        "action_type": schedule.action_type,
        "action_config": schedule.action_config,
        "enabled": True,
    }


@router.put("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    updates: ScheduleUpdate,
    _key: str = Depends(verify_api_key),
):
    """Update an existing schedule."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM schedules WHERE id = ?", (schedule_id,)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Schedule not found")

        fields = updates.model_dump(exclude_unset=True)
        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        if "action_config" in fields:
            fields["action_config"] = json.dumps(fields["action_config"])

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [schedule_id]
        await db.execute(
            f"UPDATE schedules SET {set_clause} WHERE id = ?", values
        )
        await db.commit()

        # Re-register the job if the scheduler is running.
        if scheduler_manager.scheduler and scheduler_manager.scheduler.running:
            job = scheduler_manager.scheduler.get_job(schedule_id)
            if job:
                job.remove()
            cursor = await db.execute(
                "SELECT id, cron_expr, action_type, action_config, enabled "
                "FROM schedules WHERE id = ?",
                (schedule_id,),
            )
            row = await cursor.fetchone()
            if row and row["enabled"]:
                scheduler_manager._add_job_from_row(row)

        cursor = await db.execute(
            "SELECT id, name, cron_expr, action_type, action_config, "
            "enabled, created_at FROM schedules WHERE id = ?",
            (schedule_id,),
        )
        row = await cursor.fetchone()
        return {
            "id": row["id"],
            "name": row["name"],
            "cron_expr": row["cron_expr"],
            "action_type": row["action_type"],
            "action_config": json.loads(row["action_config"]),
            "enabled": bool(row["enabled"]),
            "created_at": row["created_at"],
        }


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str, _key: str = Depends(verify_api_key)):
    """Delete a schedule."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM schedules WHERE id = ?", (schedule_id,)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Schedule not found")
        await scheduler_manager.remove_schedule(db, schedule_id)
    return {"status": "deleted", "schedule_id": schedule_id}
