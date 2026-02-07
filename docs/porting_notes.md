<!--
# Fermax Blue porting notes (from fermax-blue-intercom/open_door.py)

## Auth
- Endpoint: POST https://oauth-pro-duoxme.fermax.io/oauth/token
- Headers:
  - Authorization: Basic ZHB2N2lxejZlZTVtYXptMWlxOWR3MWQ0MnNseXV0NDhrajBtcDVmdm81OGo1aWg6Yzd5bGtxcHVqd2FoODV5aG5wcnYwd2R2eXp1dGxjbmt3NHN6OTBidWxkYnVsazE=
  - Content-Type: application/x-www-form-urlencoded
- Body (password grant):
  - grant_type=password
  - username=<email>
  - password=<password>
- Body (refresh grant):
  - grant_type=refresh_token
  - refresh_token=<refresh_token>
- Response fields used:
  - access_token
  - refresh_token
  - expires_in (seconds)
  - token_type/scope/jti are present but not used
- Token validity:
  - expires_at = now(UTC) + expires_in
  - needs_refresh() when now >= expires_at
  - needs_auth() when no token cached

## Common request headers (client emulation)
- app-version: 3.2.1
- accept-language: en-ES;q=1.0, es-ES;q=0.9, ru-ES;q=0.8
- phone-os: 16.4
- user-agent: Blue/3.2.1 (com.fermax.bluefermax; build:3; iOS 16.4.0) Alamofire/3.2.1
- phone-model: iPad14,5
- app-build: 3
- All JSON requests use Authorization: Bearer <access_token>

## Base URL and endpoints
- BASE_URL: https://pro-duoxme.fermax.io
- Pairings: GET /pairing/api/v3/pairings/me
- Device info: GET /deviceaction/api/v1/device/{device_id}
- Open door: POST /deviceaction/api/v1/device/{device_id}/directed-opendoor
- F1: POST /deviceaction/api/v1/device/{device_id}/f1
- User info: GET /user/api/v1/users/me

## DeviceId and AccessId discovery
- Uses pairings() response to discover deviceId and accessDoorMap
- accessDoorMap values contain:
  - title
  - visible
  - accessId: { block, subblock, number }
- When no deviceId is provided, the script uses the first pairing

## Open door request
- Method: POST
- Endpoint: /deviceaction/api/v1/device/{device_id}/directed-opendoor
- Body: JSON of access_id, e.g. {"block": 1, "subblock": 0, "number": 12}
- Content-Type: application/json

## F1 request
- Method: POST
- Endpoint: /deviceaction/api/v1/device/{device_id}/f1
- Body: {"deviceID": "<device_id>"}

## Optional behaviors (CLI flags)
- --no-cache: disables reading/writing token cache file
- --reauth: forces auth refresh and exits without opening a door
- --f1: calls F1 (optionally with provided deviceId)
- --accessId supports multiple values; if provided with --deviceId, opens all
- If deviceId/accessId not provided, opens the first visible door from first pairing
-->
