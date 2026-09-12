# Kayer BigBlueButton Patches & Customizations

A structured repository for production BigBlueButton patches, version-specific client fixes, and UX enhancements.

---

## Repository Structure

Each patch is versioned and organized by target BigBlueButton major version under `patches/<version>/<patch-id>/`:

```text
kayer-bbb-patches/
├── README.md
├── bbb-patch.py                # Unified CLI runner to list, check, apply, and rollback patches
└── patches/
    └── v3.0.x/
        └── audio-autojoin-muted/
            ├── README.md       # Technical explanation of the patch
            ├── metadata.json   # Patch metadata (id, version, target BBB releases)
            └── patch.py        # Self-contained standalone patch runner
```

---

## Available Patches

| Patch ID | Target BBB | Description |
| :--- | :--- | :--- |
| `audio-autojoin-muted` | `3.0.x`, `3.0.35` | Auto-joins locked users to microphone audio in muted state; enables instantaneous speech upon instructor unlock with zero popups, zero echo test, and zero reconnection delay. |

---

## Usage

### 1. List Available Patches
```bash
python3 bbb-patch.py list
```

### 2. Check Status of a Patch on This Server
```bash
python3 bbb-patch.py check audio-autojoin-muted
```

### 3. Apply a Patch
```bash
sudo python3 bbb-patch.py apply audio-autojoin-muted
```

### 4. Rollback an Applied Patch
```bash
sudo python3 bbb-patch.py rollback audio-autojoin-muted
```

Alternatively, you can run any patch script standalone directly:
```bash
sudo python3 patches/v3.0.x/audio-autojoin-muted/patch.py
```
