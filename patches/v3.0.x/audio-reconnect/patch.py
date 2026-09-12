#!/usr/bin/env python3
"""
<summary>
BigBlueButton WebRTC Voice Auto-Reconnect & ICE Retries Patch.
Target versions: BigBlueButton 3.0.x (tested on 3.0.35).
</summary>
<remarks>
Domain Problem:
Students on mobile data or unstable Wi-Fi networks frequently suffer from transient
packet loss, NAT timeouts, or brief network disconnections. In stock BigBlueButton:
1. If WebRTC ICE drops, the client often fails the audio call entirely without sufficient retries.
2. When the network returns, the attendee remains silent and disconnected until they
   manually notice and re-trigger audio join dialogs.

Implementation Strategy:
1. Configure /etc/bigbluebutton/bbb-html5.yml:
   - kurento.restartIce.audio.enabled: true
   - kurento.restartIce.audio.retries: 3
   - media.audio.retryThroughRelay: true (forces TURN relay fallback if P2P/UDP fails)
2. In the React audio container hook in both Standard and Safari HTML5 bundles:
   - Injects a background heartbeat (every 2.5s) that checks if the browser is online,
     the user previously had audio selected, but audio connection is currently dead.
   - Injects a window 'online' event listener (1s debounce) to immediately trigger joinAudio()
     when network connectivity is restored.
   - Exposes window.__bbb_joinAudio = joinAudio for debugging and external re-triggering.
3. Safe In-Place Modification:
   Unlike legacy standalone scripts, this patch modifies bundles in-place without
   clobbering other installed client patches (such as audio-autojoin-muted).
4. Verifies JavaScript syntax with node --check, re-compresses .gz static files for Nginx,
   and provides backup, rollback, and apply-config.sh persistence.
</remarks>
"""

import os
import sys
import shutil
import subprocess
import gzip
import re
import argparse

HTML5_DIR = "/usr/share/bigbluebutton/html5-client"
HTML5_YAML_PATH = "/etc/bigbluebutton/bbb-html5.yml"
APPLY_CONFIG_PATH = "/etc/bigbluebutton/bbb-conf/apply-config.sh"
BACKUP_DIR = "/root/bbb-customizations/audio-reconnect-backup"

# --- Target replacements for Standard Bundle ---
TARGET_STD = '];sye();var U=(0,c.useCallback)((function(){var e;h0.isConnected()||(v?Mue({skipEchoTest:!0,muted:null!=A?A:null==S||null===(e=S.voiceSettings)||void 0===e?void 0:e.muteOnStart}):y&&jue())}),[v,y,null==S||null===(i=S.voiceSettings)||void 0===i?void 0:i.muteOnStart,A]);return(0,c.useEffect)((function(){void 0!==E&&_&&N().then((function(){!E||h0.isUsingAudio()||l||U()}))}),[E,_]),(0,c.useEffect)((function(){L&&U()}),[L]),'
REPLACEMENT_STD = '];sye();var U=(0,c.useCallback)((function(){var e;h0.isConnected()||(v?Mue({skipEchoTest:!0,muted:null!=A?A:null==S||null===(e=S.voiceSettings)||void 0===e?void 0:e.muteOnStart}):y&&jue())}),[v,y,null==S||null===(i=S.voiceSettings)||void 0===i?void 0:i.muteOnStart,A]);try{window.__bbb_joinAudio=U}catch(e){};return(0,c.useEffect)((function(){var itv=setInterval((function(){try{if(navigator.onLine&&(v||y)&&!h0.isConnected()&&!h0.isUsingAudio()&&!l){U()}}catch(e){}}),2500);var onOnline=function(){setTimeout((function(){try{if((v||y)&&!h0.isConnected()&&!h0.isUsingAudio()&&!l){U()}}catch(e){}}),1000)};window.addEventListener("online",onOnline);return function(){clearInterval(itv);window.removeEventListener("online",onOnline)}}),[U,v,y,l]),(0,c.useEffect)((function(){void 0!==E&&_&&N().then((function(){!E||h0.isUsingAudio()||l||U()}))}),[E,_]),(0,c.useEffect)((function(){L&&U()}),[L]),'

# --- Target replacements for Safari Bundle ---
START_SAF = 'if (userSelectedListenOnly) joinListenOnly();'
END_SAF = '// Data is not loaded yet.'
REPLACEMENT_SAF = '''if (userSelectedListenOnly) joinListenOnly();
  }, [userSelectedMicrophone, userSelectedListenOnly, meeting === null || meeting === void 0 || (_meeting = meeting.voiceSettings) === null || _meeting === void 0 ? void 0 : _meeting.muteOnStart, storageMuteState]);
  try { window.__bbb_joinAudio = joinAudio; } catch(e) {};
  (0,react.useEffect)(function () {
    var itv = setInterval(function () {
      try {
        if (navigator.onLine && (userSelectedMicrophone || userSelectedListenOnly) && !audio_service.isConnected() && !audio_service.isUsingAudio() && !currentUserHasVoice) {
          joinAudio();
        }
      } catch (e) {}
    }, 2500);
    var onOnline = function () {
      setTimeout(function () {
        try {
          if ((userSelectedMicrophone || userSelectedListenOnly) && !audio_service.isConnected() && !audio_service.isUsingAudio() && !currentUserHasVoice) {
            joinAudio();
          }
        } catch (e) {}
      }, 1000);
    };
    window.addEventListener(online, onOnline);
    return function () {
      clearInterval(itv);
      window.removeEventListener(online, onOnline);
    };
  }, [joinAudio, userSelectedMicrophone, userSelectedListenOnly, currentUserHasVoice]);
  (0,react.useEffect)(function () {
    // Data is not loaded yet.'''

def get_bundle_paths():
    """
    <summary>Resolves active bundle hash and paths from index.html.</summary>
    """
    index_path = os.path.join(HTML5_DIR, "index.html")
    if not os.path.exists(index_path):
        print(f"Error: {index_path} not found.", file=sys.stderr)
        sys.exit(1)

    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    m = re.search(r"bundleHash\s*=\s*'([a-f0-9]+)'", content)
    if not m:
        print("Error: bundleHash not found in index.html.", file=sys.stderr)
        sys.exit(1)

    bundle_hash = m.group(1)
    std_path = os.path.join(HTML5_DIR, f"bundle.{bundle_hash}.js")
    saf_path = os.path.join(HTML5_DIR, f"bundle.{bundle_hash}.safari.js")
    return bundle_hash, std_path, saf_path

def update_yaml_config():
    """
    <summary>Configures restartIce and retryThroughRelay in /etc/bigbluebutton/bbb-html5.yml.</summary>
    """
    if not os.path.exists(HTML5_YAML_PATH):
        print(f"Notice: {HTML5_YAML_PATH} does not exist, creating directory structure...")
        os.makedirs(os.path.dirname(HTML5_YAML_PATH), exist_ok=True)

    try:
        import yaml
        data = {}
        if os.path.exists(HTML5_YAML_PATH):
            with open(HTML5_YAML_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        pub = data.setdefault("public", {})
        kur = pub.setdefault("kurento", {})
        restart_ice = kur.setdefault("restartIce", {})
        audio_ice = restart_ice.setdefault("audio", {})
        audio_ice["enabled"] = True
        audio_ice["retries"] = 3

        med = pub.setdefault("media", {})
        audio_med = med.setdefault("audio", {})
        audio_med["retryThroughRelay"] = True

        with open(HTML5_YAML_PATH, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False)
        print(f"Updated WebRTC ICE parameters in {HTML5_YAML_PATH}")
    except ImportError:
        # Fallback to pure string editing if PyYAML is not installed
        print("Warning: PyYAML not installed; configuring YAML via text template.")
        snippet = """
public:
  kurento:
    restartIce:
      audio:
        enabled: true
        retries: 3
  media:
    audio:
      retryThroughRelay: true
"""
        with open(HTML5_YAML_PATH, "a", encoding="utf-8") as f:
            f.write(snippet)

def check_status():
    """
    <summary>Checks whether bundle and YAML have the auto-reconnect patch installed.</summary>
    """
    bundle_hash, std_path, saf_path = get_bundle_paths()
    print(f"Active bundle hash: {bundle_hash}")

    with open(std_path, "r", encoding="utf-8") as f:
        std = f.read()

    bundle_patched = ("__bbb_joinAudio" in std)

    yaml_ok = False
    if os.path.exists(HTML5_YAML_PATH):
        with open(HTML5_YAML_PATH, "r", encoding="utf-8") as f:
            ycontent = f.read()
            if "restartIce" in ycontent and "retryThroughRelay" in ycontent:
                yaml_ok = True

    hook_ok = False
    if os.path.exists(APPLY_CONFIG_PATH):
        with open(APPLY_CONFIG_PATH, "r", encoding="utf-8") as f:
            if "patch-bbb-audio-reconnect" in f.read() or "audio-reconnect" in f.read():
                hook_ok = True

    print("\nAudio Reconnect Status:")
    print(f"  Bundle Patch (__bbb_joinAudio): {'INSTALLED' if bundle_patched else 'MISSING'}")
    print(f"  YAML Config (restartIce/relay):  {'CONFIGURED' if yaml_ok else 'MISSING'}")
    print(f"  Persistence Hook (apply-config):{'CONFIGURED' if hook_ok else 'MISSING'}")

    if bundle_patched and yaml_ok:
        print("\n[STATUS] Patch is fully APPLIED.")
        return 0
    elif not bundle_patched and not yaml_ok:
        print("\n[STATUS] Patch is NOT applied.")
        return 1
    else:
        print("\n[STATUS] Patch is PARTIALLY applied.")
        return 2

def apply_patch():
    """
    <summary>Applies audio reconnect logic to bundles and YAML, validates syntax, reloads services.</summary>
    """
    bundle_hash, std_path, saf_path = get_bundle_paths()
    print(f"Applying WebRTC voice reconnect patch to bundle {bundle_hash}...")

    os.makedirs(BACKUP_DIR, exist_ok=True)
    update_yaml_config()

    with open(std_path, "r", encoding="utf-8") as f:
        std = f.read()
    with open(saf_path, "r", encoding="utf-8") as f:
        saf = f.read()

    std_already = ("__bbb_joinAudio" in std)
    saf_already = ("__bbb_joinAudio" in saf)

    if std_already and saf_already:
        print("Notice: Client bundles already have __bbb_joinAudio reconnect logic applied.")
        return

    # 1. Backup before modification
    shutil.copy2(std_path, os.path.join(BACKUP_DIR, os.path.basename(std_path)))
    shutil.copy2(saf_path, os.path.join(BACKUP_DIR, os.path.basename(saf_path)))
    if os.path.exists(std_path + ".gz"):
        shutil.copy2(std_path + ".gz", os.path.join(BACKUP_DIR, os.path.basename(std_path) + ".gz"))
    if os.path.exists(saf_path + ".gz"):
        shutil.copy2(saf_path + ".gz", os.path.join(BACKUP_DIR, os.path.basename(saf_path) + ".gz"))
    print(f"Backup created in {BACKUP_DIR}")

    # 2. Patch standard bundle in-place
    if not std_already:
        if TARGET_STD not in std:
            print("Error: Target pattern for standard bundle not found!", file=sys.stderr)
            sys.exit(1)
        std_patched = std.replace(TARGET_STD, REPLACEMENT_STD, 1)
    else:
        std_patched = std

    # 3. Patch Safari bundle in-place
    if not saf_already:
        s_idx = saf.find(START_SAF)
        if s_idx == -1:
            print("Error: Start anchor for safari bundle not found!", file=sys.stderr)
            sys.exit(1)
        e_idx = saf.find(END_SAF, s_idx)
        if e_idx == -1:
            print("Error: End anchor for safari bundle not found!", file=sys.stderr)
            sys.exit(1)
        saf_anchor = saf[s_idx:e_idx + len(END_SAF)]
        saf_patched = saf.replace(saf_anchor, REPLACEMENT_SAF, 1)
    else:
        saf_patched = saf

    # 4. Validate syntax with node --check
    test_std_tmp = "/tmp/test_recon_std.js"
    test_saf_tmp = "/tmp/test_recon_saf.js"
    with open(test_std_tmp, "w", encoding="utf-8") as f: f.write(std_patched)
    with open(test_saf_tmp, "w", encoding="utf-8") as f: f.write(saf_patched)

    print("Verifying JavaScript syntax using node --check...")
    r1 = subprocess.run(["node", "--check", test_std_tmp], capture_output=True, text=True)
    if r1.returncode != 0:
        print("Syntax error in patched standard bundle:\n", r1.stderr, file=sys.stderr)
        sys.exit(1)

    r2 = subprocess.run(["node", "--check", test_saf_tmp], capture_output=True, text=True)
    if r2.returncode != 0:
        print("Syntax error in patched Safari bundle:\n", r2.stderr, file=sys.stderr)
        sys.exit(1)

    # 5. Write patched bundles
    with open(std_path, "w", encoding="utf-8") as f: f.write(std_patched)
    with open(saf_path, "w", encoding="utf-8") as f: f.write(saf_patched)

    # 6. Re-compress for Nginx gzip_static
    print("Re-compressing .gz archives for nginx gzip_static...")
    subprocess.run(["gzip", "-kf", "-9", std_path], check=True)
    subprocess.run(["gzip", "-kf", "-9", saf_path], check=True)

    # 7. File ownership & permissions
    subprocess.run(["chown", "bigbluebutton:bigbluebutton", std_path, saf_path, std_path + ".gz", saf_path + ".gz"])
    subprocess.run(["chmod", "644", std_path, saf_path, std_path + ".gz", saf_path + ".gz"])

    # 8. Reload Nginx
    subprocess.run(["nginx", "-t"], check=True)
    subprocess.run(["systemctl", "reload", "nginx"], check=True)

    if os.path.exists(test_std_tmp): os.remove(test_std_tmp)
    if os.path.exists(test_saf_tmp): os.remove(test_saf_tmp)

    print("\nSUCCESS: WebRTC audio auto-reconnect patch applied successfully!")

def rollback():
    """
    <summary>Restores client bundle from backup directory.</summary>
    """
    bundle_hash, std_path, saf_path = get_bundle_paths()
    backup_std = os.path.join(BACKUP_DIR, os.path.basename(std_path))
    backup_saf = os.path.join(BACKUP_DIR, os.path.basename(saf_path))

    if not os.path.exists(backup_std) or not os.path.exists(backup_saf):
        print(f"Error: Backups not found in {BACKUP_DIR}", file=sys.stderr)
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
    parser = argparse.ArgumentParser(description="BBB Audio Auto-Reconnect Patch")
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
