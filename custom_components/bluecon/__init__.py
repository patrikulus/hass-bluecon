"""The BlueCon integration."""
import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .fermax_api import FermaxClient, FermaxAuthError

LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = [Platform.LOCK] # Removed others for now as they might depend on features not in the script

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BlueCon from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.token")

    token_data = await store.async_load()

    def save_token(token):
        hass.async_create_task(store.async_save(token))

    client = FermaxClient(session, token_data, save_token)

    try:
        if not client.token_valid:
            username = entry.data.get(CONF_USERNAME)
            password = entry.data.get(CONF_PASSWORD)
            if username and password:
                await client.async_login(username, password)
            else:
                LOGGER.warning("No credentials found for re-authentication")
    except FermaxAuthError as err:
        LOGGER.error("Authentication failed during setup: %s", err)
        return False

    hass.data[DOMAIN][entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
