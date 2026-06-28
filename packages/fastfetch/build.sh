# ── Package Recipe ──────────────────────────────────────────────────────────
# Sourced by CI build system. Do NOT execute directly.
#
# BUILD_TYPE=prebuilt  → download upstream binary/deb and repackage
# BUILD_TYPE=source    → cross-compile from source
# ─────────────────────────────────────────────────────────────────────────────

PKG_NAME="fastfetch"
PKG_VERSION="2.65.1"
PKG_HOMEPAGE="https://github.com/fastfetch-cli/fastfetch"
PKG_DESCRIPTION="Fast, feature-rich neofetch-like system information tool"
PKG_LICENSE="MIT"
PKG_ARCH="aarch64"
PKG_MAINTAINER="Uncode IDE <packages@uncode.ide>"
PKG_INSTALLED_SIZE="4096"
PKG_SECTION="utils"
PKG_PRIORITY="optional"

# ── Build type: prebuilt ─────────────────────────────────────────────────────
BUILD_TYPE="prebuilt"

# Upstream polyfilled deb (Android/Termux compatible)
PREBUILT_URL="https://github.com/fastfetch-cli/fastfetch/releases/download/${PKG_VERSION}/fastfetch-linux-aarch64-polyfilled.deb"
PREBUILT_SHA256="ff91b1fa3df9da16c2bd78da1b63d57afdfed82de0dec2506005e1819051aa01"

# Which files to extract from upstream deb (relative to deb root)
PREBUILT_BIN_PATHS="usr/bin/fastfetch"
PREBUILT_SHARE_PATHS="usr/share/fastfetch"

# ── Source build (alternative — uncomment to build from source) ───────────────
# BUILD_TYPE="source"
# SRC_URL="https://github.com/fastfetch-cli/fastfetch/archive/refs/tags/${PKG_VERSION}.tar.gz"
# SRC_SHA256="c4a9d191601bae302cfa9939f2b5666d2565e83229840cd00554c4913646f0ad"
# BUILD_SYSTEM="cmake"
# BUILD_DEPS="cmake ninja-build libvulkan-dev libpci-dev"
# CMAKE_ARGS="-DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=OFF"
# INSTALL_BINS="usr/bin/fastfetch"
# INSTALL_SHARE="usr/share/fastfetch"
