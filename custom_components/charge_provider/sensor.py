"""Unified charging metrics for every configured provider account."""

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ChargeCoordinator
from .const import CONF_PROVIDER, DOMAIN
from .model import ProviderSnapshot


@dataclass(frozen=True, kw_only=True)
class ChargeSensorDescription(SensorEntityDescription):
    extract: Callable[[ProviderSnapshot], object]


SENSORS = (
    ChargeSensorDescription(key="total_energy", translation_key="total_energy", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL, extract=lambda data: data.total_energy_kwh),
    ChargeSensorDescription(key="total_cost", translation_key="total_cost", native_unit_of_measurement="EUR", device_class=SensorDeviceClass.MONETARY, state_class=SensorStateClass.TOTAL, extract=lambda data: data.total_cost_eur),
    ChargeSensorDescription(key="total_sessions", translation_key="total_sessions", state_class=SensorStateClass.TOTAL, extract=lambda data: data.total_sessions),
    ChargeSensorDescription(key="last_charge", translation_key="last_charge", device_class=SensorDeviceClass.TIMESTAMP, extract=lambda data: data.last_session.started_at if data.last_session else None),
    ChargeSensorDescription(key="last_energy", translation_key="last_energy", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, extract=lambda data: data.last_session.energy_kwh if data.last_session else None),
    ChargeSensorDescription(key="last_cost", translation_key="last_cost", native_unit_of_measurement="EUR", device_class=SensorDeviceClass.MONETARY, extract=lambda data: data.last_session.cost_eur if data.last_session else None),
    ChargeSensorDescription(key="last_station", translation_key="last_station", extract=lambda data: data.last_session.station if data.last_session else None),
    ChargeSensorDescription(key="last_duration", translation_key="last_duration", native_unit_of_measurement="min", extract=lambda data: round(data.last_session.duration_seconds / 60, 1) if data.last_session and data.last_session.duration_seconds is not None else None),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(ChargeSensor(coordinator, entry, description) for description in SENSORS)


class ChargeSensor(CoordinatorEntity[ChargeCoordinator], SensorEntity):
    """Standard key names remain the same for future Ionity/EWE/Aral adapters."""

    entity_description: ChargeSensorDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator: ChargeCoordinator, entry: ConfigEntry, description: ChargeSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="EnBW" if entry.data[CONF_PROVIDER] == "enbw" else entry.data[CONF_PROVIDER],
            model="Charging account",
        )

    @property
    def native_value(self):
        return self.entity_description.extract(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        if self.entity_description.key != "last_charge":
            return None
        session = self.coordinator.data.last_session
        if not session:
            return None
        return {
            "session_id": session.identifier,
            "stopped_at": session.stopped_at.isoformat() if session.stopped_at else None,
            "operator": session.operator,
            "station": session.station,
            **session.details,
        }
