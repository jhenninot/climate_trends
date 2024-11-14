import logging
from homeassistant.components.sensor import SensorEntity

from . import ThermoCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Configurer les capteurs à partir d'une entrée de configuration."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = [
        TempSensor(coordinator,"current_temperature"),
        TempSensor(coordinator,"temperature"),
        TempTrendSensor(coordinator),
        ActionTempTrendSensor(coordinator, "heating"),
        ActionTempTrendSensor(coordinator, "idle")
    ]
    async_add_entities(sensors)

class TempSensor(SensorEntity):
    def __init__(self, coordinator: ThermoCoordinator, sensor_type: str):
        self.coordinator = coordinator
        state = self.coordinator.hass.states.get(self.coordinator.climate_entity)
        self.thermo_friendly_name = state.attributes.get("friendly_name", "Unknown Entity")
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{sensor_type}"
        self._attr_name = f"{coordinator.config_entry.title} {sensor_type.replace('_', ' ').title()}"
        self._attr_device_class = "temperature"
        self._attr_native_unit_of_measurement = "°C"

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.config_entry.entry_id)},
            "name": self.coordinator.config_entry.title,
            "manufacturer": DOMAIN,
            "model": "Smart Thermostat",
            "sw_version": "1.0",
        }

    @property
    def native_value(self):
        value = self.coordinator.data.get(self._sensor_type)
        return float(value) if value is not None else None

    @property
    def available(self):
        return self.coordinator.last_update_success
    
    @property
    def extra_state_attributes(self):
        state = self.coordinator.hass.states.get(self.coordinator.climate_entity)
        return state.attributes

    async def async_update(self):
        await self.coordinator.async_request_refresh()


class TempTrendSensor(SensorEntity):
    def __init__(self, coordinator: ThermoCoordinator):
        self.coordinator = coordinator
        self._attr_name = f"{coordinator.config_entry.title} 1h temperature trend"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_temp_trend"
        self._attr_native_unit_of_measurement = "°C/h"

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.config_entry.entry_id)},
            "name": self.coordinator.config_entry.title,
            "manufacturer": DOMAIN,
            "model": "Smart Thermostat",
            "sw_version": "1.0",
        }
    
    @property
    def icon(self):
        if self.native_value is None:
            return "mdi:thermometer-alert"
        if self.native_value > 0:
            return "mdi:thermometer-chevron-up"
        if self.native_value < 0:
            return "mdi:thermometer-chevron-down"
        return "mdi:thermometer-alert"

    @property
    def native_value(self):
        """Retourne la variation de température en degré/heure."""
        return self.coordinator.get_one_hour_temperature_variation()
    
    @property
    def extra_state_attributes(self):
        temp_histo = self.coordinator.get_temp_history()
        hvac_actions_periods = self.coordinator.get_actions_history()
        return {
            "actions_history": hvac_actions_periods,
            "temperature_history": temp_histo,
        }

    @property
    def available(self):
        return self.coordinator.last_update_success

    async def async_update(self):
        await self.coordinator.async_request_refresh()

class ActionTempTrendSensor(SensorEntity):
    def __init__(self, coordinator: ThermoCoordinator, action):
        self._action = action
        self.coordinator = coordinator
        self._attr_name = f"{coordinator.config_entry.title} {action} Temperature Trend"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{action}_temp_trend"
        self._attr_native_unit_of_measurement = "°C/h"

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.config_entry.entry_id)},
            "name": self.coordinator.config_entry.title,
            "manufacturer": DOMAIN,
            "model": "Thermostat trends",
            "sw_version": "1.0",
        }
    
    @property
    def icon(self):
        if self.native_value is None:
            return "mdi:thermometer-alert"

        if self._action == 'idle':
            if self.native_value > 0:
                return "mdi:snowflake-alert"
            if self.native_value < 0:
                return "mdi:snowflake"
            return "mdi:thermometer-alert"
        
        if self._action == 'heating':
            if self.native_value > 0:
                return "mdi:fire"
            if self.native_value < 0:
                return "mdi:fire_alert"
            return "mdi:thermometer-alert"

        if self.native_value > 0:
            return "mdi:thermometer-chevron-down"
        if self.native_value < 0:
            return "mdi:thermometer-chevron-up"
        return "mdi:thermometer-alert"

    @property
    def native_value(self):
        """Retourne la variation de température en degré/heure."""
        data = self.coordinator.get_last_action_temperature_variation(self._action)
        if data is not None:
            self._attr_extra_state_attributes = data["action_data"]
            return data["temperature_variation"]
        return None

    @property
    def available(self):
        return self.coordinator.last_update_success

    async def async_update(self):
        await self.coordinator.async_request_refresh()




