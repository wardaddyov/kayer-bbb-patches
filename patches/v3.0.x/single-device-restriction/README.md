# BigBlueButton Single-Device Concurrency Policy

- **Target Versions**: BigBlueButton 3.0.x (tested on 3.0.35)
- **Target Component**: `bbb-web` Java service
- **Patch Type**: Backend configuration & persistence policy

---

## 1. Problem Description

By default, BigBlueButton allows the same user identity / external user ID (`extId`) to open concurrent sessions from multiple browser tabs or distinct physical devices (e.g. laptop + smartphone).

In controlled educational and examination contexts:
1. Students may share room join links or account sessions with other individuals.
2. Concurrent logins make attendance and active participant metrics ambiguous.

---

## 2. Solution & Implementation

This patch configures `bbb-web` with strict single-device session handling:
1. **`maxUserConcurrentAccesses=1`**: Limits active sessions for any given external user identifier to 1.
2. **`allowDuplicateExtUserid=false`**: Prohibits duplicate user IDs. When a user connects from a second device or new browser session, `bbb-web` immediately terminates and ejects the previous session.
3. **Persistence Hook**: Adds an idempotent configuration enforcement block to `/etc/bigbluebutton/bbb-conf/apply-config.sh` so these settings persist across server updates and `bbb-conf --restart`.
4. **Health Check**: Restarts `systemctl restart bbb-web` and polls `http://127.0.0.1:8090/bigbluebutton/api` until `SUCCESS` is confirmed.

---

## 3. Usage

### Apply the Patch
```bash
python3 patch.py
```
Or via the central manager:
```bash
python3 bbb-patch.py apply single-device-restriction
```

### Check Status
```bash
python3 bbb-patch.py check single-device-restriction
```

### Rollback
```bash
python3 bbb-patch.py rollback single-device-restriction
```
