"""Active EnBW charging session (not physical cable connectivity)."""

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LiveCoordinator
from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([EnBWActiveSession(hass.data[DOMAIN][entry.entry_id]["live"], entry)])


class EnBWActiveSession(CoordinatorEntity[LiveCoordinator], BinarySensorEntity):
    """True while EnBW reports at least one active session."""

    _attr_has_entity_name = True
    entity_description = BinarySensorEntityDescription(key="active_session", translation_key="active_session")

    def __init__(self, coordinator: LiveCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_active_session"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="EnBW",
            model="Charging account",
        )

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.sessions)
