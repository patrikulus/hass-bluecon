"""Camera platform for Fermax Blue (BlueCon).

NOTE: This platform is currently **disabled** (not listed in PLATFORMS).
The ``getLastPicture`` API endpoint used by the old ``bluecon`` library
is not available in the reference implementation.  This file is kept as
a placeholder for future re-activation once the endpoint is identified.
"""

from __future__ import annotations

import logging

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_MANUFACTURER, DOMAIN, HASS_BLUECON_VERSION
from .fermax_api import FermaxClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up camera entities – currently a no-op."""
    # Camera functionality requires the getLastPicture endpoint which is
    # not yet known.  See docs/porting_notes.md for details.
    async_add_entities([])
