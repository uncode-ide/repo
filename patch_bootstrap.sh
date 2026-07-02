#!/usr/bin/env bash
##
## Patch a pre-built Termux bootstrap archive to use custom apt repo
## Usage: ./patch_bootstrap.sh <bootstrap-file> [gpg-key-file]
##
## Example:
##   ./patch_bootstrap.sh bootstrap-aarch64.zip assets/uncode.gpg
##   ./patch_bootstrap.sh bootstrap-aarch64.tar.xz assets/uncode.gpg
##

set -e

CUSTOM_REPO_URL="https://uncode-ide.github.io/repo"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GPG_KEY="${2:-$SCRIPT_DIR/assets/uncode.gpg}"

if [ -z "$1" ]; then
    echo "Usage: $0 <bootstrap-file> [gpg-key-file]"
    echo ""
    echo "Example:"
    echo "  $0 bootstrap-aarch64.zip"
    echo "  $0 bootstrap-aarch64.tar.xz /path/to/uncode.gpg"
    exit 1
fi

BOOTSTRAP_FILE="$(realpath "$1")"
BOOTSTRAP_NAME="$(basename "$BOOTSTRAP_FILE")"

# Detect architecture from filename (e.g. bootstrap-aarch64.zip -> aarch64)
ARCH=$(echo "$BOOTSTRAP_NAME" | sed -E 's/bootstrap-([a-z0-9_]+)\..*/\1/')
if [ -z "$ARCH" ]; then
    ARCH="aarch64"
    echo "[*] Could not detect architecture from filename, defaulting to: $ARCH"
fi

if [ ! -f "$BOOTSTRAP_FILE" ]; then
    echo "[!] Bootstrap file not found: $BOOTSTRAP_FILE"
    exit 1
fi

if [ ! -f "$GPG_KEY" ]; then
    echo "[!] GPG key file not found: $GPG_KEY"
    echo "    Specify path as second argument, or place uncode.gpg in assets/"
    exit 1
fi

echo ""
echo "========================================="
echo "  Patching Bootstrap: $BOOTSTRAP_NAME"
echo "  Architecture: $ARCH"
echo "  GPG Key: $GPG_KEY"
echo "========================================="
echo ""

# Create temp working directory
WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/bootstrap-patch.XXXXXXXX")
trap 'rm -rf "$WORK_DIR"' EXIT

EXTRACT_DIR="$WORK_DIR/rootfs"
mkdir -p "$EXTRACT_DIR"

# Detect format and extract
if [[ "$BOOTSTRAP_FILE" == *.zip ]]; then
    FORMAT="zip"
    echo "[1/5] Extracting ZIP archive..."
    unzip -q "$BOOTSTRAP_FILE" -d "$EXTRACT_DIR"
elif [[ "$BOOTSTRAP_FILE" == *.tar.xz ]]; then
    FORMAT="tar.xz"
    echo "[1/5] Extracting TAR.XZ archive..."
    tar xf "$BOOTSTRAP_FILE" -C "$EXTRACT_DIR"
else
    echo "[!] Unknown format. Supported: .zip, .tar.xz"
    exit 1
fi

echo "    ✓ Extracted to temp directory"

# Find the etc/apt directory (could be at root or inside a prefix path)
APT_DIR=""
if [ -d "$EXTRACT_DIR/etc/apt" ]; then
    APT_DIR="$EXTRACT_DIR/etc/apt"
elif [ -d "$EXTRACT_DIR/data/data/"*"/files/usr/etc/apt" ]; then
    APT_DIR=$(find "$EXTRACT_DIR/data" -path "*/etc/apt" -type d | head -1)
fi

if [ -z "$APT_DIR" ] || [ ! -d "$APT_DIR" ]; then
    echo "[!] Could not find etc/apt directory in the archive."
    echo "    Directory contents:"
    ls -la "$EXTRACT_DIR/"
    echo ""
    echo "    Looking deeper..."
    find "$EXTRACT_DIR" -name "apt" -type d 2>/dev/null || echo "    No apt directory found"
    exit 1
fi

echo "[2/5] Found apt config at: ${APT_DIR#$EXTRACT_DIR/}"

# Patch sources.list — remove/replace official Termux repo entries
echo "[3/5] Patching apt sources..."

# a) Main sources.list: replace official Termux URLs with our repo
if [ -f "$APT_DIR/sources.list" ]; then
    echo "    Old sources.list:"
    cat "$APT_DIR/sources.list" | sed 's/^/    > /'

    # Replace official Termux repo URLs
    sed -i \
        -e 's|https://packages-cf.termux.dev/apt/termux-main/\? *stable *main|https://uncode-ide.github.io/repo uncode main|g' \
        -e 's|https://packages.termux.dev/apt/termux-main/\? *stable *main|https://uncode-ide.github.io/repo uncode main|g' \
        "$APT_DIR/sources.list"

    echo "    New sources.list:"
    cat "$APT_DIR/sources.list" | sed 's/^/    > /'
else
    echo "    No existing sources.list found, creating new one..."
    echo "deb ${CUSTOM_REPO_URL} uncode main" > "$APT_DIR/sources.list"
fi

# Add GPG key
echo "[4/5] Adding GPG key..."
mkdir -p "$APT_DIR/trusted.gpg.d"
cp "$GPG_KEY" "$APT_DIR/trusted.gpg.d/uncode.gpg"
echo "    ✓ GPG key added to trusted.gpg.d/uncode.gpg"

# Re-create the archive
echo "[5/5] Creating patched archive..."

# Backup original
BACKUP_FILE="${BOOTSTRAP_FILE}.bak"
cp "$BOOTSTRAP_FILE" "$BACKUP_FILE"
echo "    ✓ Original backed up to: $(basename "$BACKUP_FILE")"

if [ "$FORMAT" = "zip" ]; then
    # For zip: recreate from extracted contents
    rm "$BOOTSTRAP_FILE"
    (cd "$EXTRACT_DIR" && zip -r9 "$BOOTSTRAP_FILE" ./*)
elif [ "$FORMAT" = "tar.xz" ]; then
    rm "$BOOTSTRAP_FILE"
    (cd "$EXTRACT_DIR" && XZ_OPT=-e9 tar cJf "$BOOTSTRAP_FILE" ./*)
fi

echo "    ✓ Patched archive created: $(basename "$BOOTSTRAP_FILE")"

# Show final size
ORIG_SIZE=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE")
NEW_SIZE=$(stat -c%s "$BOOTSTRAP_FILE" 2>/dev/null || stat -f%z "$BOOTSTRAP_FILE")
echo ""
echo "========================================="
echo "  ✓ Patching Complete!"
echo "  Architecture: $ARCH"
echo "  Original size: $(echo "$ORIG_SIZE" | awk '{printf "%.2f MB", $1/1024/1024}')"
echo "  Patched size:  $(echo "$NEW_SIZE" | awk '{printf "%.2f MB", $1/1024/1024}')"
echo "  Backup saved:  $(basename "$BACKUP_FILE")"
echo ""
echo "  trusted.gpg.d/uncode.gpg: ✓"
echo "========================================="
echo ""
