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

## Adding a package

1. Copy the `hello` package as a starting point:

```sh
cp -r packages/hello packages/my-package
```

2. Edit `packages/my-package/DEBIAN/control`:

```
Package: my-package
Version: 1.0.0-1
Architecture: aarch64
Maintainer: Uncode IDE <packages@uncode.ide>
Installed-Size: 512
Description: What this package does
```

3. Put your files under:

```
packages/my-package/data/data/com.uncode.ide/files/usr/
  bin/        ← executables
  lib/        ← libraries
  share/      ← data files
```

4. Push to `main`. GitHub Actions builds and deploys automatically.

---

## GPG setup (first time only)

Run this locally once before your first push:

```sh
chmod +x setup-gpg.sh && ./setup-gpg.sh
git add assets/
git commit -m "chore: add GPG public key"
git push
```

Add these to your repo secrets (`Settings → Secrets → Actions`):

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
