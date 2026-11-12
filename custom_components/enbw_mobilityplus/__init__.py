"""EnBW mobility+ charging history integration."""

import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LIVE_POLL_INTERVAL, POLL_INTERVAL
from .diagnostics import diagnostic_message
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
        except Exception as exc:
            detail = diagnostic_message(exc)
            _LOGGER.error("EnBW mobility+ Ladehistorie konnte nicht abgerufen werden: %s", detail)
            raise UpdateFailed(f"EnBW Ladehistorie: {detail}") from None


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
        except Exception as exc:
            detail = diagnostic_message(exc)
            _LOGGER.error("EnBW mobility+ Live-Abfrage fehlgeschlagen: %s", detail)
            raise UpdateFailed(f"EnBW Live-Abfrage: {detail}") from None

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
    except Exception as exc:
        _LOGGER.error("EnBW mobility+ Einrichtung nicht abgeschlossen: %s", diagnostic_message(exc))
        await hass.async_add_executor_job(provider.close)
        raise ConfigEntryNotReady("EnBW mobility+ login/API unavailable; will retry") from exc
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"history": coordinator, "live": live}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    coordinators = hass.data[DOMAIN].pop(entry.entry_id)
    await hass.async_add_executor_job(coordinators["history"].provider.close)
    return True
