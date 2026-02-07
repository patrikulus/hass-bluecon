from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import asyncio
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

AUTH_URL = "https://oauth-pro-duoxme.fermax.io/oauth/token"
BASE_URL = "https://pro-duoxme.fermax.io"

COMMON_HEADERS = {
    "app-version": "3.2.1",
    "accept-language": "en-ES;q=1.0, es-ES;q=0.9, ru-ES;q=0.8",
    "phone-os": "16.4",
    "user-agent": "Blue/3.2.1 (com.fermax.bluefermax; build:3; iOS 16.4.0) Alamofire/3.2.1",
    "phone-model": "iPad14,5",
    "app-build": "3",
}

AUTH_HEADERS = {
    "Authorization": "Basic ZHB2N2lxejZlZTVtYXptMWlxOWR3MWQ0MnNseXV0NDhrajBtcDVmdm81OGo1aWg6Yzd5bGtxcHVqd2FoODV5aG5wcnYwd2R2eXp1dGxjbmt3NHN6OTBidWxkYnVsazE=",
    "Content-Type": "application/x-www-form-urlencoded",
}

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=10)
STORAGE_VERSION = 1


class FermaxError(HomeAssistantError):
    """Base error for Fermax API failures."""


class FermaxAuthError(ConfigEntryAuthFailed):
    """Raised when authentication fails."""


class FermaxConnectionError(FermaxError):
    """Raised when the API cannot be reached."""


class FermaxResponseError(FermaxError):
    """Raised for unexpected API responses."""


@dataclass(frozen=True)
class TokenData:
    access_token: str
    refresh_token: str
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return datetime.now(tz=timezone.utc) >= self.expires_at

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TokenData":
        expires_at = datetime.fromisoformat(data["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=expires_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat(),
        }


@dataclass(frozen=True)
class AccessId:
    block: int
    subblock: int
    number: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AccessId":
        return cls(
            block=int(data["block"]),
            subblock=int(data["subblock"]),
            number=int(data["number"]),
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "block": self.block,
            "subblock": self.subblock,
            "number": self.number,
        }


@dataclass(frozen=True)
class AccessDoor:
    title: str
    block: int
    subBlock: int
    number: int
    visible: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AccessDoor":
        access_id = data["accessId"]
        return cls(
            title=data.get("title", ""),
            block=int(access_id["block"]),
            subBlock=int(access_id["subblock"]),
            number=int(access_id["number"]),
            visible=bool(data.get("visible", True)),
        )

    @property
    def access_id(self) -> AccessId:
        return AccessId(block=self.block, subblock=self.subBlock, number=self.number)


@dataclass(frozen=True)
class Pairing:
    id: str
    deviceId: str
    tag: str
    status: str
    updated_at: datetime
    created_at: datetime
    accessDoorMap: dict[str, AccessDoor]
    master: bool


@dataclass(frozen=True)
class DeviceInfo:
    deviceId: str
    connectionState: str
    status: str
    family: str
    type: str
    subType: str
    photoCaller: bool
    wirelessSignal: int


class FermaxClient:
    def __init__(self, hass: HomeAssistant, username: str, password: str, entry_id: str | None = None):
        self._hass = hass
        self._username = username
        self._password = password
        self._session = async_get_clientsession(hass)
        self._token_data: TokenData | None = None
        self._token_loaded = False
        self._login_lock = asyncio.Lock()
        self._store: Store | None = None
        if entry_id:
            self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.token.{entry_id}")

    async def async_login(self, force: bool = False) -> None:
        async with self._login_lock:
            await self._async_load_token()

            if not force and self._token_data and not self._token_data.is_expired:
                return

            if not force and self._token_data and self._token_data.refresh_token:
                try:
                    await self._async_refresh_token()
                    return
                except FermaxAuthError:
                    LOGGER.debug("Refresh token failed, falling back to password grant.")

            await self._async_password_grant()

    async def async_get_devices(self) -> list[Pairing]:
        payload = await self._async_request_json(
            "get",
            "/pairing/api/v3/pairings/me",
        )
        if not isinstance(payload, list):
            raise FermaxResponseError("Unexpected pairings response format.")
        return self._parse_pairings(payload)

    async def async_get_access_ids(self, device_id: str) -> list[AccessId]:
        pairings = await self.async_get_devices()
        for pairing in pairings:
            if pairing.deviceId == device_id:
                return [door.access_id for door in pairing.accessDoorMap.values()]
        return []

    async def async_get_device_info(self, device_id: str) -> DeviceInfo:
        payload = await self._async_request_json(
            "get",
            f"/deviceaction/api/v1/device/{device_id}",
        )
        return DeviceInfo(
            deviceId=payload["deviceId"],
            connectionState=payload["connectionState"],
            status=payload["status"],
            family=payload["family"],
            type=payload["type"],
            subType=payload["subtype"],
            photoCaller=payload.get("photocaller", False),
            wirelessSignal=payload.get("wirelessSignal", 0),
        )

    async def async_open_door(self, device_id: str, access_id: AccessId | AccessDoor | dict[str, Any]) -> None:
        payload = self._normalize_access_id(access_id)
        await self._async_request(
            "post",
            f"/deviceaction/api/v1/device/{device_id}/directed-opendoor",
            json=payload,
        )

    async def async_f1(self, device_id: str) -> None:
        await self._async_request(
            "post",
            f"/deviceaction/api/v1/device/{device_id}/f1",
            json={"deviceID": device_id},
        )

    async def async_get_last_picture(self, device_id: str) -> bytes | None:
        LOGGER.debug("Last picture endpoint not implemented; returning None.")
        return None

    async def _async_load_token(self) -> None:
        if self._token_loaded or not self._store:
            self._token_loaded = True
            return
        data = await self._store.async_load()
        if data:
            try:
                self._token_data = TokenData.from_dict(data)
            except (KeyError, ValueError) as err:
                LOGGER.debug("Stored token data is invalid: %s", err)
        self._token_loaded = True

    async def _async_save_token(self) -> None:
        if not self._store or not self._token_data:
            return
        await self._store.async_save(self._token_data.to_dict())

    async def _async_password_grant(self) -> None:
        if not self._username or not self._password:
            raise FermaxAuthError("Missing Fermax credentials.")
        token_data = await self._async_auth_request(
            {
                "grant_type": "password",
                "username": self._username,
                "password": self._password,
            }
        )
        self._token_data = token_data
        await self._async_save_token()

    async def _async_refresh_token(self) -> None:
        if not self._token_data or not self._token_data.refresh_token:
            raise FermaxAuthError("Missing refresh token.")
        token_data = await self._async_auth_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": self._token_data.refresh_token,
            }
        )
        self._token_data = token_data
        await self._async_save_token()

    async def _async_auth_request(self, data: dict[str, Any]) -> TokenData:
        try:
            async with self._session.post(
                AUTH_URL,
                headers=AUTH_HEADERS,
                data=data,
                timeout=DEFAULT_TIMEOUT,
            ) as response:
                payload = await response.json(content_type=None)
        except aiohttp.ClientError as err:
            raise FermaxConnectionError("Cannot connect to Fermax auth endpoint.") from err

        if response.status >= 400:
            error = payload.get("error", "auth_error")
            description = payload.get("error_description", "")
            message = f"{error} {description}".strip()
            raise FermaxAuthError(message)

        try:
            expires_in = int(payload["expires_in"])
        except (KeyError, ValueError, TypeError) as err:
            raise FermaxResponseError("Auth response missing expires_in.") from err

        expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=expires_in)
        return TokenData(
            access_token=payload["access_token"],
            refresh_token=payload["refresh_token"],
            expires_at=expires_at,
        )

    def _auth_headers(self) -> dict[str, str]:
        if not self._token_data:
            raise FermaxAuthError("No auth token available.")
        return {
            "Authorization": f"Bearer {self._token_data.access_token}",
            **COMMON_HEADERS,
        }

    async def _async_request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        return await self._async_request(method, path, expect_json=True, **kwargs)

    async def _async_request(
        self,
        method: str,
        path: str,
        retry_on_401: bool = True,
        expect_json: bool = False,
        **kwargs: Any,
    ) -> Any:
        await self.async_login()
        headers = kwargs.pop("headers", {})
        request_headers = {
            **self._auth_headers(),
            **headers,
        }
        try:
            async with self._session.request(
                method,
                f"{BASE_URL}{path}",
                headers=request_headers,
                timeout=DEFAULT_TIMEOUT,
                **kwargs,
            ) as response:
                if response.status == 401 and retry_on_401:
                    await response.release()
                    await self.async_login(force=True)
                    return await self._async_request(
                        method,
                        path,
                        retry_on_401=False,
                        expect_json=expect_json,
                        headers=headers,
                        **kwargs,
                    )

                if response.status >= 400:
                    text = await response.text()
                    raise FermaxResponseError(f"API error {response.status}: {text}")

                if expect_json:
                    try:
                        return await response.json(content_type=None)
                    except (aiohttp.ContentTypeError, ValueError) as err:
                        text = await response.text()
                        raise FermaxResponseError(f"Unexpected response: {text}") from err

                return None
        except aiohttp.ClientError as err:
            raise FermaxConnectionError("Cannot connect to Fermax API.") from err

    @staticmethod
    def _parse_pairings(payload: list[dict[str, Any]]) -> list[Pairing]:
        pairings: list[Pairing] = []
        for pairing in payload:
            access_door_map: dict[str, AccessDoor] = {}
            for key, value in pairing.get("accessDoorMap", {}).items():
                access_door_map[key] = AccessDoor.from_dict(value)

            pairings.append(
                Pairing(
                    id=pairing["id"],
                    deviceId=pairing["deviceId"],
                    tag=pairing["tag"],
                    status=pairing["status"],
                    updated_at=datetime.fromtimestamp(pairing["updatedAt"] / 1000, tz=timezone.utc),
                    created_at=datetime.fromtimestamp(pairing["createdAt"] / 1000, tz=timezone.utc),
                    accessDoorMap=access_door_map,
                    master=pairing.get("master", False),
                )
            )
        return pairings

    @staticmethod
    def _normalize_access_id(access_id: AccessId | AccessDoor | dict[str, Any]) -> dict[str, int]:
        if isinstance(access_id, AccessId):
            return access_id.to_dict()
        if isinstance(access_id, AccessDoor):
            return access_id.access_id.to_dict()
        if isinstance(access_id, dict):
            if "subblock" in access_id:
                return {
                    "block": int(access_id["block"]),
                    "subblock": int(access_id["subblock"]),
                    "number": int(access_id["number"]),
                }
            return {
                "block": int(access_id["block"]),
                "subblock": int(access_id.get("subBlock", access_id.get("sub_block"))),
                "number": int(access_id["number"]),
            }
        raise FermaxResponseError("Unsupported access_id format.")
