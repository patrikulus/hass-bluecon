"""Config flow for Fermax Blue (BlueCon)."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LOCK_STATE_RESET, DOMAIN
from .fermax_api import FermaxAuthError, FermaxClient, FermaxConnectionError

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class BlueConConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle initial setup and re-authentication."""

    VERSION = 7

    # ---- Initial setup ---------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial config step (username + password)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            error = await self._async_validate_credentials(username, password)
            if error is None:
                await self.async_set_unique_id(username)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=username,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                    options={CONF_LOCK_STATE_RESET: 5},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    # ---- Re-authentication (after migration or token failure) ------------

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Start the reauth flow when credentials are missing / invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask the user to re-enter credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            error = await self._async_validate_credentials(username, password)
            if error is None:
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                if entry:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                        },
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            errors["base"] = error

        # Pre-fill username from the existing unique_id when possible
        default_user = self.context.get("unique_id", "")
        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=default_user): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
        )

    # ---- Reconfigure (user-initiated) ------------------------------------

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to update credentials without removing the entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            error = await self._async_validate_credentials(username, password)
            if error is None:
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                if entry:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                        },
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    # ---- Validation helper -----------------------------------------------

    async def _async_validate_credentials(
        self, username: str, password: str
    ) -> str | None:
        """Try to log in. Return an error key or None on success."""
        session = async_get_clientsession(self.hass)
        client = FermaxClient(username, password, session)
        try:
            await client.async_login(force=True)
        except FermaxAuthError:
            return "invalid_auth"
        except FermaxConnectionError:
            return "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error during credential validation")
            return "unknown"
        return None

    # ---- Options flow ----------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> BlueConOptionsFlow:
        """Get the options flow handler."""
        return BlueConOptionsFlow(config_entry)


class BlueConOptionsFlow(OptionsFlow):
    """Handle integration options (lock timeout)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show options form."""
        errors: dict[str, str] = {}
        lock_timeout = self.config_entry.options.get(CONF_LOCK_STATE_RESET, 5)

        if user_input is not None:
            if user_input[CONF_LOCK_STATE_RESET] >= 0:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, options=user_input
                )
                return self.async_create_entry(title=None, data=None)
            errors["base"] = "negative_value"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required(CONF_LOCK_STATE_RESET, default=lock_timeout): int}
            ),
            errors=errors,
        )
