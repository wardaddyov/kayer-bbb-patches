#!/usr/bin/env python3
"""
<summary>
Unified CLI tool to manage BigBlueButton client patches across versions.
Discovers available patches in the `patches/` directory, checks their status,
and provides commands to apply or rollback specific patches or all patches at once.
</summary>
<remarks>
Coding Standards:
- Compliant with repository rules requiring XML summaries and clear inline comments.
- Supports batch commands (--all) and granular per-patch lifecycle operations.
</remarks>
"""

import os
import sys
import json
import argparse
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
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

    # Sort patches deterministically by ID
    patches.sort(key=lambda p: p.get("id", ""))
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
        category = p.get("category", "general")
        print(f"• ID:          {pid} (v{ver}) [{category}]")
        print(f"  Name:        {name}")
        print(f"  Target BBB:  {target}")
        print(f"  Description: {desc}")
        print("-" * 70)

def find_patch(patches, patch_id):
    """
    <summary>Finds a single patch dict by its ID.</summary>
    """
    for p in patches:
        if p.get("id") == patch_id:
            return p
    return None

def execute_command_on_patch(patch, action):
    """
    <summary>Executes check, patch, or rollback action on a specific patch.</summary>
    <param name="patch">The patch metadata dict.</param>
    <param name="action">One of: check, apply, rollback.</param>
    <returns>Process exit code.</returns>
    """
    script_path = patch["_path"]
    pid = patch.get("id")
    name = patch.get("name")

    flag_map = {
        "check": "--check",
        "apply": "--patch",
        "rollback": "--rollback"
    }
    flag = flag_map.get(action, "--check")

    print(f"\n>>> [{action.upper()}] {name} ({pid})")
    print("-" * 60)
    res = subprocess.run([sys.executable, script_path, flag])
    return res.returncode

def main():
    parser = argparse.ArgumentParser(
        description="Kayer BigBlueButton Patch Manager",
        epilog="Examples:\n  python3 bbb-patch.py list\n  python3 bbb-patch.py check --all\n  python3 bbb-patch.py apply audio-autojoin-muted\n  python3 bbb-patch.py apply --all\n  python3 bbb-patch.py rollback --all\n",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    subparsers.add_parser("list", help="List all available patches")

    check_parser = subparsers.add_parser("check", help="Check status of patch(es) on this server")
    check_parser.add_argument("patch_id", nargs="?", default="--all", help="Patch ID or omit/--all for all")
    check_parser.add_argument("--all", action="store_true", help="Check all patches")

    apply_parser = subparsers.add_parser("apply", help="Apply patch(es) to this server")
    apply_parser.add_argument("patch_id", nargs="?", default="", help="Patch ID (e.g. audio-autojoin-muted) or 'all'")
    apply_parser.add_argument("--all", action="store_true", help="Apply all patches")

    rb_parser = subparsers.add_parser("rollback", help="Rollback patch(es)")
    rb_parser.add_argument("patch_id", nargs="?", default="", help="Patch ID or 'all'")
    rb_parser.add_argument("--all", action="store_true", help="Rollback all patches")

    args = parser.parse_args()
    patches = discover_patches()

    if not args.command or args.command == "list":
        list_patches(patches)
        return

    # Determine if action targets all patches
    is_all = getattr(args, "all", False) or getattr(args, "patch_id", "") in ("all", "--all")
    target_id = getattr(args, "patch_id", "")

    if is_all or not target_id:
        if args.command not in ("check", "apply", "rollback"):
            parser.print_help()
            return

        print(f"\nExecuting '{args.command}' across all {len(patches)} available patches...")
        for p in patches:
            execute_command_on_patch(p, args.command)
        return

    # Single patch action
    patch = find_patch(patches, target_id)
    if not patch:
        print(f"Error: Patch '{target_id}' not found. Run 'python3 bbb-patch.py list' to view available patches.", file=sys.stderr)
        sys.exit(1)

    ret = execute_command_on_patch(patch, args.command)
    sys.exit(ret)

if __name__ == "__main__":
    main()
