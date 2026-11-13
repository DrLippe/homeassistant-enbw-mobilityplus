"""Manually refresh the EnBW history without changing automatic polling."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ChargeCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([HistoryRefreshButton(hass.data[DOMAIN][entry.entry_id]["history"], entry)])


class HistoryRefreshButton(CoordinatorEntity[ChargeCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Historie aktualisieren"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: ChargeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_history_refresh"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="EnBW",
            model="Charging account",
        )

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
