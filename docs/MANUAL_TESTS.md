# Manual Test Checklist

Use this checklist after installing the updated integration in
Home Assistant.

---

## Config Flow

- [ ] **Fresh install**: Add the integration via Settings → Integrations →
      Add Integration → "Fermax Blue". Enter username + password.
      Expect: entry is created, entities appear.
- [ ] **Invalid credentials**: Enter a wrong password during setup.
      Expect: "Invalid authentication" error shown; no entry created.
- [ ] **Connection failure**: Disconnect network, attempt setup.
      Expect: "Failed to connect to Fermax API" error.
- [ ] **Duplicate account**: Try to add the same username again.
      Expect: "Account is already configured" abort.

## Migration (from v ≤ 6)

- [ ] **Upgrade path**: Install v0.7.0 over an existing v0.6.x config.
      Expect: entry migrates to v7, integration shows "Re-authenticate"
      prompt (ConfigEntryAuthFailed).
- [ ] **Re-auth flow**: Complete the re-auth form with correct credentials.
      Expect: integration loads normally, entities reappear.

## Token Management

- [ ] **Token caching**: After first login, restart HA.
      Expect: integration reloads without hitting the auth endpoint
      (check debug logs for "Authenticating" vs. "Refreshing").
- [ ] **Token refresh**: Wait for the token to expire (~1 hour).
      Expect: next API call automatically refreshes the token; no
      user interaction needed.
- [ ] **401 retry**: Force a 401 (e.g., invalidate the cached token
      file in `.storage/bluecon.token.*`).
      Expect: client re-authenticates and the request succeeds.

## Entities

### Lock (`lock.<deviceid>_<doorname>_door_lock`)

- [ ] **Unlock**: Call `lock.unlock` service (or press Unlock in UI).
      Expect: state goes `locked → unlocking → unlocked → locked`
      (after timeout). API endpoint `directed-opendoor` is called.
- [ ] **Multiple doors**: If the device has >1 access door, verify each
      gets its own lock entity with the correct door name.

### Binary Sensor (`binary_sensor.<deviceid>_connection_status`)

- [ ] **Connected**: When the device is online, the sensor is "on".
- [ ] **Disconnected**: When the device is offline, the sensor is "off".
- [ ] **Polling**: The sensor auto-updates on each HA poll cycle.

### Sensor (`sensor.<deviceid>_wifi_strength`)

- [ ] **Signal level**: Shows one of: terrible / bad / weak / good /
      excelent / unknown.
- [ ] **Polling**: Updates automatically.

### Button (`button.<deviceid>_f1_button`)

- [ ] **Press**: Pressing the F1 button calls the `/f1` API endpoint.
      Expect: no error, debug log shows "Sending F1 command…".

## Options

- [ ] **Lock timeout**: Go to integration Options, change the timer.
      Expect: next unlock respects the new value.
- [ ] **Negative value**: Enter a negative number.
      Expect: "The value must be a positive number" error.

## Reconfigure

- [ ] **Update credentials**: Use the Reconfigure action from the
      integration entry menu.
      Expect: after entering new credentials, the integration reloads.

---

## Notes

- **Camera / Call Status sensors** are not available in this version.
  The camera relied on `getLastPicture` (endpoint unknown) and call
  status relied on FCM push (not ported).
- If either feature is needed later, see `docs/porting_notes.md` for
  the endpoint documentation.
