#!/usr/bin/env python3
"""
<summary>
BigBlueButton Backend Policy Patch: Enforce Single-Device Concurrency.
Target versions: BigBlueButton 3.0.x (tested on 3.0.35).
</summary>
<remarks>
Domain Problem:
By default, BigBlueButton allows the same user credentials / external user ID
to join a meeting from multiple tabs or physical devices simultaneously.
In school and exam environments, students may attempt to share credentials or
join concurrently from a second device to bypass attendance or integrity controls.

Implementation Strategy:
1. Configure /etc/bigbluebutton/bbb-web.properties:
   - maxUserConcurrentAccesses=1: Restricts active sessions to 1 per user.
   - allowDuplicateExtUserid=false: Prevents duplicate logins with the same external ID.
     When a student logs in on a second device, bbb-web terminates/ejects the previous session.
2. Ingest persistent hook into /etc/bigbluebutton/bbb-conf/apply-config.sh
   to ensure settings survive bbb-conf updates or maintenance rebuilds.
3. Gracefully reload the bbb-web systemd service and perform an HTTP health check
   against http://127.0.0.1:8090/bigbluebutton/api until SUCCESS is confirmed.
4. Provide check, apply, and rollback operations with automatic configuration backups.
</remarks>
"""

import os
import sys
import shutil
import subprocess
import time
import argparse
import urllib.request
import urllib.error

WEB_PROPERTIES_PATH = "/etc/bigbluebutton/bbb-web.properties"
APPLY_CONFIG_PATH = "/etc/bigbluebutton/bbb-conf/apply-config.sh"
BACKUP_DIR = "/root/bbb-customizations/single-device-restriction-backup"

# <summary>Target configuration parameters for bbb-web</summary>
EXPECTED_PROPERTIES = {
    "maxUserConcurrentAccesses": "1",
    "allowDuplicateExtUserid": "false"
}

HOOK_MARKER = "# Enforce single concurrent session per user (kick older device)"
HOOK_SNIPPET = """
# Enforce single concurrent session per user (kick older device)
if ! grep -q '^maxUserConcurrentAccesses=1' /etc/bigbluebutton/bbb-web.properties 2>/dev/null; then
    sed -i '/^maxUserConcurrentAccesses/d' /etc/bigbluebutton/bbb-web.properties
    echo 'maxUserConcurrentAccesses=1' >> /etc/bigbluebutton/bbb-web.properties
fi
if ! grep -q '^allowDuplicateExtUserid=false' /etc/bigbluebutton/bbb-web.properties 2>/dev/null; then
    sed -i '/^allowDuplicateExtUserid/d' /etc/bigbluebutton/bbb-web.properties
    echo 'allowDuplicateExtUserid=false' >> /etc/bigbluebutton/bbb-web.properties
fi
"""

def parse_properties(file_path):
    """
    <summary>Parses a Java .properties file into a Python dict.</summary>
    <param name="file_path">Absolute path to the properties file.</param>
    <returns>Dict of key-value pairs.</returns>
    """
    props = {}
    if not os.path.exists(file_path):
        return props
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                props[key.strip()] = val.strip()
    return props

def wait_for_bbb_web_health(timeout_seconds=30):
    """
    <summary>Polls bbb-web internal HTTP API endpoint until healthy or timeout.</summary>
    <param name="timeout_seconds">Maximum duration in seconds to poll.</param>
    <returns>True if healthy, False if timed out.</returns>
    """
    url = "http://127.0.0.1:8090/bigbluebutton/api"
    print(f"Waiting up to {timeout_seconds}s for bbb-web to report healthy API status...")
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "bbb-patcher"})
            with urllib.request.urlopen(req, timeout=2) as response:
                content = response.read().decode("utf-8")
                if "SUCCESS" in content:
                    print("bbb-web is healthy and successfully responding to API queries.")
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(1)
    print("Warning: bbb-web did not respond with SUCCESS within the allotted timeout.")
    return False

def check_status():
    """
    <summary>Validates whether single-device restrictions and persistence hooks are active.</summary>
    """
    props = parse_properties(WEB_PROPERTIES_PATH)
    props_ok = True
    for key, expected_val in EXPECTED_PROPERTIES.items():
        val = props.get(key)
        if val != expected_val:
            props_ok = False
            break

    hook_ok = False
    if os.path.exists(APPLY_CONFIG_PATH):
        with open(APPLY_CONFIG_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        if "maxUserConcurrentAccesses=1" in content and "allowDuplicateExtUserid=false" in content:
            hook_ok = True

    print("\nSingle-Device Concurrency Status:")
    print(f"  Configuration File: {WEB_PROPERTIES_PATH}")
    print(f"    - maxUserConcurrentAccesses: {props.get('maxUserConcurrentAccesses', 'not set')} (target: 1)")
    print(f"    - allowDuplicateExtUserid:   {props.get('allowDuplicateExtUserid', 'not set')} (target: false)")
    print(f"  Persistence Hook:   {APPLY_CONFIG_PATH} -> {'CONFIGURED' if hook_ok else 'MISSING'}")

    if props_ok and hook_ok:
        print("\n[STATUS] Patch is fully APPLIED and PERSISTED.")
        return 0
    elif not props_ok and not hook_ok:
        print("\n[STATUS] Patch is NOT applied.")
        return 1
    else:
        print("\n[STATUS] Patch is PARTIALLY configured.")
        return 2

def apply_patch():
    """
    <summary>Applies single-device restrictions, persistence hook, and restarts bbb-web.</summary>
    """
    print("Applying single-device restriction patch...")
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # 1. Backup existing configuration files
    if os.path.exists(WEB_PROPERTIES_PATH):
        backup_props = os.path.join(BACKUP_DIR, "bbb-web.properties.bak")
        shutil.copy2(WEB_PROPERTIES_PATH, backup_props)
        print(f"Backed up {WEB_PROPERTIES_PATH} to {backup_props}")

    if os.path.exists(APPLY_CONFIG_PATH):
        backup_hook = os.path.join(BACKUP_DIR, "apply-config.sh.bak")
        shutil.copy2(APPLY_CONFIG_PATH, backup_hook)
        print(f"Backed up {APPLY_CONFIG_PATH} to {backup_hook}")

    # 2. Update bbb-web.properties
    os.makedirs(os.path.dirname(WEB_PROPERTIES_PATH), exist_ok=True)
    lines = []
    if os.path.exists(WEB_PROPERTIES_PATH):
        with open(WEB_PROPERTIES_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

    # Filter out existing keys
    filtered_lines = [
        line for line in lines
        if not line.strip().startswith("maxUserConcurrentAccesses")
        and not line.strip().startswith("allowDuplicateExtUserid")
    ]

    # Ensure clean trailing newline
    if filtered_lines and not filtered_lines[-1].endswith("\n"):
        filtered_lines[-1] += "\n"

    filtered_lines.append("\n# Restrict concurrent sessions per user to 1 (prevent multi-device login)\n")
    filtered_lines.append("maxUserConcurrentAccesses=1\n")
    filtered_lines.append("allowDuplicateExtUserid=false\n")

    with open(WEB_PROPERTIES_PATH, "w", encoding="utf-8") as f:
        f.writelines(filtered_lines)
    print(f"Updated properties in {WEB_PROPERTIES_PATH}")

    # 3. Register persistence hook in apply-config.sh
    os.makedirs(os.path.dirname(APPLY_CONFIG_PATH), exist_ok=True)
    hook_content = ""
    if os.path.exists(APPLY_CONFIG_PATH):
        with open(APPLY_CONFIG_PATH, "r", encoding="utf-8") as f:
            hook_content = f.read()

    if "maxUserConcurrentAccesses=1" not in hook_content:
        with open(APPLY_CONFIG_PATH, "a", encoding="utf-8") as f:
            f.write(HOOK_SNIPPET)
        print(f"Appended persistence hook to {APPLY_CONFIG_PATH}")
    else:
        print(f"Persistence hook already present in {APPLY_CONFIG_PATH}")

    # Ensure executable permission
    subprocess.run(["chmod", "+x", APPLY_CONFIG_PATH], check=True)

    # 4. Restart bbb-web and verify health
    print("Restarting bbb-web service...")
    subprocess.run(["systemctl", "restart", "bbb-web"], check=True)
    wait_for_bbb_web_health(30)
    print("\nSUCCESS: Single-device restriction applied successfully!")

def rollback():
    """
    <summary>Reverts bbb-web.properties and apply-config.sh from backup or strips added lines.</summary>
    """
    print("Rolling back single-device restriction patch...")
    backup_props = os.path.join(BACKUP_DIR, "bbb-web.properties.bak")
    backup_hook = os.path.join(BACKUP_DIR, "apply-config.sh.bak")

    if os.path.exists(backup_props):
        shutil.copy2(backup_props, WEB_PROPERTIES_PATH)
        print(f"Restored {WEB_PROPERTIES_PATH} from backup.")
    else:
        if os.path.exists(WEB_PROPERTIES_PATH):
            with open(WEB_PROPERTIES_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
            filtered = [
                line for line in lines
                if not line.strip().startswith("maxUserConcurrentAccesses")
                and not line.strip().startswith("allowDuplicateExtUserid")
            ]
            with open(WEB_PROPERTIES_PATH, "w", encoding="utf-8") as f:
                f.writelines(filtered)
            print(f"Stripped restriction keys from {WEB_PROPERTIES_PATH}.")

    if os.path.exists(backup_hook):
        shutil.copy2(backup_hook, APPLY_CONFIG_PATH)
        print(f"Restored {APPLY_CONFIG_PATH} from backup.")

    print("Restarting bbb-web service...")
    subprocess.run(["systemctl", "restart", "bbb-web"], check=True)
    wait_for_bbb_web_health(30)
    print("Rollback completed successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BBB Single Device Concurrency Patch")
    parser.add_argument("--patch", action="store_true", help="Apply patch (default action)")
    parser.add_argument("--rollback", action="store_true", help="Rollback patch")
    parser.add_argument("--check", action="store_true", help="Check patch status")
    args = parser.parse_args()

    if args.rollback:
        rollback()
    elif args.check:
        sys.exit(check_status())
    else:
        apply_patch()
