import logging
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

from .coordinators import ThermoCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry
):
    coordinator = ThermoCoordinator(hass,entry)
    await coordinator.async_load_history()
    await coordinator.async_config_entry_first_refresh()
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    @callback
    def _async_climate_state_listener(event):
        new_state = event.data.get("new_state")
        if new_state:
            coordinator.async_update_from_event(new_state)

    climate_entity_id = entry.data["climate_entity"]
    hass.bus.async_listen(
        "state_changed",
        lambda event: _async_climate_state_listener(event)
        if event.data.get("entity_id") == climate_entity_id
        else None,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Supprimer l'intégration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Redémarrer l'intégration après mise à jour de la configuration."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)