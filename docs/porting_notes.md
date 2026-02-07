# Porting Notes — Fermax Blue API (from `open_door.py` reference)

This document summarises the working API behaviour extracted from
`fermax-blue-intercom/open_door.py` and how it maps to the
Home Assistant integration rewrite.

---

## 1. Authentication

| Item | Value |
|---|---|
| **OAuth endpoint** | `POST https://oauth-pro-duoxme.fermax.io/oauth/token` |
| **Content-Type** | `application/x-www-form-urlencoded` |
| **Authorization header** | `Basic ZHB2N2lxejZlZTVtYXptMWlxOWR3MWQ0MnNseXV0NDhrajBtcDVmdm81OGo1aWg6Yzd5bGtxcHVqd2FoODV5aG5wcnYwd2R2eXp1dGxjbmt3NHN6OTBidWxkYnVsazE=` |
| **Password grant** | `grant_type=password&username=…&password=…` |
| **Refresh grant** | `grant_type=refresh_token&refresh_token=…` |

### Response fields

```json
{
  "access_token": "…",
  "token_type": "bearer",
  "refresh_token": "…",
  "expires_in": 3600,
  "scope": "…",
  "jti": "…"
}
```

### Token validity

- `expires_at = now_utc + timedelta(seconds=expires_in)`
- Token needs refresh when `now_utc >= expires_at` or `token_data` is `None`.
- On refresh failure, fall back to full re-auth with username/password.

---

## 2. Common request headers (all API calls)

```python
COMMON_HEADERS = {
    "app-version": "3.2.1",
    "accept-language": "en-ES;q=1.0, es-ES;q=0.9, ru-ES;q=0.8",
    "phone-os": "16.4",
    "user-agent": "Blue/3.2.1 (com.fermax.bluefermax; build:3; iOS 16.4.0) Alamofire/3.2.1",
    "phone-model": "iPad14,5",
    "app-build": "3",
}
```

Authenticated API calls add:

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

---

## 3. Endpoints

| Purpose | Method | URL |
|---|---|---|
| Get pairings (devices + doors) | GET | `https://pro-duoxme.fermax.io/pairing/api/v3/pairings/me` |
| Get device info | GET | `https://pro-duoxme.fermax.io/deviceaction/api/v1/device/{device_id}` |
| Open door (directed) | POST | `https://pro-duoxme.fermax.io/deviceaction/api/v1/device/{device_id}/directed-opendoor` |
| F1 command | POST | `https://pro-duoxme.fermax.io/deviceaction/api/v1/device/{device_id}/f1` |
| Get user info | GET | `https://pro-duoxme.fermax.io/user/api/v1/users/me` |

### Open door body

```json
{ "block": 0, "subblock": 0, "number": 0 }
```

Values come from `accessDoorMap[name].accessId`.

### F1 body

```json
{ "deviceID": "<device_id>" }
```

---

## 4. Data models (from API JSON)

### Pairing

```
deviceId, tag, status, updatedAt, createdAt, appBuild, appVersion,
phoneModel, phoneOS, home, address, master,
accessDoorMap: { "<name>": { title, visible, accessId: { block, subblock, number } } }
```

### DeviceInfo

```
deviceId, connectionState, status, installationId, family, type, subtype,
numBlock, numSubblock, unitNumber, connectable, iccid, divertService,
photocaller, wirelessSignal, blueStream, phone, monitor,
monitorOrGuardUnit, terminal, panelOrEdibox, panel, streamingMode
```

---

## 5. Removed / not ported features

| Feature | Reason |
|---|---|
| FCM push notifications (call started/ended) | Not in reference script; requires `rustPlusPushReceiver` and Firebase credentials |
| Camera `getLastPicture` | Endpoint unknown from reference script |
| `--no-cache`, `--reauth` CLI flags | Handled internally by the HA integration (token caching via HA Store, reauth via config flow) |

---

## 6. Integration mapping

| Old (`bluecon` library) | New (`FermaxClient`) |
|---|---|
| `BlueConAPI.create(username, password, …)` | `FermaxClient(username, password, session)` + `async_login()` |
| `BlueConAPI.create_already_authed(…)` | `client.set_token_data(cached)` + `async_login()` |
| `bluecon.getPairings()` | `client.async_get_pairings()` |
| `bluecon.getDeviceInfo(id)` | `client.async_get_device_info(id)` |
| `bluecon.openDoor(id, door)` | `client.async_open_door(id, access_id)` |
| `bluecon.getLastPicture(id)` | *not ported* |
| `bluecon.startNotificationListener()` | *not ported (FCM)* |
| `ConfigFolderOAuthTokenStorage` (HA Store) | Inline `Store` usage in `__init__.py` |

### Config flow simplification

- **Removed**: `client_id`, `client_secret`, `api_key`, `senderId`, `appId`, `projectId`, `packageName`
- **Kept**: `username`, `password`
- The OAuth Basic-auth header is hardcoded (same as the mobile app uses).
