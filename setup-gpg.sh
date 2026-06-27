#!/usr/bin/env bash
# setup-gpg.sh — Run ONCE locally to export your GPG public key into assets/
# Usage: chmod +x setup-gpg.sh && ./setup-gpg.sh

set -e

KEY_ID="1A667B2A5E7FFC5642A27D6B8AC53265FB7C2ABC"
ASSETS_DIR="assets"

echo "=== Exporting GPG public key ==="
mkdir -p "$ASSETS_DIR"

gpg --export "$KEY_ID" > "$ASSETS_DIR/uncode.gpg"
echo "✓ Binary key  → $ASSETS_DIR/uncode.gpg"

gpg --armor --export "$KEY_ID" > "$ASSETS_DIR/uncode.asc"
echo "✓ Armored key → $ASSETS_DIR/uncode.asc"

echo ""
echo "=== Private key for GitHub Secret PRIVATE_GPG_KEY ==="
echo "Run and copy the output:"
echo ""
echo "  gpg --armor --export-secret-keys $KEY_ID"
echo ""
echo "=== Next steps ==="
echo "  git add assets/"
echo "  git commit -m 'chore: add GPG public key'"
echo "  git push"
