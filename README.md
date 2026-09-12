# Kayer BigBlueButton Patches & Customizations

A structured, production-ready repository for BigBlueButton patches, version-specific client fixes, WebRTC optimizations, and security/concurrency policies.

---

## Repository Structure

Each patch is versioned and organized by target BigBlueButton major version under `patches/<version>/<patch-id>/`:

```text
kayer-bbb-patches/
├── README.md
├── bbb-patch.py                # Unified CLI runner to list, check, apply, and rollback patches
└── patches/
    └── v3.0.x/
        ├── audio-autojoin-muted/
        │   ├── README.md       # Technical explanation of the patch
        │   ├── metadata.json   # Patch metadata (id, version, target BBB releases)
        │   └── patch.py        # Self-contained standalone patch runner
        ├── audio-reconnect/
        │   ├── README.md       # WebRTC voice auto-reconnect & ICE retry policy
        │   ├── metadata.json
        │   └── patch.py
        └── single-device-restriction/
            ├── README.md       # 1 session per user policy & auto-ejection
            ├── metadata.json
            └── patch.py
```

---

## Available Patches

| Patch ID | Target BBB | Category | Description |
| :--- | :--- | :--- | :--- |
| `audio-autojoin-muted` | `3.0.x`, `3.0.35` | UX / Audio | Auto-joins locked users to microphone audio in muted state; enables instantaneous speech upon instructor unlock with zero popups, zero echo test, and zero reconnection delay. |
| `audio-reconnect` | `3.0.x`, `3.0.35` | Network / WebRTC | Configures WebRTC ICE retries + relay fallback, and injects a client background heartbeat and network `online` listener to automatically reconnect audio after network drops. |
| `single-device-restriction` | `3.0.x`, `3.0.35` | Policy / Security | Enforces `maxUserConcurrentAccesses=1` and `allowDuplicateExtUserid=false` in `bbb-web`, automatically terminating previous sessions when a user joins on a new device. |

---

## Usage

### 1. List Available Patches
```bash
python3 bbb-patch.py list
```

### 2. Check Status on Server
Check all patches:
```bash
python3 bbb-patch.py check --all
```
Or check a specific patch:
```bash
python3 bbb-patch.py check audio-autojoin-muted
```

### 3. Apply Patches
Apply all patches at once:
```bash
sudo python3 bbb-patch.py apply --all
```
Or apply an individual patch:
```bash
sudo python3 bbb-patch.py apply audio-reconnect
```

### 4. Rollback Patches
Rollback all patches:
```bash
sudo python3 bbb-patch.py rollback --all
```
Or rollback an individual patch:
```bash
sudo python3 bbb-patch.py rollback audio-reconnect
```

---

## Standalone Execution

Each patch is completely self-contained and can also be executed directly without the CLI wrapper:
```bash
sudo python3 patches/v3.0.x/audio-autojoin-muted/patch.py --check
sudo python3 patches/v3.0.x/audio-reconnect/patch.py --patch
sudo python3 patches/v3.0.x/single-device-restriction/patch.py --rollback
```
