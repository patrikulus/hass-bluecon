"""Fermax Blue (BlueCon) integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import CONF_LOCK_STATE_RESET, DOMAIN
from .fermax_api import (
    FermaxAuthError,
    FermaxClient,
    FermaxConnectionError,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.LOCK,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.BUTTON,
]

TOKEN_STORE_VERSION = 1


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fermax Blue from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    username: str | None = entry.data.get(CONF_USERNAME)
    password: str | None = entry.data.get(CONF_PASSWORD)

    if not username or not password:
        raise ConfigEntryAuthFailed(
            "Credentials missing – please reconfigure the integration"
        )

    session = async_get_clientsession(hass)
    store = Store(hass, TOKEN_STORE_VERSION, f"{DOMAIN}.token.{entry.entry_id}")

    async def _save_token(data: dict) -> None:
        await store.async_save(data)

    client = FermaxClient(username, password, session, on_token_update=_save_token)

    # Restore cached token (if any)
    cached = await store.async_load()
    client.set_token_data(cached)

    # Authenticate (will use cache / refresh / full re-auth as needed)
    try:
        await client.async_login()
    except FermaxAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except FermaxConnectionError as err:
        raise ConfigEntryNotReady(str(err)) from err

    hass.data[DOMAIN][entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_update_listener))

    return True


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Migrate older config entry versions to current."""
    _LOGGER.debug(
        "Migrating config entry from version %s", config_entry.version
    )

    if config_entry.version < 7:
        # Versions ≤6 used the old bluecon library with different stored
        # data.  We cannot recover username/password from the old format,
        # so we clear data and let the reauth flow collect fresh
        # credentials.  Options (lock timeout) are preserved.
        hass.config_entries.async_update_entry(
            config_entry,
            data={},
            options=config_entry.options or {CONF_LOCK_STATE_RESET: 5},
            version=7,
        )
        _LOGGER.info(
            "Migrated config entry to v7 – re-authentication required"
        )

    return True
