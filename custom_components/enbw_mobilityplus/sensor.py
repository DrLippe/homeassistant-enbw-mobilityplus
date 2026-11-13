"""EnBW mobility+ charging metrics."""

from dataclasses import dataclass
from homeassistant.util import dt as dt_util
from typing import Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ChargeCoordinator, LiveCoordinator
from .const import DOMAIN
from .charge_type import normalize_charge_type
from .model import LiveSnapshot, ProviderSnapshot
from .tariff_adapter import tariff_comparison
from .monthly import month_summary, recent_sessions


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
    ChargeSensorDescription(key="last_end", translation_key="last_end", device_class=SensorDeviceClass.TIMESTAMP, extract=lambda data: data.last_session.stopped_at if data.last_session else None),
)

LIVE_SENSORS = (
    ChargeSensorDescription(key="charging_status", translation_key="charging_status", extract=lambda data: None),
    ChargeSensorDescription(key="charging_power", translation_key="charging_power", native_unit_of_measurement="kW", device_class=SensorDeviceClass.POWER, extract=lambda data: data.primary.power_kw if data.primary else None),
    ChargeSensorDescription(key="charging_energy", translation_key="charging_energy", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, extract=lambda data: data.primary.energy_kwh if data.primary else None),
    ChargeSensorDescription(key="charging_soc", translation_key="charging_soc", native_unit_of_measurement="%", device_class=SensorDeviceClass.BATTERY, extract=lambda data: data.primary.soc_percent if data.primary else None),
    ChargeSensorDescription(key="charging_duration", translation_key="charging_duration", native_unit_of_measurement="min", extract=lambda data: round(data.primary.duration_seconds / 60, 1) if data.primary and data.primary.duration_seconds is not None else None),
    ChargeSensorDescription(key="charging_cost", translation_key="charging_cost", native_unit_of_measurement="EUR", device_class=SensorDeviceClass.MONETARY, extract=lambda data: data.primary.cost_eur if data.primary else None),
    ChargeSensorDescription(key="charging_location", translation_key="charging_location", extract=lambda data: data.primary.location if data.primary else None),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinators = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ChargeSensor(coordinators["history"], entry, description) for description in SENSORS] + [LiveChargeSensor(coordinators["live"], entry, description) for description in LIVE_SENSORS] + [EnBWChargeTypeSensor(coordinators["history"], coordinators["live"], entry)] + [TariffSensor(coordinators["history"], entry, key, name, unit) for key, name, unit in TARIFF_SENSORS] + [MonthlySensor(coordinators["history"], entry, key, name, unit) for key, name, unit in MONTHLY_SENSORS] + [RecentHistorySensor(coordinators["history"], entry)])


class ChargeSensor(CoordinatorEntity[ChargeCoordinator], SensorEntity):
    """Charging metrics of an EnBW mobility+ account."""

    entity_description: ChargeSensorDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator: ChargeCoordinator, entry: ConfigEntry, description: ChargeSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="EnBW",
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


class LiveChargeSensor(ChargeSensor):
    """Live readings; unavailable if EnBW's monitor cannot be queried."""

    def __init__(self, coordinator: LiveCoordinator, entry: ConfigEntry, description: ChargeSensorDescription) -> None:
        super().__init__(coordinator, entry, description)

    @property
    def native_value(self):
        if self.entity_description.key == "charging_status":
            return {"idle": "Inaktiv", "active": "Aktiv", "end_pending": "Ende wird geprüft", "completed": "Beendet"}[self.coordinator.status]
        return self.entity_description.extract(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        session = self.coordinator.data.primary
        if self.entity_description.key == "charging_status" and session:
            return {"transaction_id": session.transaction_id, "evse_id": session.evse_id, "operator": session.operator}
        return None


class EnBWChargeTypeSensor(SensorEntity):
    """Use the active connector type, falling back to latest completed history."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "charge_type"

    def __init__(self, history: ChargeCoordinator, live: LiveCoordinator, entry: ConfigEntry) -> None:
        self.history = history
        self.live = live
        self._attr_unique_id = f"{entry.entry_id}_charge_type"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="EnBW",
            model="Charging account",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.history.async_add_listener(self.async_write_ha_state))
        self.async_on_remove(self.live.async_add_listener(self.async_write_ha_state))

    @property
    def available(self) -> bool:
        return self.history.last_update_success or self.live.last_update_success

    def _source(self) -> tuple[str | None, str | None]:
        if self.live.last_update_success and self.live.data and self.live.data.primary:
            return self.live.data.primary.charge_point_type, "Aktiver Ladevorgang"
        if self.history.last_update_success and self.history.data and self.history.data.last_session:
            return self.history.data.last_session.details.get("plug_type"), "Letzter abgeschlossener Ladevorgang"
        return None, None

    @property
    def native_value(self) -> str:
        raw, _source = self._source()
        return normalize_charge_type(raw) or "Unbekannt"

    @property
    def extra_state_attributes(self):
        raw, source = self._source()
        return {"api_wert": raw, "datenquelle": source}


TARIFF_SENSORS = (
    ("recommendation", "Tarifwechsel", None),
    ("monthly_savings", "Tarifwechsel Ersparnis", "EUR"),
    ("break_even_kwh", "Tarifwechsel Wechselgrenze", "kWh"),
    ("average_energy", "Tarifwechsel Monatsverbrauch", "kWh"),
)


class TariffSensor(CoordinatorEntity[ChargeCoordinator], SensorEntity):
    """Derive S/M/L comparison from the existing history snapshot, without API calls."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:calculator-variant"

    def __init__(self, coordinator: ChargeCoordinator, entry: ConfigEntry, key: str, name: str, unit: str | None):
        super().__init__(coordinator)
        self.key = key
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_tariff_{key}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="EnBW",
            model="Charging account",
        )

    @property
    def _result(self) -> dict:
        return tariff_comparison(self.coordinator.data, dt_util.now(), dict(self.entry.options))

    @property
    def native_value(self):
        return self._result.get(self.key)

    @property
    def extra_state_attributes(self):
        return {**self._result, "config_entry_id": self.entry.entry_id}


MONTHLY_SENSORS = (
    ("energy", "Monat Energie", "kWh"),
    ("cost", "Monat Kosten", "EUR"),
    ("count", "Monat Ladevorgänge", None),
    ("price", "Monat Durchschnittspreis", "EUR/kWh"),
)


class MonthlySensor(CoordinatorEntity[ChargeCoordinator], SensorEntity):
    """Calendar-month totals calculated from downloaded history."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ChargeCoordinator, entry: ConfigEntry, key: str, name: str, unit: str | None):
        super().__init__(coordinator)
        self.key = key
        self._attr_unique_id = f"{entry.entry_id}_month_{key}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="EnBW",
            model="Charging account",
        )

    @property
    def native_value(self):
        return month_summary(self.coordinator.data, dt_util.now())[self.key]


class RecentHistorySensor(CoordinatorEntity[ChargeCoordinator], SensorEntity):
    """Last 50 completed sessions for the native Lovelace markdown example."""

    _attr_has_entity_name = True
    _attr_name = "Ladehistorie"
    _attr_icon = "mdi:history"
    # The full details are displayed live in dashboards; avoid recorder bloat.
    _unrecorded_attributes = frozenset({"sessions"})

    def __init__(self, coordinator: ChargeCoordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_charging_history"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="EnBW",
            model="Charging account",
        )

    @property
    def native_value(self):
        return self.coordinator.data.total_sessions

    @property
    def extra_state_attributes(self):
        return {"sessions": recent_sessions(self.coordinator.data, 50)}
