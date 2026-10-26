"""Multi-provider charging history integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_PROVIDER, DOMAIN, POLL_INTERVAL, PROVIDER_ENBW
from .providers.enbw import EnBWProvider

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


class ChargeCoordinator(DataUpdateCoordinator):
    """One update coordinator per provider account."""

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
                raise UpdateFailed("Failed to update charging provider") from retry_exc


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.data[CONF_PROVIDER] != PROVIDER_ENBW:
        raise ConfigEntryNotReady("Unsupported charging provider")
    provider = EnBWProvider(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    coordinator = ChargeCoordinator(hass, provider, entry.title)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await hass.async_add_executor_job(provider.close)
        raise
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    coordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await hass.async_add_executor_job(coordinator.provider.close)
    return True
