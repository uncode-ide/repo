#!/usr/bin/env python3
"""
Build a minimal ~25MB bootstrap-aarch64.zip for com.uncode package name.
Includes on-the-fly patching hooks for installing packages from official Termux repos.
"""

import os
import sys
import subprocess
import shutil

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TERMUX_PACKAGES_DIR = os.path.join(REPO_DIR, "termux-packages-main")
CUSTOM_PACKAGE_NAME = "com.uncode"  # Exactly 10 characters!
OFFICIAL_PACKAGE_NAME = "com.termux" # Exactly 10 characters!

def check_package_name_length():
    if len(CUSTOM_PACKAGE_NAME) != len(OFFICIAL_PACKAGE_NAME):
        print(f"ERROR: Custom package name '{CUSTOM_PACKAGE_NAME}' ({len(CUSTOM_PACKAGE_NAME)} chars) "
              f"must be EXACTLY {len(OFFICIAL_PACKAGE_NAME)} characters long (like '{OFFICIAL_PACKAGE_NAME}')!")
        sys.exit(1)
    print(f"✓ Package name '{CUSTOM_PACKAGE_NAME}' is exactly {len(CUSTOM_PACKAGE_NAME)} bytes (10-byte rule satisfied).")

def ensure_termux_packages():
    if not os.path.exists(TERMUX_PACKAGES_DIR):
        print("[*] Cloning termux-packages repository...")
        subprocess.run([
            "git", "clone", "--depth=1", "https://github.com/termux/termux-packages.git", TERMUX_PACKAGES_DIR
        ], check=True)
    else:
        print("[*] Using existing termux-packages clone.")

def patch_package_name():
    print(f"[*] Patching package name: {OFFICIAL_PACKAGE_NAME} -> {CUSTOM_PACKAGE_NAME}...")
    properties_path = os.path.join(TERMUX_PACKAGES_DIR, "scripts", "properties.sh")
    if os.path.exists(properties_path):
        with open(properties_path, "r") as f:
            content = f.read()
        content = content.replace(f'TERMUX_APP_PACKAGE="{OFFICIAL_PACKAGE_NAME}"', f'TERMUX_APP_PACKAGE="{CUSTOM_PACKAGE_NAME}"')
        content = content.replace(f'TERMUX_APP_PACKAGE={OFFICIAL_PACKAGE_NAME}', f'TERMUX_APP_PACKAGE={CUSTOM_PACKAGE_NAME}')
        with open(properties_path, "w") as f:
            f.write(content)
        print("  ✓ Updated properties.sh")

    # 1. APT Pinning Hook: Prevent 'pkg upgrade' from overwriting our compiled dpkg/apt with upstream com.termux binaries
    apt_pref_dir = os.path.join(TERMUX_PACKAGES_DIR, "packages", "apt", "etc-apt-preferences.d")
    os.makedirs(apt_pref_dir, exist_ok=True)
    pin_file = os.path.join(apt_pref_dir, "uncode-pin-dpkg")
    with open(pin_file, "w") as f:
        f.write('''Package: dpkg apt termux-exec termux-keyring termux-tools
Pin: release *
Pin-Priority: 1001
''')
    print("  ✓ Added APT pin preference to lock dpkg/apt against upstream overwrite")

    # 2. APT Post-Invoke Hook: On-the-fly patching of maintainer scripts & status DB for upstream debs
    apt_hook_dir = os.path.join(TERMUX_PACKAGES_DIR, "packages", "apt", "etc-apt-apt.conf.d")
    os.makedirs(apt_hook_dir, exist_ok=True)
    hook_file = os.path.join(apt_hook_dir, "99uncode-rewrite-postinst")
    with open(hook_file, "w") as f:
        f.write(f'''// On-the-fly patching hook for com.uncode
DPkg::Post-Invoke {{
    "if [ -d /data/data/{CUSTOM_PACKAGE_NAME}/files/usr/var/lib/dpkg/info ]; then sed -i 's|/data/data/{OFFICIAL_PACKAGE_NAME}/|/data/data/{CUSTOM_PACKAGE_NAME}/|g' /data/data/{CUSTOM_PACKAGE_NAME}/files/usr/var/lib/dpkg/info/* /data/data/{CUSTOM_PACKAGE_NAME}/files/usr/var/lib/dpkg/status 2>/dev/null || true; fi";
}};
''')
    print("  ✓ Added APT post-invoke hook for on-the-fly maintainer script patching")

def build_bootstrap(arch="aarch64"):
    print(f"[*] Building minimal bootstrap zip for {arch}...")
    cmd = [
        "bash", "-c",
        f"cd {TERMUX_PACKAGES_DIR} && "
        f"./scripts/run-docker.sh ./scripts/build-bootstraps.sh --architectures {arch}"
    ]
    subprocess.run(cmd, check=True)

    # Move output bootstrap zip to repo root
    output_dir = os.path.join(REPO_DIR, "dist")
    os.makedirs(output_dir, exist_ok=True)
    
    # Locate built zip
    built_zip_dir = os.path.join(TERMUX_PACKAGES_DIR, "bootstrap-archives")
    if os.path.exists(built_zip_dir):
        for f in os.listdir(built_zip_dir):
            if f.endswith(".zip"):
                src = os.path.join(built_zip_dir, f)
                dst = os.path.join(output_dir, f"uncode-bootstrap-{arch}.zip")
                shutil.copy(src, dst)
                size_mb = os.path.getsize(dst) / (1024 * 1024)
                print(f"\n==================================================")
                print(f" SUCCESS: Minimal Bootstrap Built!")
                print(f" Output: {dst}")
                print(f" File Size: {size_mb:.2f} MB")
                print(f"==================================================\n")
                return dst
    print("[!] Warning: Could not find output zip in bootstrap-archives directory.")
    return None

if __name__ == "__main__":
    check_package_name_length()
    ensure_termux_packages()
    patch_package_name()
    build_bootstrap("aarch64")
