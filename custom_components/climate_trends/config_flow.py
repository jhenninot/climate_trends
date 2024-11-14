import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN  # Remplacez par le nom de domaine de votre component

class ComapConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}      
        if user_input is not None:
            return self.async_create_entry(
                title=user_input["name"],  # Nom personnalisé
                data={
                    "climate_entity": user_input["climate_entity"]
                }
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("name", default="Thermostat trends"): str,
                vol.Required("climate_entity"): selector.EntitySelector({
                    "domain": "climate"
                }),
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("climate_entity", default=self.config_entry.data.get("climate_entity")): selector.EntitySelector({
                    "domain": "climate"
                }),
            }),
            errors=errors,
        )
