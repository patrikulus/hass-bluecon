# Manual test checklist

- Add the integration with valid Fermax Blue credentials and finish the flow.
- Verify the config entry stores `username`/`password` and options include `pairings`.
- Confirm lock entities are created for each discovered access door.
- Trigger `lock.unlock` on a door and confirm the intercom opens.
- Trigger `lock.unlock` twice in a row to ensure the second call reuses the cached token.
- Restart Home Assistant and confirm the integration loads without re-auth.
- Force an auth failure (change password) and confirm re-auth flow prompts again.

Optional:

- Enable debug logging for `custom_components.bluecon` and confirm token refresh
  occurs after expiry (or after a forced 401) with a single retry.
