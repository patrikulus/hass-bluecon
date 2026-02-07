# Manual Test Checklist

## 1. Setup
- [ ] Install the custom component in `custom_components/bluecon`.
- [ ] Restart Home Assistant.
- [ ] Go to Settings -> Devices & Services -> Add Integration -> Fermax Blue.

## 2. Config Flow
- [ ] Enter valid Username and Password.
- [ ] Verify that the integration loads successfully.
- [ ] Check logs for any "Login failed" or "Authentication failed" errors if creds are wrong.

## 3. Entities
- [ ] Check that a Lock entity is created for each door.
- [ ] Verify the entity name matches the door name/device info.

## 4. Functionality
- [ ] Click "Unlock" on the lock entity.
- [ ] Verify the door actually opens (if testing with real hardware).
- [ ] Check logs for "Open door" request success.

## 5. Token Refresh
- [ ] Wait for token expiry (usually 1 hour, or manually edit `.storage/bluecon...` file to set expiry in the past).
- [ ] Trigger an action (Unlock).
- [ ] Verify that the action succeeds and a new token is fetched (logs should show refresh or re-login).

## 6. Re-authentication
- [ ] Change password on Fermax side (if possible) or invalidate token manually.
- [ ] Verify that HA prompts for re-authentication or logs an error.
