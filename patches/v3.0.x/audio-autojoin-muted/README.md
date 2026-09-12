# BigBlueButton Audio Auto-Join Muted & Lock Bypass

- **Target Versions**: BigBlueButton 3.0.x (tested on 3.0.35)
- **Target Component**: `bbb-html5` Webpack client bundles
- **Patch Type**: Runtime client bundle enhancement

---

## 1. Problem Description

In stock BigBlueButton v3:
1. When a meeting is started with viewer microphones locked (`lockSettingsDisableMic=true`):
   - Joining attendees are forcefully routed to **Listen-Only** mode (`handleJoinListenOnly()`).
   - Listen-Only mode only receives incoming audio; the local browser microphone stream is never requested or connected.
   - BBB sets `inputDeviceId = 'listen-only'` and clears any stored audio device from browser storage.
2. When the instructor unlocks a student:
   - The student remains in Listen-Only mode.
   - When the student clicks to connect microphone, BBB's `joinFullAudioImmediately` is disabled because `inputDeviceId === 'listen-only'`.
   - The student is forced through the **Audio Settings / Microphone Selection dialog** (BBB v3's Local Echo Test).

---

## 2. Solution & Architecture

This patch modifies the compiled client bundle:
1. **Direct Microphone Auto-Join**: Attendees joining with `audioLocked = true` auto-join two-way microphone audio immediately.
2. **Guaranteed Initial Mute**: In the container's `joinMic` wrapper, `muted: true` and `skipEchoTest: true` are enforced whenever `audioLocked` is active.
3. **Hardware-Ready Muted State**: The WebRTC microphone track is pre-negotiated and active in FreeSWITCH / LiveKit, but muted at the server level.
4. **UI Lock Enforcement**: The student's mute toggle button is disabled (`isAudioLocked: true`). If they attempt to unmute, the client UI blocks it and the Scala backend (`MuteUserCmdMsgHdlr.scala`) rejects it.
5. **Instant Speech on Unlock**: When the instructor unlocks the student:
   - `isAudioLocked` becomes `false` in real time.
   - The student's microphone button immediately enables.
   - The student clicks **Unmute** and speaks immediately with **zero popups, zero echo test, and zero WebRTC reconnection delay**.
6. **Listen-Only Transition Safety**: Eliminates the hardcoded `'listen-only'` check so that if an attendee ever transitions from listen-only, the modal is bypassed if `skipCheck: true` is configured.

---

## 3. Usage

### Apply the Patch
Run as `root` on the BBB node:
```bash
python3 patch.py
```

### Check Patch Status
```bash
python3 patch.py --check
```

### Revert the Patch
```bash
python3 patch.py --rollback
```
