#!/usr/bin/env python3
"""
build_pipeline.py — Automated package build pipeline manager for com.uncode.ide APT repo.

Manages build state in build-state.json, determines next package chunk,
orchestrates Docker builds, and tracks success/failure.

Usage:
  python3 scripts/build_pipeline.py init           # Initialize state from termux-packages
  python3 scripts/build_pipeline.py status         # Show current build status
  python3 scripts/build_pipeline.py next [N]       # Build next N packages (default: 40)
  python3 scripts/build_pipeline.py retry-failed   # Retry all failed packages
  python3 scripts/build_pipeline.py reset          # Reset all state (start over)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

# ─── Configuration ────────────────────────────────────────────────────────────
CUSTOM_PACKAGE_NAME = "com.uncode.ide"
OFFICIAL_PACKAGE_NAME = "com.termux"
REPO_URL = "https://uncode-ide.github.io/repo"
DOCKER_IMAGE = "ghcr.io/termux/package-builder:latest"
TERMUX_PACKAGES_DIR = "termux-packages-main"
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(REPO_DIR, "debs")
STATE_FILE = os.path.join(REPO_DIR, "build-state.json")
CUSTOM_PACKAGES_DIR = os.path.join(REPO_DIR, "packages")

# Package directories to scan in termux-packages (in priority order)
PACKAGE_DIRS = ["packages", "root-packages"]

# Packages to always SKIP (broken, too heavy, or irrelevant)
SKIP_PACKAGES = {
    "swift",           # Broken container corruption
    "zeronet",         # Broken
    "openjdk-17",      # Requires special setup
    "openjdk-21",      # Requires special setup
    "rustc",           # Multi-hour build, handle separately
    "ghc",             # Haskell compiler, multi-hour
    "llvm",            # LLVM itself (clang is enough)
    "chromium",        # Too large
    "firefox",         # Too large
}

# Force these packages to build FIRST before others (critical bootstrap order)
PRIORITY_PACKAGES = [
    "ndk-sysroot",
    "libandroid-support",
    "libandroid-selinux",
    "libandroid-posix-semaphore",
    "ncurses",
    "readline",
    "zlib",
    "liblz4",
    "liblzma",
    "libzstd",
    "openssl",
    "ca-certificates",
    "libgmp",
    "libgpg-error",
    "libgcrypt",
    "libassuan",
    "libnpth",
    "gpgv",
    "dpkg",
    "bash",
    "dash",
    "coreutils",
    "termux-exec",
    "termux-am",
    "termux-tools",
    "termux-core",
    "termux-licenses",
    "debianutils",
    "apt",
    "curl",
]
# ─────────────────────────────────────────────────────────────────────────────


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return None


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    print(f"  ✓ State saved: {STATE_FILE}")


def get_all_termux_packages():
    """Scan termux-packages directory and return ordered list of all package names."""
    if not os.path.isdir(TERMUX_PACKAGES_DIR):
        print(f"[!] {TERMUX_PACKAGES_DIR} not found — clone it first")
        return []

    packages = []
    for pkg_dir_name in PACKAGE_DIRS:
        pkg_dir_path = os.path.join(TERMUX_PACKAGES_DIR, pkg_dir_name)
        if not os.path.isdir(pkg_dir_path):
            continue
        for name in sorted(os.listdir(pkg_dir_path)):
            if name in SKIP_PACKAGES:
                continue
            build_sh = os.path.join(pkg_dir_path, name, "build.sh")
            if os.path.isfile(build_sh):
                packages.append(name)

    # Reorder: priority packages first, then rest alphabetically
    priority = [p for p in PRIORITY_PACKAGES if p in packages]
    rest = [p for p in packages if p not in set(PRIORITY_PACKAGES)]
    return priority + rest


def get_published_packages():
    """Query gh-pages APT repo to get already-published packages."""
    published = set()
    try:
        url = f"{REPO_URL}/dists/uncode/main/binary-aarch64/Packages"
        with urllib.request.urlopen(url, timeout=15) as resp:
            for line in resp.read().decode("utf-8").splitlines():
                if line.startswith("Package: "):
                    published.add(line.split(": ", 1)[1].strip())
        print(f"  Found {len(published)} already-published package(s) in APT repo")
    except Exception as e:
        print(f"  [*] APT repo not reachable (first run?): {e}")
    return published


def clone_and_patch_termux_packages():
    """Clone termux-packages and apply com.uncode.ide patches."""
    if os.path.isdir(TERMUX_PACKAGES_DIR):
        print(f"[*] Using existing {TERMUX_PACKAGES_DIR} clone")
        return

    print("[*] Cloning termux-packages (shallow)...")
    subprocess.run(
        ["git", "clone", "--depth=1",
         "https://github.com/termux/termux-packages.git",
         TERMUX_PACKAGES_DIR],
        check=True
    )

    print("[*] Patching: com.termux → com.uncode.ide ...")
    skip_exts = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".tar",
                 ".gz", ".xz", ".deb", ".so", ".a", ".o", ".pyc", ".apk"}
    skip_dirs = {".git", "__pycache__"}
    count = 0
    for root, dirs, files in os.walk(TERMUX_PACKAGES_DIR):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in files:
            if any(fname.endswith(ext) for ext in skip_exts):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                if OFFICIAL_PACKAGE_NAME in content:
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(content.replace(OFFICIAL_PACKAGE_NAME, CUSTOM_PACKAGE_NAME))
                    count += 1
            except (IOError, OSError, PermissionError):
                pass
    print(f"  ✓ Patched {count} files")

    # CRITICAL: bypass the repo prefix mismatch guard that prevents
    # downloading pre-built deps from official termux mirrors
    _bypass_prefix_guard()


def _bypass_prefix_guard():
    """
    Bypass the check in termux-packages that prevents downloading
    pre-built .deb dependencies when the package name doesn't match
    the official com.termux repo. We need pre-built deps for compilation.
    """
    targets = [
        os.path.join(TERMUX_PACKAGES_DIR, "scripts", "build",
                     "termux_download_deb_pac.sh"),
        os.path.join(TERMUX_PACKAGES_DIR, "scripts",
                     "build-bootstraps.sh"),
        os.path.join(TERMUX_PACKAGES_DIR, "scripts", "build",
                     "termux_step_get_dependencies.sh"),
    ]
    guard_patterns = [
        # The actual guard check pattern (various forms)
        ('if [[ "$TERMUX_REPO_APP__PACKAGE_NAME" != "$TERMUX_APP_PACKAGE" ]]',
         'if false'),
        ('if [ "$TERMUX_REPO_APP__PACKAGE_NAME" != "$TERMUX_APP_PACKAGE" ]',
         'if false'),
        # Repo URL hardcoded to termux.dev — force it to still work
        ('packages.termux.dev/apt/termux-main',
         'packages.termux.dev/apt/termux-main'),  # keep same, deps download works
        # Prevent target package from being downloaded when -I is used
        ('done < <(./scripts/buildorder.py $([[ "${TERMUX_INSTALL_DEPS}" == "true" ]] && echo "-i") "$TERMUX_PKG_BUILDER_DIR" $TERMUX_PACKAGES_DIRECTORIES || echo "ERROR")',
         'done < <(./scripts/buildorder.py "$TERMUX_PKG_BUILDER_DIR" $TERMUX_PACKAGES_DIRECTORIES || echo "ERROR")'),
    ]
    for fpath in targets:
        if not os.path.exists(fpath):
            continue
        with open(fpath) as f:
            content = f.read()
        modified = False
        for old, new in guard_patterns:
            if old in content and old != new:
                content = content.replace(old, new)
                modified = True
        if modified:
            with open(fpath, "w") as f:
                f.write(content)
            print(f"  ✓ Bypassed prefix guard in {os.path.basename(fpath)}")


def build_package(pkg, arch="aarch64"):
    """Build a single package using termux Docker environment."""
    cmd = [
        "bash", "-c",
        f"cd {TERMUX_PACKAGES_DIR} && "
        f"scripts/run-docker.sh ./build-package.sh -a {arch} -I {pkg}"
    ]
    try:
        result = subprocess.run(
            cmd, timeout=1800,  # 30 min per package max
            capture_output=False
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"  ✗ Timeout: {pkg}")
        return False
    except Exception as e:
        print(f"  ✗ Error building {pkg}: {e}")
        return False


def collect_debs():
    """Collect all built .deb files into the OUTPUT_DIR."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    count = 0

    search_dirs = [
        os.path.join(TERMUX_PACKAGES_DIR, "output"),
        os.path.join(TERMUX_PACKAGES_DIR, "output", "aarch64"),
        os.path.join(TERMUX_PACKAGES_DIR, "output", "arm"),
        os.path.join(TERMUX_PACKAGES_DIR, "output", "x86_64"),
        os.path.join(TERMUX_PACKAGES_DIR, "debs"),
    ]

    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for fname in os.listdir(search_dir):
            if not fname.endswith(".deb"):
                continue
            src = os.path.join(search_dir, fname)
            dst = os.path.join(OUTPUT_DIR, fname)
            if os.path.abspath(src) == os.path.abspath(dst):
                continue
            try:
                shutil.move(src, dst)
                print(f"  ✓ Collected: {fname}")
                count += 1
            except OSError:
                shutil.copy2(src, dst)
                count += 1

    # Count what's already in OUTPUT_DIR
    total = sum(1 for f in os.listdir(OUTPUT_DIR) if f.endswith(".deb"))
    return total


def build_custom_packages():
    """Build pre-packaged custom packages from /packages directory."""
    skip = {"TEMPLATE"}
    built = 0
    if not os.path.isdir(CUSTOM_PACKAGES_DIR):
        return 0
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for pkg_name in os.listdir(CUSTOM_PACKAGES_DIR):
        if pkg_name in skip:
            continue
        pkg_dir = os.path.join(CUSTOM_PACKAGES_DIR, pkg_name)
        if not os.path.isfile(os.path.join(pkg_dir, "DEBIAN", "control")):
            continue
        try:
            subprocess.run(
                ["dpkg-deb", "-b", "-Zxz", pkg_dir, OUTPUT_DIR],
                check=True, capture_output=True
            )
            built += 1
        except subprocess.CalledProcessError:
            pass
    return built


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_init(args):
    """Initialize build state from termux-packages package list."""
    clone_and_patch_termux_packages()
    all_packages = get_all_termux_packages()
    published = get_published_packages()

    state = {
        "version": "2.0",
        "initialized_at": now_iso(),
        "last_run": None,
        "run_count": 0,
        "total_packages": len(all_packages),
        "chunk_size": getattr(args, "chunk_size", 40),
        "built": sorted(published),
        "failed": [],
        "pending": [p for p in all_packages if p not in published],
        "all_packages": all_packages,
    }
    save_state(state)
    print(f"\n  ✓ Initialized: {len(state['pending'])} packages pending, "
          f"{len(state['built'])} already built")


def cmd_status(args):
    """Print current build status."""
    state = load_state()
    if not state:
        print("[!] No build state found. Run: python3 scripts/build_pipeline.py init")
        return

    total = state["total_packages"]
    built = len(state["built"])
    failed = len(state["failed"])
    pending = len(state["pending"])
    pct = (built / total * 100) if total else 0

    print(f"\n{'='*50}")
    print(f"  Build Pipeline Status")
    print(f"{'='*50}")
    print(f"  Total packages: {total}")
    print(f"  Built:          {built} ({pct:.1f}%)")
    print(f"  Failed:         {failed}")
    print(f"  Pending:        {pending}")
    print(f"  Run count:      {state.get('run_count', 0)}")
    print(f"  Last run:       {state.get('last_run', 'never')}")
    if state["failed"]:
        print(f"\n  Failed: {', '.join(state['failed'][:20])}")
        if len(state["failed"]) > 20:
            print(f"          ... and {len(state['failed']) - 20} more")
    print(f"{'='*50}\n")


def cmd_next(args):
    """Build next chunk of packages and update state."""
    chunk_size = getattr(args, "n", 40)

    # Load or initialize state
    state = load_state()
    if not state:
        print("[*] No state found, initializing...")
        clone_and_patch_termux_packages()
        all_packages = get_all_termux_packages()
        published = get_published_packages()
        state = {
            "version": "2.0",
            "initialized_at": now_iso(),
            "last_run": None,
            "run_count": 0,
            "total_packages": len(all_packages),
            "chunk_size": chunk_size,
            "built": sorted(published),
            "failed": [],
            "pending": [p for p in all_packages if p not in published],
            "all_packages": all_packages,
        }

    if not state["pending"]:
        print("\n  ✓ ALL PACKAGES BUILT! Nothing pending.")
        # Still build custom packages
        build_custom_packages()
        return

    # Take next chunk
    chunk = state["pending"][:chunk_size]
    state["pending"] = state["pending"][chunk_size:]
    state["last_run"] = now_iso()
    state["run_count"] = state.get("run_count", 0) + 1

    print(f"\n[*] Building chunk #{state['run_count']}: "
          f"{len(chunk)} packages")
    print(f"    {', '.join(chunk)}")

    # Ensure termux-packages is cloned and patched
    clone_and_patch_termux_packages()

    # Build each package
    built_this_run = []
    failed_this_run = []
    arch = getattr(args, "arch", "aarch64")

    for pkg in chunk:
        print(f"\n  → [{chunk.index(pkg)+1}/{len(chunk)}] Building: {pkg}")
        success = build_package(pkg, arch)
        if success:
            built_this_run.append(pkg)
            if pkg not in state["built"]:
                state["built"].append(pkg)
            print(f"  ✓ Built: {pkg}")
        else:
            failed_this_run.append(pkg)
            if pkg not in state["failed"]:
                state["failed"].append(pkg)
            print(f"  ✗ Failed: {pkg}")

    # Collect built debs
    total_debs = collect_debs()

    # Also build custom packages
    custom_built = build_custom_packages()

    # Save updated state
    save_state(state)

    # Summary
    remaining = len(state["pending"])
    print(f"\n{'='*50}")
    print(f"  Chunk #{state['run_count']} Complete")
    print(f"{'='*50}")
    print(f"  Built this run:  {len(built_this_run)}")
    print(f"  Failed this run: {len(failed_this_run)}")
    print(f"  Custom packages: {custom_built}")
    print(f"  Total debs:      {total_debs}")
    print(f"  Remaining:       {remaining} packages")
    if failed_this_run:
        print(f"\n  ⚠ Failed: {', '.join(failed_this_run)}")
    print(f"{'='*50}\n")

    # Exit 0 even with failures (partial success = still publish)
    if total_debs == 0 and custom_built == 0:
        print("[!] Nothing to publish")
        sys.exit(1)


def cmd_retry_failed(args):
    """Move failed packages back to pending for retry."""
    state = load_state()
    if not state:
        print("[!] No state file found")
        sys.exit(1)

    failed = state["failed"]
    if not failed:
        print("  No failed packages to retry")
        return

    print(f"[*] Moving {len(failed)} failed packages back to pending...")
    state["pending"] = failed + state["pending"]
    state["failed"] = []
    save_state(state)
    print(f"  ✓ Ready to retry: {', '.join(failed)}")


def cmd_reset(args):
    """Reset build state completely."""
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
        print("  ✓ State file deleted")
    if os.path.isdir(TERMUX_PACKAGES_DIR):
        shutil.rmtree(TERMUX_PACKAGES_DIR)
        print(f"  ✓ {TERMUX_PACKAGES_DIR} deleted")
    print("  ✓ Reset complete — run 'init' to start fresh")


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Automated package build pipeline for com.uncode.ide APT repo"
    )
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Initialize build state")
    p_init.add_argument("--chunk-size", type=int, default=40)

    p_status = sub.add_parser("status", help="Show build status")

    p_next = sub.add_parser("next", help="Build next chunk")
    p_next.add_argument("n", nargs="?", type=int, default=40,
                        help="Number of packages to build")
    p_next.add_argument("--arch", default="aarch64")

    p_retry = sub.add_parser("retry-failed", help="Retry failed packages")
    p_retry.add_argument("--arch", default="aarch64")

    p_reset = sub.add_parser("reset", help="Reset all state")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "next": cmd_next,
        "retry-failed": cmd_retry_failed,
        "reset": cmd_reset,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
