"""Fermax Blue API client for Home Assistant.

Ported from fermax-blue-intercom/open_door.py.  Uses aiohttp (HA's
preferred async HTTP library) and is completely independent of the old
``bluecon`` PyPI package.
"""

from __future__ import annotations

import datetime
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Coroutine

import aiohttp

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class FermaxAuthError(Exception):
    """Raised when authentication / authorisation fails (401/403)."""


class FermaxApiError(Exception):
    """Raised when a non-auth API call fails (4xx/5xx)."""


class FermaxConnectionError(Exception):
    """Raised on network-level failures."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TokenData:
    """In-memory representation of an OAuth token pair."""

    access_token: str
    refresh_token: str
    expires_at: datetime.datetime


@dataclass
class AccessId:
    """Block/subblock/number triplet that identifies a door relay."""

    block: int
    subblock: int
    number: int

    def to_dict(self) -> dict[str, int]:
        return {"block": self.block, "subblock": self.subblock, "number": self.number}


@dataclass
class AccessDoor:
    """A single door on a device."""

    title: str
    access_id: AccessId
    visible: bool


@dataclass
class Pairing:
    """A paired device with its doors."""

    device_id: str
    tag: str
    access_door_map: dict[str, AccessDoor]


@dataclass
class DeviceInfo:
    """Subset of device metadata returned by the API."""

    device_id: str
    connection_state: str
    family: str
    type: str
    subtype: str
    photocaller: bool
    wireless_signal: int


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

# Type alias for the token-update callback
TokenUpdateCallback = Callable[[dict], Coroutine[Any, Any, None]]


class FermaxClient:
    """Async client for the Fermax Blue (duox-me) REST API."""

    AUTH_URL = "https://oauth-pro-duoxme.fermax.io/oauth/token"
    BASE_URL = "https://pro-duoxme.fermax.io"

    # Fixed Basic-auth credential identical to the official iOS app.
    AUTH_BASIC = (
        "Basic "
        "ZHB2N2lxejZlZTVtYXptMWlxOWR3MWQ0MnNseXV0NDhrajBtcDVmdm81OGo1aWg6"
        "Yzd5bGtxcHVqd2FoODV5aG5wcnYwd2R2eXp1dGxjbmt3NHN6OTBidWxkYnVsazE="
    )

    COMMON_HEADERS: dict[str, str] = {
        "app-version": "3.2.1",
        "accept-language": "en-ES;q=1.0, es-ES;q=0.9, ru-ES;q=0.8",
        "phone-os": "16.4",
        "user-agent": (
            "Blue/3.2.1 (com.fermax.bluefermax; build:3; iOS 16.4.0) "
            "Alamofire/3.2.1"
        ),
        "phone-model": "iPad14,5",
        "app-build": "3",
    }

    # ------------------------------------------------------------------
    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        on_token_update: TokenUpdateCallback | None = None,
    ) -> None:
        self._username = username
        self._password = password
        self._session = session
        self._on_token_update = on_token_update
        self._token_data: TokenData | None = None

    # ------------------------------------------------------------------
    # Token cache helpers (dict ↔ TokenData)
    # ------------------------------------------------------------------

    def set_token_data(self, data: dict | None) -> None:
        """Restore an in-memory token from a previously-cached dict."""
        if not data:
            self._token_data = None
            return
        try:
            expires_at = datetime.datetime.fromisoformat(data["expires_at"])
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            self._token_data = TokenData(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_at=expires_at,
            )
        except (KeyError, TypeError, ValueError):
            _LOGGER.warning("Could not restore cached token – will re-authenticate")
            self._token_data = None

    def get_token_data(self) -> dict | None:
        """Serialise the current token to a JSON-safe dict for caching."""
        if not self._token_data:
            return None
        return {
            "access_token": self._token_data.access_token,
            "refresh_token": self._token_data.refresh_token,
            "expires_at": self._token_data.expires_at.isoformat(),
        }

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _needs_refresh(self) -> bool:
        if not self._token_data:
            return True
        return (
            datetime.datetime.now(tz=datetime.timezone.utc)
            >= self._token_data.expires_at
        )

    async def async_login(self, force: bool = False) -> None:
        """Ensure the client holds a valid access token.

        * ``force=True`` always re-authenticates with username/password.
        * Otherwise: uses cached token → refreshes if expired → full
          re-auth on refresh failure.
        """
        if force or self._token_data is None:
            await self._async_auth()
            return

        if self._needs_refresh():
            try:
                await self._async_refresh_token()
            except (FermaxAuthError, FermaxApiError, FermaxConnectionError):
                _LOGGER.info("Token refresh failed – performing full re-auth")
                await self._async_auth()

    async def _async_auth(self) -> None:
        _LOGGER.debug("Authenticating with Fermax Blue API (password grant)")
        await self._async_oauth_request(
            {
                "grant_type": "password",
                "username": self._username,
                "password": self._password,
            }
        )

    async def _async_refresh_token(self) -> None:
        if not self._token_data:
            raise FermaxAuthError("No token data available for refresh")
        _LOGGER.debug("Refreshing Fermax Blue access token")
        await self._async_oauth_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": self._token_data.refresh_token,
            }
        )

    async def _async_oauth_request(self, form_data: dict) -> None:
        """POST to the OAuth endpoint and update internal token state."""
        headers = {
            "Authorization": self.AUTH_BASIC,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            async with self._session.post(
                self.AUTH_URL, data=form_data, headers=headers
            ) as resp:
                body = await resp.text()
                if resp.status >= 400:
                    try:
                        err = json.loads(body)
                        msg = (
                            f'{err.get("error", "unknown")} - '
                            f'{err.get("error_description", "")}'
                        )
                    except (json.JSONDecodeError, KeyError):
                        msg = f"HTTP {resp.status}: {body}"
                    raise FermaxAuthError(msg)

                parsed = json.loads(body)
                now = datetime.datetime.now(tz=datetime.timezone.utc)
                self._token_data = TokenData(
                    access_token=parsed["access_token"],
                    refresh_token=parsed["refresh_token"],
                    expires_at=now
                    + datetime.timedelta(seconds=parsed["expires_in"]),
                )
                if self._on_token_update:
                    await self._on_token_update(self.get_token_data())

        except aiohttp.ClientError as err:
            raise FermaxConnectionError(
                f"Connection error during auth: {err}"
            ) from err

    # ------------------------------------------------------------------
    # Authenticated request helper
    # ------------------------------------------------------------------

    def _get_api_headers(self) -> dict[str, str]:
        if not self._token_data:
            raise FermaxAuthError("Not authenticated – call async_login() first")
        return {
            "Authorization": f"Bearer {self._token_data.access_token}",
            "Content-Type": "application/json",
            **self.COMMON_HEADERS,
        }

    async def _async_api_request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
    ) -> Any:
        """Make an authenticated API request.

        On a 401 response the client will re-login and retry **once**.
        """
        url = f"{self.BASE_URL}{path}"

        for attempt in range(2):
            try:
                headers = self._get_api_headers()
                kwargs: dict[str, Any] = {"headers": headers}
                if body is not None:
                    kwargs["data"] = json.dumps(body)

                async with self._session.request(
                    method, url, **kwargs
                ) as resp:
                    if resp.status == 401 and attempt == 0:
                        _LOGGER.debug("Received 401 – refreshing token and retrying")
                        await self.async_login(force=True)
                        continue

                    resp_text = await resp.text()

                    if resp.status >= 400:
                        if resp.status in (401, 403):
                            raise FermaxAuthError(
                                f"Auth error {resp.status}: {resp_text}"
                            )
                        raise FermaxApiError(
                            f"API error {resp.status}: {resp_text}"
                        )

                    ct = resp.headers.get("Content-Type", "")
                    if resp_text and "json" in ct:
                        return json.loads(resp_text)
                    return resp_text

            except aiohttp.ClientError as err:
                raise FermaxConnectionError(
                    f"Connection error: {err}"
                ) from err

        # Should not be reached, but just in case:
        raise FermaxApiError("Request failed after retry")

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def async_get_pairings(self) -> list[Pairing]:
        """Return all device pairings for the authenticated user."""
        data = await self._async_api_request(
            "GET", "/pairing/api/v3/pairings/me"
        )

        pairings: list[Pairing] = []
        for p in data:
            access_door_map: dict[str, AccessDoor] = {}
            for name, door_data in p.get("accessDoorMap", {}).items():
                aid = door_data["accessId"]
                access_door_map[name] = AccessDoor(
                    title=door_data.get("title", name),
                    access_id=AccessId(
                        block=aid["block"],
                        subblock=aid["subblock"],
                        number=aid["number"],
                    ),
                    visible=door_data.get("visible", True),
                )
            pairings.append(
                Pairing(
                    device_id=p["deviceId"],
                    tag=p.get("tag", ""),
                    access_door_map=access_door_map,
                )
            )
        return pairings

    async def async_get_device_info(self, device_id: str) -> DeviceInfo:
        """Fetch metadata for a single device."""
        data = await self._async_api_request(
            "GET", f"/deviceaction/api/v1/device/{device_id}"
        )
        return DeviceInfo(
            device_id=data["deviceId"],
            connection_state=data.get("connectionState", "Unknown"),
            family=data.get("family", ""),
            type=data.get("type", ""),
            subtype=data.get("subtype", ""),
            photocaller=data.get("photocaller", False),
            wireless_signal=data.get("wirelessSignal", -1),
        )

    async def async_open_door(
        self, device_id: str, access_id: AccessId
    ) -> str:
        """Send a directed-opendoor command."""
        result = await self._async_api_request(
            "POST",
            f"/deviceaction/api/v1/device/{device_id}/directed-opendoor",
            body=access_id.to_dict(),
        )
        return str(result) if result else ""

    async def async_f1(self, device_id: str) -> str:
        """Send an F1 command to a device."""
        result = await self._async_api_request(
            "POST",
            f"/deviceaction/api/v1/device/{device_id}/f1",
            body={"deviceID": device_id},
        )
        return str(result) if result else ""
