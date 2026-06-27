#!/data/data/com.uncode.ide/files/usr/bin/bash

REPO_URL="https://uncode-ide.github.io/repo"
SOURCES_DIR="$PREFIX/etc/apt/sources.list.d"
TRUSTED_DIR="$PREFIX/etc/apt/trusted.gpg.d"
SOURCE_FILE="$SOURCES_DIR/uncode.list"
GPG_FILE="$TRUSTED_DIR/uncode.gpg"

info()    { echo -e "\e[36minfo\e[0m  $1"; }
success() { echo -e "\e[32msuccess\e[0m $1"; }
warn()    { echo -e "\e[33mwarn\e[0m  $1"; }
error()   { echo -e "\e[31merror\e[0m $1"; exit 1; }

echo ""
info "Setting up Uncode IDE package repository..."
echo ""

# Check curl
if ! command -v curl &> /dev/null; then
  info "Installing curl..."
  apt install curl -y > /dev/null 2>&1 || error "curl is required but could not be installed"
  success "curl installed"
fi

# Create dirs
mkdir -p "$SOURCES_DIR" "$TRUSTED_DIR" || error "Failed to create APT directories"

# Download GPG key
info "Downloading GPG signing key..."
if curl -fsSL "${REPO_URL}/assets/uncode.gpg" -o "$GPG_FILE" 2>/dev/null && [ -s "$GPG_FILE" ]; then
  success "GPG key installed"
  SOURCE_ENTRY="deb [arch=aarch64] ${REPO_URL} uncode main"
else
  warn "GPG key unavailable, falling back to trusted mode"
  SOURCE_ENTRY="deb [trusted=yes arch=aarch64] ${REPO_URL} uncode main"
fi

# Add source
info "Adding repository source..."
echo "$SOURCE_ENTRY" > "$SOURCE_FILE" || error "Failed to write sources.list entry"
success "Repository added"

# Update
info "Running apt update..."
if apt update -y > /dev/null 2>&1; then
  success "Package list updated"
else
  warn "apt update had errors, but repository was added"
fi

echo ""
echo "  Uncode IDE repository is ready."
echo ""
echo "  Install packages:"
echo "    pkg install <package-name>"
echo ""
echo "  Repository: ${REPO_URL}"
echo ""
