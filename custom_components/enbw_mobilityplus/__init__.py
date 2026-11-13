"""EnBW mobility+ charging history integration."""

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.components.http import StaticPathConfig
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ACTIVE_POLL_INTERVAL, DOMAIN, LIVE_POLL_INTERVAL, POLL_INTERVAL
from .diagnostics import diagnostic_message
from .providers.enbw import EnBWProvider
from .tariff import next_tariff_date

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]
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

    def __init__(self, hass: HomeAssistant, provider: EnBWProvider, name: str, history: ChargeCoordinator) -> None:
        super().__init__(hass, logger=_LOGGER, name=f"{name} live", update_interval=LIVE_POLL_INTERVAL)
        self.provider = provider
        self.history = history
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

        # Match EWE Go: 30 s during charging, 5 min otherwise.
        self.update_interval = (
            ACTIVE_POLL_INTERVAL if snapshot.sessions or self._previous_ids else LIVE_POLL_INTERVAL
        )
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
                self.update_interval = LIVE_POLL_INTERVAL
                # Refresh history promptly after the second empty live poll.
                # History also retains its independent hourly schedule.
                try:
                    await self.history.async_request_refresh()
                except Exception:
                    # History refresh problems must not invalidate valid live data.
                    _LOGGER.debug("EnBW history refresh after charge completion failed", exc_info=True)
        elif self.status != "completed":
            self.status = "idle"
        return snapshot


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    provider = EnBWProvider(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    coordinator = ChargeCoordinator(hass, provider, entry.title)
    live = LiveCoordinator(hass, provider, entry.title, coordinator)
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

    # A calendar-day boundary changes the three-complete-month calculation,
    # without requiring any additional EnBW API requests.
    entry.async_on_unload(
        async_track_time_change(
            hass, lambda now: coordinator.async_update_listeners(),
            hour=0, minute=0, second=5,
        )
    )
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    if not hass.data.get(f"{DOMAIN}_frontend_registered"):
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                "/enbw-mobilityplus/enbw-tariff-card.js",
                str(Path(__file__).parent / "www" / "enbw-tariff-card.js"),
                cache_headers=False,
            )
        ])
        hass.data[f"{DOMAIN}_frontend_registered"] = True

    if not hass.services.has_service(DOMAIN, "record_tariff_change"):
        async def record_tariff_change(call):
            configured = hass.config_entries.async_entries(DOMAIN)
            target_id = call.data.get("config_entry_id")
            targets = [e for e in configured if e.entry_id == target_id] if target_id else configured
            if len(targets) != 1:
                raise HomeAssistantError("Bitte genau ein EnBW-Konto auswählen (config_entry_id)")
            selected = targets[0]
            today = dt_util.now().date()
            hass.config_entries.async_update_entry(
                selected,
                options={
                    **selected.options,
                    "current_tariff": call.data["tariff"],
                    "tariff_started_on": today.isoformat(),
                    "tariff_next_switch_on": next_tariff_date(today).isoformat(),
                },
            )

        hass.services.async_register(
            DOMAIN, "record_tariff_change", record_tariff_change,
            schema=vol.Schema({
                vol.Required("tariff"): vol.In(["S", "M", "L"]),
                vol.Optional("config_entry_id"): str,
            }),
        )
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    coordinators = hass.data[DOMAIN].pop(entry.entry_id)
    await hass.async_add_executor_job(coordinators["history"].provider.close)
    if not hass.data[DOMAIN] and hass.services.has_service(DOMAIN, "record_tariff_change"):
        hass.services.async_remove(DOMAIN, "record_tariff_change")
    return True
