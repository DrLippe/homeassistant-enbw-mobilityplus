"""Contract tests for EnBW adaptive poll schedule, without requiring HA."""
import ast
from datetime import timedelta
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, Mock

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "enbw_mobilityplus"


class FakeCoordinator:
    def __init__(self, hass, logger, name, update_interval):
        self.hass = hass
        self.update_interval = update_interval


class FakeUpdateFailed(Exception):
    pass


class Snapshot:
    def __init__(self, sessions=()):
        self.sessions = sessions


class Session:
    def __init__(self, transaction_id):
        self.transaction_id = transaction_id


def load_live_coordinator():
    constants = {}
    exec((ROOT / "const.py").read_text(encoding="utf-8"), constants)
    namespace = dict(
        DataUpdateCoordinator=FakeCoordinator,
        UpdateFailed=FakeUpdateFailed,
        _LOGGER=Mock(),
        diagnostic_message=str,
        ACTIVE_POLL_INTERVAL=constants["ACTIVE_POLL_INTERVAL"],
        LIVE_POLL_INTERVAL=constants["LIVE_POLL_INTERVAL"],
        set=set,
    )
    source = (ROOT / "__init__.py").read_text(encoding="utf-8")
    parsed = ast.parse(source)
    node = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == "LiveCoordinator")
    # Avoid runtime evaluation of HA-only type hints in isolated unit tests.
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node], type_ignores=[])
    exec(compile(module, "<live_coordinator>", "exec"), namespace)
    return namespace["LiveCoordinator"], constants


class PollScheduleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        coordinator_cls, self.constants = load_live_coordinator()
        self.hass = Mock()
        self.hass.async_add_executor_job = AsyncMock()
        self.history = Mock()
        self.history.async_request_refresh = AsyncMock()
        self.provider = Mock()
        self.live = coordinator_cls(self.hass, self.provider, "test", self.history)

    async def poll(self, *sessions):
        self.hass.async_add_executor_job.return_value = Snapshot(sessions)
        return await self.live._async_update_data()

    async def test_idle_five_minutes_and_history_one_hour(self):
        await self.poll()
        self.assertEqual(self.live.update_interval, timedelta(minutes=5))
        self.assertEqual(self.constants["POLL_INTERVAL"], timedelta(hours=1))
        self.history.async_request_refresh.assert_not_awaited()

    async def test_active_thirty_seconds(self):
        await self.poll(Session("tx1"))
        self.assertEqual(self.live.update_interval, timedelta(seconds=30))
        self.assertEqual(self.live.status, "active")

    async def test_completed_refreshes_history_once_after_confirmation(self):
        await self.poll(Session("tx1"))
        await self.poll()
        self.assertEqual(self.live.status, "end_pending")
        self.assertEqual(self.live.update_interval, timedelta(seconds=30))
        self.history.async_request_refresh.assert_not_awaited()
        await self.poll()
        self.assertEqual(self.live.status, "completed")
        self.assertEqual(self.live.update_interval, timedelta(minutes=5))
        self.history.async_request_refresh.assert_awaited_once()
        self.hass.bus.async_fire.assert_called_once_with(
            "enbw_mobilityplus_charge_completed", {"transaction_id": "tx1"}
        )
        await self.poll()
        self.history.async_request_refresh.assert_awaited_once()

    async def test_failed_history_refresh_keeps_live_status(self):
        self.history.async_request_refresh.side_effect = RuntimeError("test")
        await self.poll(Session("tx1"))
        await self.poll()
        await self.poll()
        self.assertEqual(self.live.status, "completed")


if __name__ == "__main__":
    unittest.main()
