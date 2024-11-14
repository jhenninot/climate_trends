from collections import deque
from datetime import timedelta, datetime
import logging

from homeassistant.core import callback
from homeassistant.helpers.storage import Store
import json  # Pour sérialisation des dates

from .const import DOMAIN

MAXLEN = 50
TEMP_HISTO_MINUTES = 5

_LOGGER = logging.getLogger(__name__)

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

class ThermoCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, config_entry):
        super().__init__(hass, _LOGGER, name=config_entry.title, update_interval=timedelta(minutes=5))

        self.config_entry = config_entry
        self.climate_entity = config_entry.data.get("climate_entity")
        self._current_temp = None
        self._temperature_history = deque(maxlen=MAXLEN)
        self._actions_history = deque(maxlen=MAXLEN)

        self._history_store = Store(hass, "1", f"{DOMAIN}_temperature_history_{config_entry.entry_id}")
        self._actions_store = Store(hass, "1", f"{DOMAIN}_temperature_actions_{config_entry.entry_id}")
        
        self.action = None
        self.action_start_temp = None
        self.action_start_time = None

    async def async_load_history(self):

        """Charge l'historique depuis le fichier de stockage."""
        # Historique des températures
        history_data = await self._history_store.async_load()
        if history_data:
            self._temperature_history = deque(
                [(datetime.fromisoformat(item["timestamp"]), item["temperature"]) for item in history_data],
                maxlen=MAXLEN
            )

        # Historique des actions
        actions_data = await self._actions_store.async_load()
        
        if actions_data:
            self._actions_history = deque(
                [(item["action"], datetime.fromisoformat(item["start_time"]), item["start_temp"], datetime.fromisoformat(item["stop_time"]), item["stop_temp"]) for item in actions_data],
                maxlen=MAXLEN
            )
    
    async def async_save_history(self):
        """Sauvegarde l'historique dans le fichier de stockage."""
        # Historique des températures
        history_data  = self.get_temp_history()
        await self._history_store.async_save(history_data)
       
        # Historique des actions
        actions_data = self.get_actions_history()
        await self._actions_store.async_save(actions_data)


    async def _async_update_data(self):
        """Met à jour périodiquement les données depuis Home Assistant."""
        state = self.hass.states.get(self.climate_entity)
        if not state:
            raise UpdateFailed(f"L'entité {self.climate_entity} est introuvable.")
        current_temp = state.attributes.get("current_temperature")
        self._current_temp = current_temp
        if self.action_start_temp is None:
            self.action_start_temp = current_temp
        current_time = datetime.now()

        # On récupère l'action en cours (heating, idle ....)
        action = state.attributes.get("hvac_action")

        # Si l'action change (nouvelle action)
        if self.action != action:
            # si on avait bien une action en cours, on enregistre l'action en cours
            if self.action is not None:
                self._actions_history.append((self.action, self.action_start_time, self.action_start_temp, current_time, current_temp))
                await self.async_save_history()

            # ensuite, on crée la nouvelle action 
            self.action_start_time = current_time
            self.action_start_temp = current_temp
            self.action = action

        if current_temp is not None:
            if not self._temperature_history or self._temperature_history[-1][1] != current_temp:
                self._temperature_history.append((datetime.now(), current_temp))
                await self.async_save_history()

        return self._parse_state(state)

    @callback
    def async_update_from_event(self, state):
        """Met à jour les données immédiatement à partir d'un événement."""
        self.data = self._parse_state(state)
        self.async_update_listeners()

    def _parse_state(self, state):
        """Extrait et retourne les données pertinentes de l'état de l'entité."""
        data = {}
        for key in state.attributes:
            data[key] = state.attributes[key]
        data ["temperature_history"] = self._temperature_history
        return data
    
    def get_actions_history(self): 
        actions_data = [
            {"action": action, "start_time": start_time, "start_temp": start_temp, "stop_time": stop_time, "stop_temp": stop_temp}
            for action, start_time, start_temp, stop_time, stop_temp in self._actions_history
        ]
        return actions_data
    
    def get_temp_history(self):
        history_data = [
            {"timestamp": timestamp.isoformat(), "temperature": temp}
            for timestamp, temp in self._temperature_history
        ]
        return history_data
    
    def get_temperature_variation(self):
        if len(self._temperature_history) < 2:
            return None
        first_entry = self._temperature_history[0]
        last_entry = self._temperature_history[-1]
        first_time, first_temp = first_entry
        last_time, last_temp = last_entry
        temp_diff = last_temp - first_temp
        time_diff_minutes = (last_time - first_time).total_seconds() / 60
        time_diff_hours = (last_time - first_time).total_seconds() / 3600
        return round(temp_diff / time_diff_hours,2) if time_diff_minutes > TEMP_HISTO_MINUTES else None
    
    def get_one_hour_temperature_variation(self):
        """Calcul de la variation de température sur 1 heure."""
        if len(self._temperature_history) < 2:
            return None
        
        if self._current_temp is None:
            return None
        
        history = self.get_temp_history()
        history.reverse()

        last_time = datetime.now()
        last_temp = self._current_temp

        first_entry = None
        for item in history:
            hours = (last_time - datetime.fromisoformat(item["timestamp"])).total_seconds() / 3600
            if hours >= 1:
                first_entry = item

        if first_entry is None:
            return None
        
        first_time = datetime.fromisoformat(first_entry["timestamp"])
        temp_diff = last_temp - first_entry["temperature"]
        time_diff_minutes = (last_time - first_time).total_seconds() / 60
        time_diff_hours = (last_time - first_time).total_seconds() / 3600
        
        return round(temp_diff / time_diff_hours,2) if time_diff_minutes > TEMP_HISTO_MINUTES else None
    
    def get_last_action_temperature_variation(self,action):
        history = self.get_actions_history()
        action_data = None
        if history is not None:
            history.reverse()
            for item in history:
                if item["action"] == action and item["start_temp"] is not None and item["stop_temp"] is not None:
                    action_data = item
                    break
        if action_data is not None:
            temp_diff = action_data["stop_temp"] - action_data["start_temp"]
            time_diff_hours = (action_data["stop_time"] - action_data["start_time"]).total_seconds() / 3600
            return {
                "temperature_variation": round(temp_diff / time_diff_hours,2),
                "action_data": action_data
            }
        
        return None

