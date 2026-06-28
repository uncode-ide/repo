# uncode-ide/repo

APT repository for Uncode IDE (`com.uncode.ide`).

## Install

Run this in your Uncode IDE terminal:

```sh
curl -fsSL https://uncode-ide.github.io/repo/install.sh | bash
```

That's it. The script adds the repo source, installs the GPG key, and runs `pkg update`.

## Manual setup

```sh
# Add repository source
echo "deb [arch=aarch64] https://uncode-ide.github.io/repo uncode main" \
  > $PREFIX/etc/apt/sources.list.d/uncode.list

# Install GPG signing key
curl -fsSL https://uncode-ide.github.io/repo/assets/uncode.gpg \
  -o $PREFIX/etc/apt/trusted.gpg.d/uncode.gpg

# Update and install
pkg update
pkg install <package-name>
```

## Remove

```sh
rm $PREFIX/etc/apt/sources.list.d/uncode.list
rm $PREFIX/etc/apt/trusted.gpg.d/uncode.gpg
pkg update
```

---

## Package system

Each package lives under `packages/<name>/` with two possible structures:

### 1. Static package (files pre-staged in tree)

No `build.sh` needed. Files are committed directly:

```
packages/hello/
  DEBIAN/control
  data/data/com.uncode.ide/files/usr/bin/hello
```

### 2. Prebuilt package (binary downloaded from upstream at CI time)

```
packages/fastfetch/
  DEBIAN/control
  build.sh          ← BUILD_TYPE=prebuilt
```

`build.sh` specifies where to download the binary from. No binaries committed to git.

### 3. Source build (cross-compiled in CI)

```
packages/mypackage/
  DEBIAN/control
  build.sh          ← BUILD_TYPE=source, BUILD_SYSTEM=cmake|make|go|python
```

CI cross-compiles for `aarch64` using `aarch64-linux-gnu` toolchain.

---

## Adding a package

### Static (small scripts, pre-built you already have)

```sh
cp -r packages/hello packages/my-package
# Edit DEBIAN/control
# Put files under packages/my-package/data/data/com.uncode.ide/files/usr/
git add packages/my-package/
git commit -m "feat: add my-package"
git push
```

### Prebuilt (upstream releases a binary/deb)

```sh
mkdir -p packages/my-package/DEBIAN
# Create DEBIAN/control
# Create build.sh with BUILD_TYPE=prebuilt
git add packages/my-package/
git commit -m "feat: add my-package"
git push
```

### Source build (compile from source)

```sh
mkdir -p packages/my-package/DEBIAN
# Create DEBIAN/control
# Create build.sh with BUILD_TYPE=source
git add packages/my-package/
git commit -m "feat: add my-package"
git push
```

---

## build.sh reference

```sh
PKG_NAME="my-package"
PKG_VERSION="1.0.0"
PKG_DESCRIPTION="What this does"
PKG_LICENSE="MIT"
PKG_HOMEPAGE="https://example.com"

# ── Option A: Prebuilt ──────────────────────────────────────────────────────
BUILD_TYPE="prebuilt"
PREBUILT_URL="https://example.com/releases/v${PKG_VERSION}/tool-linux-aarch64.deb"
PREBUILT_SHA256="abc123..."
PREBUILT_BIN_PATHS="usr/bin/tool"         # space-separated paths inside upstream deb
PREBUILT_SHARE_PATHS="usr/share/tool"     # optional

# ── Option B: Source (cmake) ────────────────────────────────────────────────
# BUILD_TYPE="source"
# SRC_URL="https://example.com/archive/v${PKG_VERSION}.tar.gz"
# SRC_SHA256="abc123..."
# BUILD_SYSTEM="cmake"           # cmake | make | go | python
# BUILD_DEPS="libfoo-dev"        # extra apt packages needed to build
# CMAKE_ARGS="-DBUILD_TESTS=OFF"
# INSTALL_BINS="usr/bin/tool"
# INSTALL_SHARE="usr/share/tool"

# ── Option C: Source (Go) ───────────────────────────────────────────────────
# BUILD_TYPE="source"
# SRC_URL="https://example.com/archive/v${PKG_VERSION}.tar.gz"
# SRC_SHA256="abc123..."
# BUILD_SYSTEM="go"
# GO_MAIN="./cmd/tool"
# INSTALL_BINS="usr/bin/tool"
```

---

## DEBIAN/control reference

```
Package: my-package
Version: 1.0.0-1
Architecture: aarch64
Maintainer: Uncode IDE <packages@uncode.ide>
Installed-Size: 512
Section: utils
Priority: optional
Homepage: https://example.com
Description: Short one-line description
 Longer description here.
 .
 Repackaged for com.uncode.ide namespace.
```

---

## GPG setup (first time only)

Add these to repo secrets (`Settings → Secrets → Actions`):

| Secret | Value |
|--------|-------|
| `PRIVATE_GPG_KEY` | `gpg --armor --export-secret-keys <KEY_ID>` |
| `GPG_PASSPHRASE` | Your passphrase, or leave blank |

---

## Repository info

| | |
|---|---|
| URL | `https://uncode-ide.github.io/repo` |
| Distribution | `uncode` |
| Component | `main` |
| Architecture | `aarch64` |
| GPG key | `https://uncode-ide.github.io/repo/assets/uncode.gpg` |
