#!/usr/bin/env python3
"""
build_chunk.py — Orchestrates incremental package building for com.uncode.ide APT repo.

Usage:
  python3 scripts/build_chunk.py --tier tier-1
  python3 scripts/build_chunk.py --tier tier-2 --arch aarch64
  python3 scripts/build_chunk.py --packages bash,curl,git
  python3 scripts/build_chunk.py --list-tiers
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

CUSTOM_PACKAGE_NAME = "com.uncode.ide"
OFFICIAL_PACKAGE_NAME = "com.termux"
REPO_URL = "https://uncode-ide.github.io/repo"
DOCKER_IMAGE = "ghcr.io/termux/package-builder:latest"
CONTAINER_NAME = f"{CUSTOM_PACKAGE_NAME}-package-builder"
TIERS_FILE = os.path.join(os.path.dirname(__file__), "package_tiers.json")
CUSTOM_PACKAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "packages")
TERMUX_PACKAGES_DIR = "termux-packages-main"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "debs")


def load_tiers():
    with open(TIERS_FILE) as f:
        return json.load(f)["tiers"]


def list_tiers():
    tiers = load_tiers()
    for tier_name, tier_data in tiers.items():
        pkgs = ", ".join(tier_data["packages"])
        print(f"\n  [{tier_name}] {tier_data['description']}")
        print(f"    Packages ({len(tier_data['packages'])}): {pkgs}")


def get_published_packages():
    """Query gh-pages repo to get list of already-published packages with versions."""
    published = {}
    try:
        packages_url = f"{REPO_URL}/dists/uncode/main/binary-aarch64/Packages"
        with urllib.request.urlopen(packages_url, timeout=10) as resp:
            content = resp.read().decode("utf-8")
        current_pkg = {}
        for line in content.splitlines():
            if line.startswith("Package: "):
                current_pkg["name"] = line.split(": ", 1)[1].strip()
            elif line.startswith("Version: "):
                current_pkg["version"] = line.split(": ", 1)[1].strip()
            elif line == "" and "name" in current_pkg:
                published[current_pkg["name"]] = current_pkg.get("version", "0")
                current_pkg = {}
    except Exception as e:
        print(f"[*] Could not fetch published packages (may be first run): {e}")
    return published


def replace_package_name_in_file(filepath):
    """Replace com.termux with com.uncode.ide in a single file."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if OFFICIAL_PACKAGE_NAME in content:
            content = content.replace(OFFICIAL_PACKAGE_NAME, CUSTOM_PACKAGE_NAME)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True
    except (IOError, OSError):
        pass
    return False


def replace_package_name_in_dir(directory):
    """Recursively replace com.termux with com.uncode.ide in all text files."""
    count = 0
    skip_dirs = {".git", "__pycache__", ".repo"}
    skip_exts = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".tar", ".gz",
                 ".xz", ".deb", ".so", ".a", ".o", ".pyc"}
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in files:
            if any(fname.endswith(ext) for ext in skip_exts):
                continue
            fpath = os.path.join(root, fname)
            if replace_package_name_in_file(fpath):
                count += 1
    print(f"  ✓ Replaced '{OFFICIAL_PACKAGE_NAME}' → '{CUSTOM_PACKAGE_NAME}' in {count} files")


def clone_termux_packages():
    """Clone termux-packages if not already present."""
    if os.path.isdir(TERMUX_PACKAGES_DIR):
        print(f"[*] {TERMUX_PACKAGES_DIR} already exists, using existing clone.")
        return
    print("[*] Cloning termux-packages...")
    subprocess.run(
        ["git", "clone", "--depth=1",
         "https://github.com/termux/termux-packages.git",
         TERMUX_PACKAGES_DIR],
        check=True
    )
    print("[*] Applying com.uncode.ide name patch...")
    replace_package_name_in_dir(TERMUX_PACKAGES_DIR)


def build_packages_in_docker(packages, arch="aarch64"):
    """Run Docker container to cross-compile packages."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    packages_str = " ".join(packages)
    print(f"\n[*] Building {len(packages)} package(s) in Docker: {packages_str}")
    print(f"    Architecture: {arch}")

    # Docker run command that mounts the termux-packages directory
    # and runs the build script for the specified packages
    cmd = [
        "docker", "run", "--rm",
        "--name", CONTAINER_NAME,
        "-v", f"{os.path.abspath(TERMUX_PACKAGES_DIR)}:/home/builder/termux-packages",
        "-v", f"{os.path.abspath(OUTPUT_DIR)}:/home/builder/termux-packages/output",
        DOCKER_IMAGE,
        "bash", "-c",
        f"cd /home/builder/termux-packages && "
        f"for pkg in {packages_str}; do "
        f"  python3 scripts/run-docker.sh bash -c "
        f"  'cd /home/builder/termux-packages && "
        f"   ./build-package.sh -a {arch} -I $pkg' || true; "
        f"done"
    ]

    # Simpler approach: use termux-packages' own run-docker.sh per package
    results = {"built": [], "failed": [], "skipped": []}
    for pkg in packages:
        print(f"\n  → Building: {pkg}")
        build_cmd = [
            "bash", "-c",
            f"cd {TERMUX_PACKAGES_DIR} && "
            f"scripts/run-docker.sh ./build-package.sh -a {arch} -I {pkg}"
        ]
        try:
            result = subprocess.run(build_cmd, check=True, timeout=3600)
            results["built"].append(pkg)
            print(f"  ✓ Built: {pkg}")
        except subprocess.CalledProcessError:
            results["failed"].append(pkg)
            print(f"  ✗ Failed: {pkg}")
        except subprocess.TimeoutExpired:
            results["failed"].append(pkg)
            print(f"  ✗ Timeout: {pkg}")

    return results


def collect_debs():
    """Move built .deb files from termux-packages output dirs to our debs/ directory."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    count = 0

    # Search in multiple possible output locations
    search_dirs = [
        os.path.join(TERMUX_PACKAGES_DIR, "output"),
        os.path.join(TERMUX_PACKAGES_DIR, "debs"),
        "/data/data/.built-packages",  # Docker internal output
    ]

    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        # Walk recursively to catch nested arch subdirs
        for root, dirs, files in os.walk(search_dir):
            for fname in files:
                if fname.endswith(".deb"):
                    src = os.path.join(root, fname)
                    dst = os.path.join(OUTPUT_DIR, fname)
                    if os.path.abspath(src) == os.path.abspath(dst):
                        continue  # Already in place
                    try:
                        os.rename(src, dst)
                        print(f"  ✓ Collected: {fname}")
                        count += 1
                    except OSError:
                        import shutil
                        shutil.copy2(src, dst)
                        print(f"  ✓ Copied: {fname}")
                        count += 1

    # Also count any debs already in OUTPUT_DIR (placed directly by Docker)
    existing = sum(1 for f in os.listdir(OUTPUT_DIR) if f.endswith(".deb"))
    if existing > count:
        print(f"  ✓ {existing - count} deb(s) already in debs/ directory")
        count = existing

    return count


def build_custom_packages():
    """Build custom packages from the /packages directory (non-source, pre-built debs)."""
    if not os.path.isdir(CUSTOM_PACKAGES_DIR):
        return

    skip_dirs = {"TEMPLATE"}
    built = 0
    for pkg_name in os.listdir(CUSTOM_PACKAGES_DIR):
        if pkg_name in skip_dirs:
            continue
        pkg_dir = os.path.join(CUSTOM_PACKAGES_DIR, pkg_name)
        control_file = os.path.join(pkg_dir, "DEBIAN", "control")
        if not os.path.isfile(control_file):
            continue

        print(f"  → Building custom package: {pkg_name}")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        try:
            subprocess.run(
                ["dpkg-deb", "-b", "-Zxz", pkg_dir, OUTPUT_DIR],
                check=True
            )
            print(f"  ✓ Built custom: {pkg_name}")
            built += 1
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Failed custom: {pkg_name}: {e}")

    return built


def main():
    parser = argparse.ArgumentParser(
        description="Build packages incrementally for com.uncode.ide APT repo"
    )
    parser.add_argument("--tier", help="Build all packages in a tier (e.g. tier-1)")
    parser.add_argument("--packages", help="Comma-separated list of specific packages to build")
    parser.add_argument("--arch", default="aarch64", help="Target architecture (default: aarch64)")
    parser.add_argument("--skip-check", action="store_true",
                        help="Skip checking already-published packages")
    parser.add_argument("--custom-only", action="store_true",
                        help="Only build custom packages from /packages dir")
    parser.add_argument("--list-tiers", action="store_true", help="List all tiers and their packages")
    args = parser.parse_args()

    if args.list_tiers:
        list_tiers()
        return

    print("\n" + "=" * 60)
    print("  Uncode IDE Package Builder")
    print(f"  Custom App:  {CUSTOM_PACKAGE_NAME}")
    print(f"  Repo URL:    {REPO_URL}")
    print(f"  Arch:        {args.arch}")
    print("=" * 60 + "\n")

    # Handle custom-only mode
    if args.custom_only:
        print("[*] Building custom packages only...")
        count = build_custom_packages()
        print(f"\n  ✓ Built {count} custom package(s) into debs/")
        return

    # Get list of already published packages
    published = {}
    if not args.skip_check:
        print("[*] Checking already-published packages...")
        published = get_published_packages()
        if published:
            print(f"  Found {len(published)} already-published package(s)")
        else:
            print("  No published packages found (or first run)")

    # Determine which packages to build
    packages_to_build = []

    if args.tier:
        tiers = load_tiers()
        if args.tier not in tiers:
            print(f"[!] Unknown tier '{args.tier}'. Use --list-tiers to see available tiers.")
            sys.exit(1)
        tier_packages = tiers[args.tier]["packages"]
        print(f"[*] Tier '{args.tier}': {len(tier_packages)} package(s)")

        for pkg in tier_packages:
            if pkg in published and not args.skip_check:
                print(f"  → Skipping (already published): {pkg} ({published[pkg]})")
            else:
                packages_to_build.append(pkg)

    elif args.packages:
        packages_to_build = [p.strip() for p in args.packages.split(",") if p.strip()]
        # Filter already published
        if not args.skip_check:
            packages_to_build = [p for p in packages_to_build if p not in published]

    else:
        print("[!] Specify --tier, --packages, --custom-only, or --list-tiers")
        parser.print_help()
        sys.exit(1)

    if not packages_to_build:
        print("\n  ✓ All packages already published — nothing to build!")
        # Still build custom packages
        build_custom_packages()
        return

    print(f"\n[*] Packages to build ({len(packages_to_build)}): {', '.join(packages_to_build)}")

    # Clone and patch termux-packages
    clone_termux_packages()

    # Build packages in Docker
    results = build_packages_in_docker(packages_to_build, args.arch)

    # Collect .deb files to debs/
    collected = collect_debs()

    # Also build custom packages from /packages dir
    custom_built = build_custom_packages()

    print("\n" + "=" * 60)
    print("  Build Summary")
    print("=" * 60)
    print(f"  Built:     {len(results['built'])}")
    print(f"  Failed:    {len(results['failed'])}")
    print(f"  Custom:    {custom_built}")
    print(f"  Collected: {collected} .deb file(s)")
    if results["failed"]:
        print(f"\n  ⚠ Failed packages: {', '.join(results['failed'])}")
        print("    These can be retried with: --packages " + ",".join(results["failed"]))
    print("=" * 60 + "\n")

    # Only fail hard if NOTHING was built at all (not even partial success)
    total_built = len(results["built"]) + (custom_built or 0)
    if total_built == 0 and collected == 0:
        print("[!] Nothing built — aborting")
        sys.exit(1)
    # Partial failures = warning only, publish what we have
    if results["failed"]:
        print(f"[!] WARNING: {len(results['failed'])} package(s) failed — but publishing {collected} successful deb(s)")


if __name__ == "__main__":
    main()
