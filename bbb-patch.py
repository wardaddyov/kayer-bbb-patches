#!/usr/bin/env python3
"""
<summary>
Unified CLI tool to manage BigBlueButton client patches across versions.
Discovers available patches in the `patches/` directory, checks their status,
and provides commands to apply or rollback specific patches.
</summary>
"""

import os
import sys
import json
import argparse
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PATCHES_DIR = os.path.join(SCRIPT_DIR, "patches")

def discover_patches():
    """
    <summary>Recursively discovers all patch metadata files in patches/.</summary>
    <returns>List of dicts containing patch information and paths.</returns>
    """
    patches = []
    if not os.path.exists(PATCHES_DIR):
        return patches

    for root, _, files in os.walk(PATCHES_DIR):
        if "metadata.json" in files and "patch.py" in files:
            meta_file = os.path.join(root, "metadata.json")
            script_file = os.path.join(root, "patch.py")
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["_path"] = script_file
                meta["_dir"] = root
                patches.append(meta)
            except Exception as e:
                print(f"Warning: Failed to load metadata from {meta_file}: {e}", file=sys.stderr)

    return patches

def list_patches(patches):
    """
    <summary>Displays all available patches and their target BigBlueButton versions.</summary>
    """
    print(f"\nAvailable BigBlueButton Patches ({len(patches)} total):")
    print("=" * 70)
    for p in patches:
        pid = p.get("id", "unknown")
        name = p.get("name", "Unknown")
        ver = p.get("version", "1.0.0")
        target = ", ".join(p.get("target_bbb_versions", []))
        desc = p.get("description", "")
        print(f"• ID:          {pid} (v{ver})")
        print(f"  Name:        {name}")
        print(f"  Target BBB:  {target}")
        print(f"  Description: {desc}")
        print("-" * 70)

def find_patch(patches, patch_id):
    for p in patches:
        if p.get("id") == patch_id:
            return p
    return None

def main():
    parser = argparse.ArgumentParser(
        description="Kayer BigBlueButton Patch Manager",
        epilog="Examples:\n  python3 bbb-patch.py list\n  python3 bbb-patch.py check audio-autojoin-muted\n  python3 bbb-patch.py apply audio-autojoin-muted\n  python3 bbb-patch.py rollback audio-autojoin-muted\n",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    subparsers.add_parser("list", help="List all available patches")

    check_parser = subparsers.add_parser("check", help="Check status of a patch on this server")
    check_parser.add_argument("patch_id", help="Patch ID (e.g. audio-autojoin-muted)")

    apply_parser = subparsers.add_parser("apply", help="Apply a patch to this server")
    apply_parser.add_argument("patch_id", help="Patch ID (e.g. audio-autojoin-muted)")

    rb_parser = subparsers.add_parser("rollback", help="Rollback an applied patch")
    rb_parser.add_argument("patch_id", help="Patch ID (e.g. audio-autojoin-muted)")

    args = parser.parse_args()
    patches = discover_patches()

    if not args.command or args.command == "list":
        list_patches(patches)
        return

    patch = find_patch(patches, args.patch_id)
    if not patch:
        print(f"Error: Patch '{args.patch_id}' not found. Run 'python3 bbb-patch.py list' to see available patches.", file=sys.stderr)
        sys.exit(1)

    script_path = patch["_path"]

    if args.command == "check":
        subprocess.run([sys.executable, script_path, "--check"])
    elif args.command == "apply":
        subprocess.run([sys.executable, script_path, "--patch"])
    elif args.command == "rollback":
        subprocess.run([sys.executable, script_path, "--rollback"])

if __name__ == "__main__":
    main()
