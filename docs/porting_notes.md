# Porting Notes: Fermax Blue API

Reference implementation taken from `fermax-blue-intercom/open_door.py`.

## Authentication
- **Base URL**: `https://pro-duoxme.fermax.io`
- **Auth URL**: `https://oauth-pro-duoxme.fermax.io/oauth/token`
- **Auth Headers**:
  - `Authorization`: `Basic ZHB2N2lxejZlZTVtYXptMWlxOWR3MWQ0MnNseXV0NDhrajBtcDVmdm81OGo1aWg6Yzd5bGtxcHVqd2FoODV5aG5wcnYwd2R2eXp1dGxjbmt3NHN6OTBidWxkYnVsazE=`
  - `Content-Type`: `application/x-www-form-urlencoded`
- **Login Payload**:
  ```json
  {
    "grant_type": "password",
    "username": "...",
    "password": "..."
  }
  ```
- **Refresh Payload**:
  ```json
  {
    "grant_type": "refresh_token",
    "refresh_token": "..."
  }
  ```
- **Response**: Standard OAuth2 JSON (`access_token`, `refresh_token`, `expires_in`, etc.).

## Common Headers (Client Simulation)
The script simulates an iOS client:
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

## Device Discovery (Pairings)
- **Endpoint**: `GET /pairing/api/v3/pairings/me`
- **Headers**: Bearer token + Common Headers.
- **Response**: List of pairings. Each pairing has:
  - `deviceId` (string)
  - `accessDoorMap`: Dictionary where values contain `accessId` (block, subblock, number) and `title`.

## Actions
### Open Door
- **Endpoint**: `POST /deviceaction/api/v1/device/{device_id}/directed-opendoor`
- **Body**: JSON of AccessId
  ```json
  {
    "block": 1,
    "subblock": 0,
    "number": 1
  }
  ```
- **Response**: Text response (success check).

### F1 Function
- **Endpoint**: `POST /deviceaction/api/v1/device/{device_id}/f1`
- **Body**:
  ```json
  {
    "deviceID": "..."
  }
  ```

## Other Endpoints (Optional)
- **User Info**: `GET /user/api/v1/users/me`
- **Device Info**: `GET /deviceaction/api/v1/device/{device_id}`
