"""Fermax Blue API Client."""
import logging
import json
import datetime
from typing import Optional, List, Dict, Any, Callable
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import HomeAssistantError, ConfigEntryAuthFailed

LOGGER = logging.getLogger(__name__)

BASE_URL = "https://pro-duoxme.fermax.io"
AUTH_URL = "https://oauth-pro-duoxme.fermax.io/oauth/token"

# Basic Auth Header for Fermax App
# "dpv7iqz6ee5mazm1iq9dw1d42slyut48kj0mp5fvo58j5ih:c7ylkqpujwah85yhnprv0wdvyzutlcnkw4sz90buldbulk1" base64 encoded
CLIENT_ID_SECRET_B64 = "ZHB2N2lxejZlZTVtYXptMWlxOWR3MWQ0MnNseXV0NDhrajBtcDVmdm81OGo1aWg6Yzd5bGtxcHVqd2FoODV5aG5wcnYwd2R2eXp1dGxjbmt3NHN6OTBidWxkYnVsazE="

COMMON_HEADERS = {
    "app-version": "3.2.1",
    "accept-language": "en-ES;q=1.0, es-ES;q=0.9, ru-ES;q=0.8",
    "phone-os": "16.4",
    "user-agent": "Blue/3.2.1 (com.fermax.bluefermax; build:3; iOS 16.4.0) Alamofire/3.2.1",
    "phone-model": "iPad14,5",
    "app-build": "3",
}

class FermaxError(HomeAssistantError):
    """Base error for Fermax."""

class FermaxAuthError(FermaxError):
    """Authentication error."""

class FermaxConnectionError(FermaxError):
    """Connection error."""

class FermaxClient:
    """Fermax Blue API Client."""

    def __init__(
        self, 
        session: aiohttp.ClientSession, 
        token_data: Optional[Dict[str, Any]] = None,
        save_token_callback: Optional[Callable[[Dict[str, Any]], Any]] = None
    ):
        """Initialize the client."""
        self._session = session
        self._token_data = token_data
        self._save_token_callback = save_token_callback

    @property
    def token_valid(self) -> bool:
        """Check if token is present and not expired."""
        if not self._token_data:
            return False
        
        expires_at = self._token_data.get("expires_at")
        if not expires_at:
            return False
            
        # Handle ISO string or datetime object
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.datetime.fromisoformat(expires_at)
            except ValueError:
                return False
        
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            
        return datetime.datetime.now(datetime.timezone.utc) < expires_at

    async def async_login(self, username: str, password: str) -> None:
        """Login with username and password."""
        headers = {
            "Authorization": f"Basic {CLIENT_ID_SECRET_B64}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "password",
            "username": username,
            "password": password,
        }

        try:
            async with self._session.post(AUTH_URL, headers=headers, data=data) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    LOGGER.error("Login failed: %s - %s", resp.status, text)
                    raise FermaxAuthError(f"Login failed: {resp.status}")
                
                json_data = await resp.json()
                self._process_token_response(json_data)
                
        except aiohttp.ClientError as err:
            raise FermaxConnectionError(f"Connection error during login: {err}") from err

    async def async_refresh_token(self) -> None:
        """Refresh the access token."""
        if not self._token_data or "refresh_token" not in self._token_data:
            raise FermaxAuthError("No refresh token available")

        headers = {
            "Authorization": f"Basic {CLIENT_ID_SECRET_B64}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._token_data["refresh_token"],
        }

        try:
            async with self._session.post(AUTH_URL, headers=headers, data=data) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    LOGGER.error("Token refresh failed: %s - %s", resp.status, text)
                    raise FermaxAuthError(f"Token refresh failed: {resp.status}")
                
                json_data = await resp.json()
                self._process_token_response(json_data)
                
        except aiohttp.ClientError as err:
            raise FermaxConnectionError(f"Connection error during refresh: {err}") from err

    def _process_token_response(self, data: Dict[str, Any]) -> None:
        """Process and save token data."""
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_in = data.get("expires_in", 3600)
        expires_at = now + datetime.timedelta(seconds=expires_in)
        
        self._token_data = {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", self._token_data.get("refresh_token") if self._token_data else None),
            "expires_at": expires_at.isoformat(),
            "token_type": data.get("token_type", "Bearer"),
        }
        
        if self._save_token_callback:
            self._save_token_callback(self._token_data)

    async def _async_request(self, method: str, url: str, **kwargs) -> Any:
        """Make an authenticated request with retry logic."""
        if not self.token_valid:
            try:
                await self.async_refresh_token()
            except FermaxAuthError:
                # If refresh fails, we might need re-login, but we can't do that without creds.
                # Caller should handle ConfigEntryAuthFailed
                raise ConfigEntryAuthFailed("Token expired and refresh failed")

        headers = kwargs.pop("headers", {})
        headers.update(COMMON_HEADERS)
        headers["Authorization"] = f"Bearer {self._token_data['access_token']}"
        headers["Content-Type"] = "application/json"

        try:
            async with self._session.request(method, url, headers=headers, **kwargs) as resp:
                if resp.status == 401:
                    # Token might be invalid, try refresh once
                    LOGGER.info("Received 401, trying to refresh token")
                    try:
                        await self.async_refresh_token()
                        # Update header with new token
                        headers["Authorization"] = f"Bearer {self._token_data['access_token']}"
                        async with self._session.request(method, url, headers=headers, **kwargs) as resp2:
                            if resp2.status == 401:
                                raise ConfigEntryAuthFailed("Authentication failed after refresh")
                            resp2.raise_for_status()
                            if resp2.headers.get("Content-Type", "").startswith("application/json"):
                                return await resp2.json()
                            return await resp2.text()
                    except FermaxAuthError as err:
                        raise ConfigEntryAuthFailed(f"Re-authentication required: {err}") from err
                
                resp.raise_for_status()
                if resp.headers.get("Content-Type", "").startswith("application/json"):
                    return await resp.json()
                return await resp.text()
                
        except aiohttp.ClientError as err:
            raise FermaxConnectionError(f"Request error: {err}") from err

    async def async_get_pairings(self) -> List[Dict[str, Any]]:
        """Get list of paired devices."""
        url = f"{BASE_URL}/pairing/api/v3/pairings/me"
        return await self._async_request("GET", url)

    async def async_open_door(self, device_id: str, access_id: Dict[str, int]) -> None:
        """Open door."""
        url = f"{BASE_URL}/deviceaction/api/v1/device/{device_id}/directed-opendoor"
        await self._async_request("POST", url, json=access_id)

    async def async_f1(self, device_id: str) -> None:
        """Trigger F1 function."""
        url = f"{BASE_URL}/deviceaction/api/v1/device/{device_id}/f1"
        await self._async_request("POST", url, json={"deviceID": device_id})

    async def async_get_device_info(self, device_id: str) -> Dict[str, Any]:
        """Get device info."""
        url = f"{BASE_URL}/deviceaction/api/v1/device/{device_id}"
        return await self._async_request("GET", url)
