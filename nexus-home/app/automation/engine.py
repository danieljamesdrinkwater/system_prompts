"""Automation rule engine — evaluates triggers and executes actions."""

import asyncio
import json
import logging
import operator
from typing import Any

import aiosqlite

from app.database import get_db
from app.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

OPERATORS: dict[str, Any] = {
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
    ">=": operator.ge,
    "<=": operator.le,
}


class AutomationEngine:
    """Evaluates automation rules against device events and dispatches actions."""

    def __init__(self) -> None:
        self.rules: list[dict] = []

    async def load_rules(self, db: aiosqlite.Connection) -> None:
        """Load all enabled rules from the database."""
        cursor = await db.execute(
            "SELECT id, name, trigger_type, trigger_config, conditions, actions "
            "FROM automation_rules WHERE enabled = 1"
        )
        rows = await cursor.fetchall()
        self.rules = []
        for row in rows:
            self.rules.append({
                "id": row["id"],
                "name": row["name"],
                "trigger_type": row["trigger_type"],
                "trigger_config": json.loads(row["trigger_config"]),
                "conditions": json.loads(row["conditions"]),
                "actions": json.loads(row["actions"]),
            })
        logger.info("Loaded %d automation rules", len(self.rules))

    async def evaluate(self, event: dict) -> None:
        """Evaluate all rules against a device state-change event.

        Args:
            event: Dict with keys ``device_id``, ``attribute``, ``old_value``,
                   ``new_value``, and the full ``state`` snapshot.
        """
        for rule in self.rules:
            try:
                if self._trigger_matches(rule, event) and await self._conditions_met(rule, event):
                    logger.info("Rule '%s' triggered by event on device %s",
                                rule["name"], event.get("device_id"))
                    await self.execute_actions(rule["actions"])
            except Exception:
                logger.exception("Error evaluating rule '%s'", rule.get("name"))

    # ------------------------------------------------------------------
    # Trigger matching
    # ------------------------------------------------------------------

    def _trigger_matches(self, rule: dict, event: dict) -> bool:
        """Check whether the event satisfies the rule's trigger."""
        trigger_type = rule["trigger_type"]
        config = rule["trigger_config"]

        if trigger_type == "device_state":
            return self._match_device_state(config, event)
        if trigger_type == "threshold":
            return self._match_threshold(config, event)
        return False

    @staticmethod
    def _match_device_state(config: dict, event: dict) -> bool:
        """Trigger fires when a specific device changes a specific attribute."""
        if config.get("device_id") and config["device_id"] != event.get("device_id"):
            return False
        if config.get("attribute") and config["attribute"] != event.get("attribute"):
            return False
        if "to_value" in config and config["to_value"] != event.get("new_value"):
            return False
        return True

    @staticmethod
    def _match_threshold(config: dict, event: dict) -> bool:
        """Trigger fires when a numeric value crosses a boundary."""
        if config.get("device_id") and config["device_id"] != event.get("device_id"):
            return False
        if config.get("attribute") and config["attribute"] != event.get("attribute"):
            return False

        threshold = config.get("value")
        direction = config.get("direction", "above")  # "above" or "below"
        old = event.get("old_value")
        new = event.get("new_value")

        try:
            old_f, new_f, threshold_f = float(old), float(new), float(threshold)
        except (TypeError, ValueError):
            return False

        if direction == "above":
            return old_f <= threshold_f < new_f
        if direction == "below":
            return old_f >= threshold_f > new_f
        return False

    # ------------------------------------------------------------------
    # Condition evaluation
    # ------------------------------------------------------------------

    async def _conditions_met(self, rule: dict, event: dict) -> bool:
        """All conditions must be satisfied (AND logic)."""
        conditions = rule.get("conditions") or []
        if not conditions:
            return True

        for cond in conditions:
            if not self._evaluate_condition(cond, event):
                return False
        return True

    @staticmethod
    def _evaluate_condition(condition: dict, event: dict) -> bool:
        """Evaluate a single condition against the current event state.

        A condition looks like::

            {"device_id": "...", "attribute": "...", "operator": ">=", "value": 50}

        When the condition's ``device_id`` matches the event's device, the
        attribute is looked up in ``event["state"]``.
        """
        cond_device = condition.get("device_id")
        attribute = condition.get("attribute")
        op_str = condition.get("operator", "==")
        target = condition.get("value")

        op_func = OPERATORS.get(op_str)
        if op_func is None:
            logger.warning("Unknown operator '%s' in condition", op_str)
            return False

        # Only evaluate against the event's own state snapshot for now.
        if cond_device != event.get("device_id"):
            return True  # condition for another device — skip

        state = event.get("state", {})
        actual = state.get(attribute)
        if actual is None:
            return False

        try:
            return op_func(actual, target)
        except TypeError:
            return False

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    async def execute_actions(self, actions: list[dict]) -> None:
        """Dispatch a list of actions sequentially."""
        for action in actions:
            try:
                action_type = action.get("type")
                if action_type == "device_command":
                    await self._action_device_command(action)
                elif action_type == "notify":
                    await self._action_notify(action)
                elif action_type == "scene":
                    scene_id = action.get("scene_id")
                    if scene_id:
                        async with get_db() as db:
                            await self.execute_scene(db, scene_id)
                else:
                    logger.warning("Unknown action type: %s", action_type)
            except Exception:
                logger.exception("Error executing action: %s", action)

    async def _action_device_command(self, action: dict) -> None:
        """Send a command to a device."""
        from app.devices.service import send_command

        device_id = action.get("device_id")
        command = action.get("command", {})
        if device_id:
            await send_command(device_id, command)

    async def _action_notify(self, action: dict) -> None:
        """Broadcast a notification via WebSocket."""
        message = action.get("message", "")
        await ws_manager.broadcast({
            "type": "automation_notification",
            "message": message,
            "source": action.get("source", "automation"),
        })

    async def execute_scene(self, db: aiosqlite.Connection, scene_id: str) -> None:
        """Load a scene and execute all of its commands in parallel."""
        cursor = await db.execute("SELECT actions FROM scenes WHERE id = ?", (scene_id,))
        row = await cursor.fetchone()
        if row is None:
            logger.warning("Scene '%s' not found", scene_id)
            return

        actions: list[dict] = json.loads(row["actions"])
        if not actions:
            return

        tasks = []
        for action in actions:
            if action.get("type") == "device_command":
                tasks.append(self._action_device_command(action))
            elif action.get("type") == "notify":
                tasks.append(self._action_notify(action))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("Scene '%s' executed (%d actions)", scene_id, len(tasks))


automation_engine = AutomationEngine()
