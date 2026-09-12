# BigBlueButton WebRTC Voice Auto-Reconnect & ICE Retries

- **Target Versions**: BigBlueButton 3.0.x (tested on 3.0.35)
- **Target Components**: `bbb-html5` (Webpack bundles & YAML configuration)
- **Patch Type**: Client runtime hook + WebRTC ICE resiliency policy

---

## 1. Problem Description

Attendees on cellular mobile networks (4G/LTE) or unstable home Wi-Fi frequently encounter transient packet loss or routing changes. In stock BigBlueButton:
1. When WebRTC ICE connectivity fails, the call is prematurely dropped or left in an error state.
2. The student must manually refresh the page or click through audio join modals again to get back into voice.

---

## 2. Solution & Architecture

This patch enhances connection resiliency on two levels:
1. **Server-Side & Client WebRTC Resiliency (`/etc/bigbluebutton/bbb-html5.yml`)**:
   - `kurento.restartIce.audio.enabled: true`: Enables ICE restart retries.
   - `kurento.restartIce.audio.retries: 3`: Configures 3 automatic WebRTC renegotiation attempts before giving up.
   - `media.audio.retryThroughRelay: true`: Automatically falls back through TURN relay servers if direct UDP connectivity drops.
2. **Client React Lifecycle Watcher (`bundle.*.js` and `bundle.*.safari.js`)**:
   - Periodically evaluates the audio session every 2,500ms.
   - Listens to browser `window.addEventListener('online', ...)` events.
   - If the device is online and the user had previously selected audio (mic or listen-only), but the connection is dead, automatically calls `joinAudio()` with zero clicks.
   - Exposes `window.__bbb_joinAudio` globally for health probing.

---

## 3. Usage

### Apply the Patch
```bash
python3 patch.py
```
Or via the central manager:
```bash
python3 bbb-patch.py apply audio-reconnect
```

### Check Status
```bash
python3 bbb-patch.py check audio-reconnect
```

### Rollback
```bash
python3 bbb-patch.py rollback audio-reconnect
```
