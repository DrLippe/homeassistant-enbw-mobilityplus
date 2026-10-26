"""EnBW mobility+ charging history integration."""

import logging
import httpx

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LIVE_POLL_INTERVAL, POLL_INTERVAL
from .providers.enbw import EnBWProvider

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
_LOGGER = logging.getLogger(__name__)


class ChargeCoordinator(DataUpdateCoordinator):
    """One update coordinator per EnBW account."""

    def __init__(self, hass: HomeAssistant, provider: EnBWProvider, name: str) -> None:
        super().__init__(hass, logger=_LOGGER, name=name, update_interval=POLL_INTERVAL)
        self.provider = provider

    async def _async_update_data(self):
        try:
            return await self.hass.async_add_executor_job(self.provider.fetch)
        except Exception:
            # A fresh client recovers expired credentials/cookies once.
            try:
                await self.hass.async_add_executor_job(self.provider.refresh_login)
                return await self.hass.async_add_executor_job(self.provider.fetch)
            except Exception as retry_exc:
                raise UpdateFailed("Failed to update EnBW mobility+") from retry_exc


class LiveCoordinator(DataUpdateCoordinator):
    """Poll active charging independently of the expensive historical fetch."""

    def __init__(self, hass: HomeAssistant, provider: EnBWProvider, name: str) -> None:
        super().__init__(hass, logger=_LOGGER, name=f"{name} live", update_interval=LIVE_POLL_INTERVAL)
        self.provider = provider
        self.status = "idle"
        self._previous_ids: set[str] = set()
        self._empty_polls = 0

    async def _async_update_data(self):
        try:
            snapshot = await self.hass.async_add_executor_job(self.provider.fetch_active)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in (401, 403):
                raise UpdateFailed(f"EnBW live endpoint returned HTTP {exc.response.status_code}") from exc
            try:
                await self.hass.async_add_executor_job(self.provider.refresh_login)
                snapshot = await self.hass.async_add_executor_job(self.provider.fetch_active)
            except Exception as exc:
                raise UpdateFailed("Failed to update active EnBW sessions") from exc
        except Exception as exc:
            raise UpdateFailed("Failed to update active EnBW sessions") from exc

        ids = {session.transaction_id for session in snapshot.sessions if session.transaction_id}
        if snapshot.sessions:
            self.status = "active"
            self._previous_ids = ids
            self._empty_polls = 0
        elif self._previous_ids:
            # Confirm empty sessions twice before claiming a completion.
            self._empty_polls += 1
            self.status = "end_pending"
            if self._empty_polls >= 2:
                self.status = "completed"
                for transaction_id in self._previous_ids:
                    self.hass.bus.async_fire(
                        "enbw_mobilityplus_charge_completed",
                        {"transaction_id": transaction_id},
                    )
                self._previous_ids.clear()
        elif self.status != "completed":
            self.status = "idle"
        return snapshot


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    provider = EnBWProvider(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    coordinator = ChargeCoordinator(hass, provider, entry.title)
    live = LiveCoordinator(hass, provider, entry.title)
    try:
        await coordinator.async_config_entry_first_refresh()
        # An undocumented live endpoint must not break existing history sensors.
        await live.async_refresh()
    except Exception:
        await hass.async_add_executor_job(provider.close)
        raise
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"history": coordinator, "live": live}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    coordinators = hass.data[DOMAIN].pop(entry.entry_id)
    await hass.async_add_executor_job(coordinators["history"].provider.close)
    return True
