from typing import Any
from homeassistant.config_entries import ConfigFlow, OptionsFlow, ConfigEntry
from homeassistant.data_entry_flow import FlowResult, AbortFlow
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_API_KEY,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
)
from homeassistant.core import callback, async_get_hass
import voluptuous as vol

from .fermax_api import FermaxClient, FermaxAuthError, FermaxConnectionError, FermaxResponseError
from custom_components.bluecon.const import CONF_LOCK_STATE_RESET, CONF_PACKAGE_NAME, CONF_APP_ID, CONF_PROJECT_ID, CONF_SENDER_ID, CONF_PAIRINGS

from . import DOMAIN

class BlueConConfigFlow(ConfigFlow, domain = DOMAIN):
    VERSION = 7

    def __init__(self) -> None:
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        error_info: dict[str, str] = {}
        hass = async_get_hass()

        if user_input is not None:
            try:
                client = FermaxClient(
                    hass,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
                await client.async_login()
                pairings = await client.async_get_devices()

                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title = user_input[CONF_USERNAME], 
                    data = {
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_CLIENT_ID: user_input.get(CONF_CLIENT_ID, ""),
                        CONF_CLIENT_SECRET: user_input.get(CONF_CLIENT_SECRET, ""),
                        CONF_SENDER_ID: user_input.get(CONF_SENDER_ID, None),
                        CONF_API_KEY: user_input.get(CONF_API_KEY, None),
                        CONF_PROJECT_ID: user_input.get(CONF_PROJECT_ID, None),
                        CONF_APP_ID: user_input.get(CONF_APP_ID, None),
                        CONF_PACKAGE_NAME: user_input.get(CONF_PACKAGE_NAME, None)
                    }, 
                    options = {
                        CONF_LOCK_STATE_RESET: 5,
                        CONF_PAIRINGS: _serialize_pairings(pairings),
                    }
                )
            except AbortFlow as e:
                raise e
            except FermaxAuthError:
                error_info['base'] = 'invalid_auth'
            except FermaxConnectionError:
                error_info['base'] = 'cannot_connect'
            except FermaxResponseError:
                error_info['base'] = 'unexpected_response'
            except Exception:
                error_info['base'] = 'unknown'
        
        return self.async_show_form(
            step_id = "user",
            data_schema = vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_CLIENT_ID): str,
                vol.Optional(CONF_CLIENT_SECRET): str,
                vol.Optional(CONF_API_KEY): str,
                vol.Optional(CONF_SENDER_ID): int,
                vol.Optional(CONF_APP_ID): str,
                vol.Optional(CONF_PROJECT_ID): str,
                vol.Optional(CONF_PACKAGE_NAME): str
            }),
            errors = error_info
        )
    
    async def async_step_reauth(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reconfigure(user_input)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        error_info: dict[str, str] = {}

        if user_input is not None:
            try:
                entry = self._reauth_entry or self.hass.config_entries.async_entry_for_domain_unique_id(
                    DOMAIN,
                    user_input[CONF_USERNAME],
                )
                client = FermaxClient(
                    self.hass,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
                await client.async_login()
                pairings = await client.async_get_devices()

                self.hass.config_entries.async_update_entry(
                    entry = entry, 
                    data = {
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_CLIENT_ID: user_input.get(CONF_CLIENT_ID, ""),
                        CONF_CLIENT_SECRET: user_input.get(CONF_CLIENT_SECRET, ""),
                        CONF_SENDER_ID: user_input.get(CONF_SENDER_ID, None),
                        CONF_API_KEY: user_input.get(CONF_API_KEY, None),
                        CONF_PROJECT_ID: user_input.get(CONF_PROJECT_ID, None),
                        CONF_APP_ID: user_input.get(CONF_APP_ID, None),
                        CONF_PACKAGE_NAME: user_input.get(CONF_PACKAGE_NAME, None)
                    },
                    options={
                        **(entry.options or {}),
                        CONF_PAIRINGS: _serialize_pairings(pairings),
                    },
                )
                
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")
            except AbortFlow as e:
                raise e
            except FermaxAuthError:
                error_info['base'] = 'invalid_auth'
            except FermaxConnectionError:
                error_info['base'] = 'cannot_connect'
            except FermaxResponseError:
                error_info['base'] = 'unexpected_response'
            except Exception:
                error_info['base'] = 'unknown'
        
        return self.async_show_form(
            step_id = "reconfigure",
            data_schema = vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_CLIENT_ID): str,
                vol.Optional(CONF_CLIENT_SECRET): str,
                vol.Optional(CONF_API_KEY): str,
                vol.Optional(CONF_SENDER_ID): int,
                vol.Optional(CONF_APP_ID): str,
                vol.Optional(CONF_PROJECT_ID): str,
                vol.Optional(CONF_PACKAGE_NAME): str
            }),
            errors = error_info
        )
    
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return BlueConOptionsFlow(config_entry)

class BlueConOptionsFlow(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry
    
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        error_info: dict[str, str] = {}

        lockTimeout = self.config_entry.options.get(CONF_LOCK_STATE_RESET, 5)

        if user_input is not None:
            if user_input[CONF_LOCK_STATE_RESET] >= 0:
                self.hass.config_entries.async_update_entry(self.config_entry, options=user_input)
                return self.async_create_entry(title=None, data=None)
            else:
                error_info['base'] = 'negative_value'
        
        return self.async_show_form(
            step_id = "init", 
            data_schema = vol.Schema({
                vol.Required(CONF_LOCK_STATE_RESET, default = lockTimeout): int
            }),
            errors=error_info
        )


def _serialize_pairings(pairings) -> list[dict[str, Any]]:
    result = []
    for pairing in pairings:
        access_doors = []
        for name, door in pairing.accessDoorMap.items():
            access_doors.append(
                {
                    "name": name,
                    "title": door.title,
                    "visible": door.visible,
                    "block": door.block,
                    "subblock": door.subBlock,
                    "number": door.number,
                }
            )
        result.append(
            {
                "id": pairing.id,
                "deviceId": pairing.deviceId,
                "tag": pairing.tag,
                "status": pairing.status,
                "accessDoors": access_doors,
                "master": pairing.master,
            }
        )
    return result
