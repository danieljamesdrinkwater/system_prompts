"""Tests for the automation engine — rule evaluation, conditions, and scenes."""

import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio

from app.automation.engine import AutomationEngine, OPERATORS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine():
    """Return a fresh AutomationEngine instance."""
    return AutomationEngine()


def _make_rule(
    trigger_type: str = "device_state",
    trigger_config: dict | None = None,
    conditions: list[dict] | None = None,
    actions: list[dict] | None = None,
    name: str = "test-rule",
) -> dict:
    """Helper to build a rule dict matching the engine's in-memory format."""
    return {
        "id": "rule-1",
        "name": name,
        "trigger_type": trigger_type,
        "trigger_config": trigger_config or {},
        "conditions": conditions or [],
        "actions": actions or [],
    }


# ---------------------------------------------------------------------------
# Trigger matching — device_state
# ---------------------------------------------------------------------------


class TestDeviceStateTrigger:
    """Tests for the ``device_state`` trigger type."""

    def test_matches_any_device_when_no_filter(self, engine):
        rule = _make_rule(trigger_config={})
        event = {"device_id": "light-1", "attribute": "power", "new_value": "on"}
        assert engine._trigger_matches(rule, event) is True

    def test_matches_specific_device(self, engine):
        rule = _make_rule(trigger_config={"device_id": "light-1"})
        event = {"device_id": "light-1", "attribute": "power", "new_value": "on"}
        assert engine._trigger_matches(rule, event) is True

    def test_rejects_wrong_device(self, engine):
        rule = _make_rule(trigger_config={"device_id": "light-1"})
        event = {"device_id": "light-2", "attribute": "power", "new_value": "on"}
        assert engine._trigger_matches(rule, event) is False

    def test_matches_specific_attribute(self, engine):
        rule = _make_rule(trigger_config={"device_id": "light-1", "attribute": "power"})
        event = {"device_id": "light-1", "attribute": "power", "new_value": "on"}
        assert engine._trigger_matches(rule, event) is True

    def test_rejects_wrong_attribute(self, engine):
        rule = _make_rule(trigger_config={"device_id": "light-1", "attribute": "brightness"})
        event = {"device_id": "light-1", "attribute": "power", "new_value": "on"}
        assert engine._trigger_matches(rule, event) is False

    def test_matches_to_value(self, engine):
        rule = _make_rule(trigger_config={"device_id": "light-1", "to_value": "on"})
        event = {"device_id": "light-1", "attribute": "power", "new_value": "on"}
        assert engine._trigger_matches(rule, event) is True

    def test_rejects_wrong_to_value(self, engine):
        rule = _make_rule(trigger_config={"device_id": "light-1", "to_value": "off"})
        event = {"device_id": "light-1", "attribute": "power", "new_value": "on"}
        assert engine._trigger_matches(rule, event) is False


# ---------------------------------------------------------------------------
# Trigger matching — threshold
# ---------------------------------------------------------------------------


class TestThresholdTrigger:
    """Tests for the ``threshold`` trigger type."""

    def test_above_threshold_crossing(self, engine):
        rule = _make_rule(
            trigger_type="threshold",
            trigger_config={
                "device_id": "sensor-1",
                "attribute": "temperature",
                "value": 30,
                "direction": "above",
            },
        )
        event = {
            "device_id": "sensor-1",
            "attribute": "temperature",
            "old_value": 29,
            "new_value": 31,
        }
        assert engine._trigger_matches(rule, event) is True

    def test_above_threshold_no_crossing(self, engine):
        rule = _make_rule(
            trigger_type="threshold",
            trigger_config={
                "device_id": "sensor-1",
                "attribute": "temperature",
                "value": 30,
                "direction": "above",
            },
        )
        event = {
            "device_id": "sensor-1",
            "attribute": "temperature",
            "old_value": 31,
            "new_value": 32,
        }
        assert engine._trigger_matches(rule, event) is False

    def test_below_threshold_crossing(self, engine):
        rule = _make_rule(
            trigger_type="threshold",
            trigger_config={
                "device_id": "sensor-1",
                "attribute": "temperature",
                "value": 20,
                "direction": "below",
            },
        )
        event = {
            "device_id": "sensor-1",
            "attribute": "temperature",
            "old_value": 21,
            "new_value": 19,
        }
        assert engine._trigger_matches(rule, event) is True

    def test_below_threshold_no_crossing(self, engine):
        rule = _make_rule(
            trigger_type="threshold",
            trigger_config={
                "device_id": "sensor-1",
                "attribute": "temperature",
                "value": 20,
                "direction": "below",
            },
        )
        event = {
            "device_id": "sensor-1",
            "attribute": "temperature",
            "old_value": 18,
            "new_value": 17,
        }
        assert engine._trigger_matches(rule, event) is False

    def test_threshold_non_numeric_returns_false(self, engine):
        rule = _make_rule(
            trigger_type="threshold",
            trigger_config={
                "device_id": "sensor-1",
                "attribute": "temperature",
                "value": 30,
                "direction": "above",
            },
        )
        event = {
            "device_id": "sensor-1",
            "attribute": "temperature",
            "old_value": "hot",
            "new_value": "hotter",
        }
        assert engine._trigger_matches(rule, event) is False


# ---------------------------------------------------------------------------
# Condition operators
# ---------------------------------------------------------------------------


class TestConditionOperators:
    """Verify every supported comparison operator."""

    @pytest.mark.parametrize(
        "op, actual, target, expected",
        [
            (">", 10, 5, True),
            (">", 5, 10, False),
            ("<", 5, 10, True),
            ("<", 10, 5, False),
            ("==", 5, 5, True),
            ("==", 5, 6, False),
            ("!=", 5, 6, True),
            ("!=", 5, 5, False),
            (">=", 10, 10, True),
            (">=", 9, 10, False),
            ("<=", 10, 10, True),
            ("<=", 11, 10, False),
        ],
    )
    def test_operator(self, engine, op, actual, target, expected):
        condition = {
            "device_id": "sensor-1",
            "attribute": "temperature",
            "operator": op,
            "value": target,
        }
        event = {
            "device_id": "sensor-1",
            "state": {"temperature": actual},
        }
        assert engine._evaluate_condition(condition, event) is expected

    def test_unknown_operator_returns_false(self, engine):
        condition = {
            "device_id": "sensor-1",
            "attribute": "temperature",
            "operator": "~",
            "value": 5,
        }
        event = {"device_id": "sensor-1", "state": {"temperature": 10}}
        assert engine._evaluate_condition(condition, event) is False

    def test_missing_attribute_returns_false(self, engine):
        condition = {
            "device_id": "sensor-1",
            "attribute": "humidity",
            "operator": "==",
            "value": 50,
        }
        event = {"device_id": "sensor-1", "state": {"temperature": 25}}
        assert engine._evaluate_condition(condition, event) is False

    def test_condition_for_other_device_is_skipped(self, engine):
        condition = {
            "device_id": "sensor-2",
            "attribute": "temperature",
            "operator": ">",
            "value": 100,
        }
        event = {"device_id": "sensor-1", "state": {"temperature": 10}}
        # Conditions targeting a different device are treated as satisfied.
        assert engine._evaluate_condition(condition, event) is True


# ---------------------------------------------------------------------------
# Full rule evaluation (trigger + conditions -> actions)
# ---------------------------------------------------------------------------


class TestRuleEvaluation:
    """End-to-end rule evaluation via ``engine.evaluate``."""

    @pytest.mark.asyncio
    async def test_matching_rule_fires_actions(self, engine):
        engine.rules = [
            _make_rule(
                trigger_config={"device_id": "light-1", "to_value": "on"},
                conditions=[
                    {
                        "device_id": "light-1",
                        "attribute": "brightness",
                        "operator": ">=",
                        "value": 50,
                    }
                ],
                actions=[{"type": "notify", "message": "Light is on and bright"}],
            )
        ]
        event = {
            "device_id": "light-1",
            "attribute": "power",
            "new_value": "on",
            "state": {"power": "on", "brightness": 80},
        }

        with patch.object(engine, "execute_actions", new_callable=AsyncMock) as mock_exec:
            await engine.evaluate(event)
            mock_exec.assert_called_once_with(engine.rules[0]["actions"])

    @pytest.mark.asyncio
    async def test_unmatched_trigger_skips_actions(self, engine):
        engine.rules = [
            _make_rule(
                trigger_config={"device_id": "light-1", "to_value": "off"},
                actions=[{"type": "notify", "message": "Should not fire"}],
            )
        ]
        event = {
            "device_id": "light-1",
            "attribute": "power",
            "new_value": "on",
            "state": {"power": "on"},
        }

        with patch.object(engine, "execute_actions", new_callable=AsyncMock) as mock_exec:
            await engine.evaluate(event)
            mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_condition_skips_actions(self, engine):
        engine.rules = [
            _make_rule(
                trigger_config={"device_id": "light-1"},
                conditions=[
                    {
                        "device_id": "light-1",
                        "attribute": "brightness",
                        "operator": ">=",
                        "value": 90,
                    }
                ],
                actions=[{"type": "notify", "message": "Should not fire"}],
            )
        ]
        event = {
            "device_id": "light-1",
            "attribute": "power",
            "new_value": "on",
            "state": {"power": "on", "brightness": 50},
        }

        with patch.object(engine, "execute_actions", new_callable=AsyncMock) as mock_exec:
            await engine.evaluate(event)
            mock_exec.assert_not_called()


# ---------------------------------------------------------------------------
# Action execution
# ---------------------------------------------------------------------------


class TestActionExecution:
    """Tests for ``execute_actions`` dispatching."""

    @pytest.mark.asyncio
    async def test_device_command_action(self, engine):
        with patch(
            "app.automation.engine.AutomationEngine._action_device_command",
            new_callable=AsyncMock,
        ) as mock_cmd:
            actions = [{"type": "device_command", "device_id": "light-1", "command": {"power": "off"}}]
            await engine.execute_actions(actions)
            mock_cmd.assert_called_once_with(actions[0])

    @pytest.mark.asyncio
    async def test_notify_action(self, engine):
        with patch(
            "app.automation.engine.ws_manager",
        ) as mock_ws:
            mock_ws.broadcast = AsyncMock()
            actions = [{"type": "notify", "message": "Hello"}]
            await engine.execute_actions(actions)
            mock_ws.broadcast.assert_called_once()
            payload = mock_ws.broadcast.call_args[0][0]
            assert payload["type"] == "automation_notification"
            assert payload["message"] == "Hello"

    @pytest.mark.asyncio
    async def test_unknown_action_type_does_not_raise(self, engine):
        actions = [{"type": "unknown_thing", "data": 123}]
        # Should log a warning but not raise.
        await engine.execute_actions(actions)


# ---------------------------------------------------------------------------
# Scene execution
# ---------------------------------------------------------------------------


class TestSceneExecution:
    """Tests for ``execute_scene``."""

    @pytest.mark.asyncio
    async def test_scene_executes_commands_in_parallel(self, engine):
        scene_actions = [
            {"type": "device_command", "device_id": "light-1", "command": {"power": "on"}},
            {"type": "device_command", "device_id": "light-2", "command": {"power": "on"}},
            {"type": "notify", "message": "Scene activated"},
        ]

        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_row = {"actions": json.dumps(scene_actions)}
        mock_cursor.fetchone = AsyncMock(return_value=mock_row)
        mock_db.execute = AsyncMock(return_value=mock_cursor)

        with patch.object(
            engine, "_action_device_command", new_callable=AsyncMock
        ) as mock_cmd, patch.object(
            engine, "_action_notify", new_callable=AsyncMock
        ) as mock_notify:
            await engine.execute_scene(mock_db, "scene-1")

            assert mock_cmd.call_count == 2
            mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_scene_not_found_does_not_raise(self, engine):
        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_cursor)

        # Should log a warning but not raise.
        await engine.execute_scene(mock_db, "nonexistent-scene")

    @pytest.mark.asyncio
    async def test_scene_with_empty_actions(self, engine):
        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value={"actions": "[]"})
        mock_db.execute = AsyncMock(return_value=mock_cursor)

        # Should complete without errors.
        await engine.execute_scene(mock_db, "scene-empty")


# ---------------------------------------------------------------------------
# Rule loading
# ---------------------------------------------------------------------------


class TestRuleLoading:
    """Tests for ``load_rules``."""

    @pytest.mark.asyncio
    async def test_load_rules_populates_list(self, engine):
        rows = [
            {
                "id": "r1",
                "name": "Rule 1",
                "trigger_type": "device_state",
                "trigger_config": '{"device_id": "light-1"}',
                "conditions": "[]",
                "actions": '[{"type": "notify", "message": "hi"}]',
            },
            {
                "id": "r2",
                "name": "Rule 2",
                "trigger_type": "threshold",
                "trigger_config": '{"device_id": "sensor-1", "value": 30, "direction": "above"}',
                "conditions": "[]",
                "actions": "[]",
            },
        ]

        # Build a mock row type that supports dict-style access.
        mock_rows = []
        for row_data in rows:
            mock_row = MagicMock()
            mock_row.__getitem__ = lambda self, key, _d=row_data: _d[key]
            mock_rows.append(mock_row)

        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=mock_rows)
        mock_db.execute = AsyncMock(return_value=mock_cursor)

        await engine.load_rules(mock_db)

        assert len(engine.rules) == 2
        assert engine.rules[0]["name"] == "Rule 1"
        assert engine.rules[1]["trigger_type"] == "threshold"
        assert isinstance(engine.rules[0]["trigger_config"], dict)
        assert isinstance(engine.rules[1]["actions"], list)
