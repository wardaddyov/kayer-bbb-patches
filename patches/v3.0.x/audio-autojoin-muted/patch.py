#!/usr/bin/env python3
"""
<summary>
BigBlueButton HTML5 Bundle Patch: Audio Auto-Join Muted & Lock Bypass.
Target versions: BigBlueButton 3.0.x (tested on 3.0.35).
</summary>
<remarks>
Domain Problem:
By default in BigBlueButton, if a room has lockSettingsDisableMic enabled,
attendees who join are automatically demoted to Listen-Only mode (simplex audio).
When an instructor unlocks the attendee, transitioning from Listen-Only to Microphone
requires tearing down the listen-only connection and running through the AudioModal /
EchoTest / Device Selection dialogs.

Implementation Strategy:
1. In AudioModal's useEffect, if audioLocked is true and forceListenOnlyAttendee is false,
   route the user to handleJoinMicrophone() instead of handleJoinListenOnly().
2. In the container's joinMic wrapper, force muted: true and skipEchoTest: true whenever
   audioLocked is true.
3. Remove the gatekeeper condition (Service.inputDeviceId() !== 'listen-only') that
   prevents joinFullAudioImmediately and shouldSkipEcho from activating.
4. Prevent storeAudioInputDeviceId from wiping the stored microphone device ID when in listen-only.
5. Provide automatic backup, JavaScript AST syntax validation (node --check),
   gzip recompression for Nginx gzip_static, and rollback functionality.
</remarks>
"""

import subprocess
import sys
import shutil
import os
import gzip
import re
import argparse

HTML5_DIR = "/usr/share/bigbluebutton/html5-client"
BACKUP_DIR = "/root/bbb-customizations/audio-autojoin-muted-fix-backup"

# <summary>Replacement tuples for standard browser bundles (Chrome, Firefox, Edge)</summary>
STD_REPLACEMENTS = [
    (
        # Rule 1: Allow skipEchoTest and enforce muted if userMic (audioLocked) is true
        'q=!V&&(m||g&&!a||W),$=(0,c.useCallback)((function(){var e,t,n,o=arguments.length>0&&void 0!==arguments[0]?arguments[0]:{};return Mue({skipEchoTest:o.skipEchoTest||q,muted:null!==(e=null!==(t=o.muteOnStart)&&void 0!==t?t:s)&&void 0!==e?e:null==r||null===(n=r.voiceSettings)||void 0===n?void 0:n.muteOnStart})}),[m,g,r,s])',
        'q=(m||g&&!a||W),$=(0,c.useCallback)((function(){var e,t,n,o=arguments.length>0&&void 0!==arguments[0]?arguments[0]:{};return Mue({skipEchoTest:H.userMic||o.skipEchoTest||q,muted:H.userMic||(null!==(e=null!==(t=o.muteOnStart)&&void 0!==t?t:s)&&void 0!==e?e:null==r||null===(n=r.voiceSettings)||void 0===n?void 0:n.muteOnStart)})}),[m,g,r,s,H])'
    ),
    (
        # Rule 2: Auto-join microphone when audioLocked is true (instead of handleJoinListenOnly)
        ';(0,c.useEffect)((function(){a||(t||i?Le():o||(r&&!xe?(Se(!0),De({doGUM:!0,permissionStatus:ne}).then((function(e){!1!==e&&ze()}))):Be()))}),[i,a,t,r,o,xe])',
        ';(0,c.useEffect)((function(){a||(t?Le():(r||i)&&!xe?(Se(!0),De({doGUM:!0,permissionStatus:ne}).then((function(e){!1!==e&&ze()}))):o?Le():Be())}),[i,a,t,r,o,xe])'
    ),
    (
        # Rule 3: Do not disqualify skipEchoTest simply because inputDeviceId is 'listen-only'
        't=e.skipEchoTest,n=void 0!==t&&t&&"listen-only"!==h0.inputDeviceId()',
        't=e.skipEchoTest,n=Boolean(void 0!==t&&t)'
    ),
    (
        # Rule 4: Do not delete stored microphone device ID when connected to listen-only
        'z$=function(e){return"listen-only"===e?(g$().removeItem(P$),!1):(g$().setItem(P$,e),!0)}',
        'z$=function(e){return"listen-only"===e?!1:(g$().setItem(P$,e),!0)}'
    ),
]

# <summary>Replacement tuples for Safari legacy bundle</summary>
SAF_REPLACEMENTS = [
    (
        # Rule 1: Safari container joinMic wrapper
        "var isListenOnlyInputDevice = audio_service.inputDeviceId() === 'listen-only';\n  var devicesAlreadyConfigured = skipEchoTestIfPreviousDevice && !!getStoredAudioInputDeviceId();\n  var joinFullAudioImmediately = !isListenOnlyInputDevice && (skipCheck || skipCheckOnJoin && !getEchoTest || devicesAlreadyConfigured);\n  var joinMic = (0,react.useCallback)(function () {\n    var _ref, _options$muteOnStart, _meeting$voiceSetting2;\n    var options = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : {};\n    return joinMicrophone({\n      skipEchoTest: options.skipEchoTest || joinFullAudioImmediately,\n      muted: (_ref = (_options$muteOnStart = options.muteOnStart) !== null && _options$muteOnStart !== void 0 ? _options$muteOnStart : storageMuteState) !== null && _ref !== void 0 ? _ref : meeting === null || meeting === void 0 || (_meeting$voiceSetting2 = meeting.voiceSettings) === null || _meeting$voiceSetting2 === void 0 ? void 0 : _meeting$voiceSetting2.muteOnStart\n    });\n  }, [skipCheck, skipCheckOnJoin, meeting, storageMuteState]);",
        "var isListenOnlyInputDevice = audio_service.inputDeviceId() === 'listen-only';\n  var devicesAlreadyConfigured = skipEchoTestIfPreviousDevice && !!getStoredAudioInputDeviceId();\n  var joinFullAudioImmediately = (skipCheck || skipCheckOnJoin && !getEchoTest || devicesAlreadyConfigured);\n  var joinMic = (0,react.useCallback)(function () {\n    var _ref, _options$muteOnStart, _meeting$voiceSetting2;\n    var options = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : {};\n    return joinMicrophone({\n      skipEchoTest: userLocks.userMic || options.skipEchoTest || joinFullAudioImmediately,\n      muted: userLocks.userMic || ((_ref = (_options$muteOnStart = options.muteOnStart) !== null && _options$muteOnStart !== void 0 ? _options$muteOnStart : storageMuteState) !== null && _ref !== void 0 ? _ref : meeting === null || meeting === void 0 || (_meeting$voiceSetting2 = meeting.voiceSettings) === null || _meeting$voiceSetting2 === void 0 ? void 0 : _meeting$voiceSetting2.muteOnStart)\n    });\n  }, [skipCheck, skipCheckOnJoin, meeting, storageMuteState, userLocks]);"
    ),
    (
        # Rule 2: Safari auto-join useEffect
        "if (forceListenOnlyAttendee || audioLocked) {\n        handleJoinListenOnly();\n      } else if (!listenOnlyMode) {\n        // Audio join should only be automatic if the prop says so, listen only\n        // mode is off, and automatic audio join hasn't been tried yet. For the\n        // latter, the reason is that we don't want to loop audio join retries\n        // if an error occurs.\n        if (joinFullAudioImmediately && !initialJoinExecuted) {\n          setInitialJoinExecuted(true);\n          checkMicrophonePermission({\n            doGUM: true,\n            permissionStatus: permissionStatus\n          }).then(function (hasPermission) {\n            // No permission - let the Help screen be shown as it's triggered\n            // by the checkMicrophonePermission function\n            if (hasPermission === false) return;\n\n            // Permission is granted or undetermined, so we can proceed\n            handleJoinMicrophone();\n          });\n        } else {\n          // No need to check for permission here since the AudioSettings\n          // component will handle it\n          handleGoToEchoTest();\n        }\n      }\n    }",
        "if (forceListenOnlyAttendee) {\n        handleJoinListenOnly();\n      } else if ((joinFullAudioImmediately || audioLocked) && !initialJoinExecuted) {\n        setInitialJoinExecuted(true);\n        checkMicrophonePermission({\n          doGUM: true,\n          permissionStatus: permissionStatus\n        }).then(function (hasPermission) {\n          if (hasPermission === false) return;\n          handleJoinMicrophone();\n        });\n      } else if (!listenOnlyMode) {\n        handleGoToEchoTest();\n      }\n    }"
    ),
    (
        # Rule 3: Safari skip echo test check
        "var shouldSkipEcho = skipEchoTest && audio_service.inputDeviceId() !== 'listen-only';",
        "var shouldSkipEcho = Boolean(skipEchoTest);"
    ),
    (
        # Rule 4: Safari input device storage cleanup
        "if (deviceId === 'listen-only') {\n    // Do not store listen-only \"devices\" and remove any stored device\n    // So it starts from scratch next time.\n    getStorageSingletonInstance().removeItem(INPUT_DEVICE_ID_KEY);\n    return false;\n  }",
        "if (deviceId === 'listen-only') {\n    return false;\n  }"
    )
]

def get_bundle_paths():
    """
    <summary>Extracts the active bundle hash from index.html and resolves paths.</summary>
    <returns>Tuple of (bundle_hash, standard_bundle_path, safari_bundle_path)</returns>
    """
    index_path = os.path.join(HTML5_DIR, "index.html")
    if not os.path.exists(index_path):
        print(f"Error: {index_path} not found.")
        sys.exit(1)

    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    m = re.search(r"bundleHash\s*=\s*'([a-f0-9]+)'", content)
    if not m:
        print("Error: bundleHash not found in index.html.")
        sys.exit(1)

    bundle_hash = m.group(1)
    std_path = os.path.join(HTML5_DIR, f"bundle.{bundle_hash}.js")
    saf_path = os.path.join(HTML5_DIR, f"bundle.{bundle_hash}.safari.js")
    return bundle_hash, std_path, saf_path

def check_status():
    """
    <summary>Checks whether the active bundle has already been patched.</summary>
    """
    bundle_hash, std_path, saf_path = get_bundle_paths()
    print(f"Active bundle hash: {bundle_hash}")

    with open(std_path, "r", encoding="utf-8") as f:
        std = f.read()

    patched = (STD_REPLACEMENTS[0][1] in std)
    unpatched = (STD_REPLACEMENTS[0][0] in std)

    if patched:
        print("[STATUS] Bundle is currently: PATCHED (zero-click auto-join mic active)")
    elif unpatched:
        print("[STATUS] Bundle is currently: UNPATCHED (standard BBB behavior)")
    else:
        print("[STATUS] Bundle state unknown or already modified.")

def apply_patch():
    """
    <summary>Applies code changes, verifies syntax, creates backups, and reloads Nginx.</summary>
    """
    bundle_hash, std_path, saf_path = get_bundle_paths()
    print(f"Applying patch to bundle: {bundle_hash}")

    with open(std_path, "r", encoding="utf-8") as f:
        std = f.read()
    with open(saf_path, "r", encoding="utf-8") as f:
        saf = f.read()

    if STD_REPLACEMENTS[0][1] in std:
        print("Notice: Bundle already has the patch applied.")
        return

    # Verify that all target replacement strings exist in unpatched form
    for i, (old, _) in enumerate(STD_REPLACEMENTS, 1):
        if old not in std:
            print(f"Error: Standard replacement rule #{i} target string not found.")
            sys.exit(1)

    for i, (old, _) in enumerate(SAF_REPLACEMENTS, 1):
        if old not in saf:
            print(f"Error: Safari replacement rule #{i} target string not found.")
            sys.exit(1)

    std_patched = std
    for old, new in STD_REPLACEMENTS:
        std_patched = std_patched.replace(old, new)

    saf_patched = saf
    for old, new in SAF_REPLACEMENTS:
        saf_patched = saf_patched.replace(old, new)

    # Validate syntax with node --check before writing to disk
    test_std_tmp = "/tmp/test_bundle.js"
    test_saf_tmp = "/tmp/test_bundle.safari.js"

    with open(test_std_tmp, "w", encoding="utf-8") as f:
        f.write(std_patched)
    with open(test_saf_tmp, "w", encoding="utf-8") as f:
        f.write(saf_patched)

    print("Verifying JavaScript syntax using node --check...")
    r1 = subprocess.run(["node", "--check", test_std_tmp], capture_output=True, text=True)
    if r1.returncode != 0:
        print("Syntax error in patched standard bundle:\n", r1.stderr)
        sys.exit(1)

    r2 = subprocess.run(["node", "--check", test_saf_tmp], capture_output=True, text=True)
    if r2.returncode != 0:
        print("Syntax error in patched Safari bundle:\n", r2.stderr)
        sys.exit(1)

    print("Syntax verification passed.")

    # Create safety backup
    os.makedirs(BACKUP_DIR, exist_ok=True)
    shutil.copy2(std_path, os.path.join(BACKUP_DIR, os.path.basename(std_path)))
    shutil.copy2(saf_path, os.path.join(BACKUP_DIR, os.path.basename(saf_path)))
    if os.path.exists(std_path + ".gz"):
        shutil.copy2(std_path + ".gz", os.path.join(BACKUP_DIR, os.path.basename(std_path) + ".gz"))
    if os.path.exists(saf_path + ".gz"):
        shutil.copy2(saf_path + ".gz", os.path.join(BACKUP_DIR, os.path.basename(saf_path) + ".gz"))
    print(f"Backup saved to: {BACKUP_DIR}")

    # Write patched files
    with open(std_path, "w", encoding="utf-8") as f:
        f.write(std_patched)
    with open(saf_path, "w", encoding="utf-8") as f:
        f.write(saf_patched)

    # Re-compress for Nginx gzip_static module
    print("Re-compressing .gz archives for nginx gzip_static...")
    with open(std_path, "rb") as f_in, gzip.open(std_path + ".gz", "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    with open(saf_path, "rb") as f_in, gzip.open(saf_path + ".gz", "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    # Fix file ownership and permissions
    subprocess.run(["chown", "bigbluebutton:bigbluebutton", std_path, saf_path, std_path + ".gz", saf_path + ".gz"])
    subprocess.run(["chmod", "644", std_path, saf_path, std_path + ".gz", saf_path + ".gz"])

    # Reload Nginx to invalidate any in-memory cached responses
    subprocess.run(["nginx", "-t"], check=True)
    subprocess.run(["systemctl", "reload", "nginx"], check=True)

    if os.path.exists(test_std_tmp): os.remove(test_std_tmp)
    if os.path.exists(test_saf_tmp): os.remove(test_saf_tmp)

    print("SUCCESS: Patch applied and Nginx reloaded successfully!")

def rollback():
    """
    <summary>Restores original bundle from the backup directory.</summary>
    """
    bundle_hash, std_path, saf_path = get_bundle_paths()
    backup_std = os.path.join(BACKUP_DIR, os.path.basename(std_path))
    backup_saf = os.path.join(BACKUP_DIR, os.path.basename(saf_path))

    if not os.path.exists(backup_std) or not os.path.exists(backup_saf):
        print(f"Error: Backups not found in {BACKUP_DIR}")
        sys.exit(1)

    print(f"Restoring backups for {bundle_hash}...")
    shutil.copy2(backup_std, std_path)
    shutil.copy2(backup_saf, saf_path)

    if os.path.exists(backup_std + ".gz"):
        shutil.copy2(backup_std + ".gz", std_path + ".gz")
    if os.path.exists(backup_saf + ".gz"):
        shutil.copy2(backup_saf + ".gz", saf_path + ".gz")

    subprocess.run(["chown", "bigbluebutton:bigbluebutton", std_path, saf_path, std_path + ".gz", saf_path + ".gz"])
    subprocess.run(["chmod", "644", std_path, saf_path, std_path + ".gz", saf_path + ".gz"])
    subprocess.run(["systemctl", "reload", "nginx"], check=True)

    print("Rollback completed successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BBB Audio Auto-Join Muted Patch")
    parser.add_argument("--patch", action="store_true", help="Apply patch (default action)")
    parser.add_argument("--rollback", action="store_true", help="Rollback to previous backup")
    parser.add_argument("--check", action="store_true", help="Check patch status")
    args = parser.parse_args()

    if args.rollback:
        rollback()
    elif args.check:
        check_status()
    else:
        apply_patch()
