"""Button platform for Fermax Blue (BlueCon).

Provides an F1 button per device – pressing it sends the F1 command
via the Fermax API (equivalent to the ``--f1`` flag in the reference
script).
"""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_MANUFACTURER, DOMAIN, HASS_BLUECON_VERSION
from .fermax_api import FermaxClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from a config entry."""
    client: FermaxClient = hass.data[DOMAIN][config.entry_id]

    pairings = await client.async_get_pairings()

    buttons: list[BlueConF1Button] = []
    for pairing in pairings:
        device_info = await client.async_get_device_info(pairing.device_id)
        buttons.append(
            BlueConF1Button(
                client=client,
                device_id=pairing.device_id,
                device_info=device_info,
            )
        )

    async_add_entities(buttons)


class BlueConF1Button(ButtonEntity):
    """Button that sends the F1 command to a Fermax device."""

    def __init__(self, client: FermaxClient, device_id: str, device_info) -> None:
        self._client = client
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_f1_button".lower()
        self.entity_id = f"{DOMAIN}.{self._attr_unique_id}".lower()
        self._attr_name = "F1"
        self._model = f"{device_info.type} {device_info.subtype} {device_info.family}"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.debug("Sending F1 command to device %s", self._device_id)
        await self._client.async_f1(self._device_id)

    @property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=f"{self._model} {self._device_id}",
            manufacturer=DEVICE_MANUFACTURER,
            model=self._model,
            sw_version=HASS_BLUECON_VERSION,
        )
