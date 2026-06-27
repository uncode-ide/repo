# Uncode IDE — Custom APT Repository

A self-hosted APT repository for [Uncode IDE](https://github.com/your-org/uncode-ide) (`com.uncode.ide`), built automatically via GitHub Actions and hosted on GitHub Pages.

---

## 📦 Using This Repo in Uncode IDE

In your Uncode IDE terminal:

```sh
# Add the source
echo "deb [trusted=yes] https://YOUR_GITHUB_USERNAME.github.io/YOUR_REPO_NAME uncode-stable main" \
  > $PREFIX/etc/apt/sources.list.d/uncode.list

# Update and install
pkg update
pkg install bash curl python vim
```

Replace `YOUR_GITHUB_USERNAME` and `YOUR_REPO_NAME` with your actual GitHub details.

---

## 🗂️ Repository Structure

```
.
├── .github/
│   └── workflows/
│       └── build-deploy.yml     # CI: builds .deb files + deploys to gh-pages
├── packages/
│   ├── TEMPLATE/                # Copy this to add a new package
│   │   └── DEBIAN/
│   │       └── control          # Package metadata
│   ├── bash/                    # Example package
│   │   ├── DEBIAN/
│   │   │   ├── control
│   │   │   └── postinst         # (optional) post-install script
│   │   └── data/
│   │       └── data/com.uncode.ide/files/usr/bin/bash
│   ├── curl/
│   ├── python/
│   └── vim/
├── scripts/
│   └── gen_index.py             # Generates HTML index page for gh-pages
└── README.md
```

---

## ➕ Adding a New Package

1. **Copy the template:**
   ```sh
   cp -r packages/TEMPLATE packages/my-package
   ```

2. **Edit `DEBIAN/control`:**
   ```
   Package: my-package
   Version: 1.0.0-1
   Architecture: aarch64
   Maintainer: Uncode IDE <packages@uncode.ide>
   Installed-Size: 512
   Depends: libc (>= 2.17)
   Section: utils
   Priority: optional
   Description: My custom package
    Repackaged for com.uncode.ide namespace.
   ```

3. **Add your files** under `packages/my-package/data/data/com.uncode.ide/files/usr/`:
   ```
   packages/my-package/
   └── data/
       └── data/
           └── com.uncode.ide/
               └── files/
                   └── usr/
                       ├── bin/my-tool
                       ├── lib/libmything.so
                       └── share/doc/my-package/copyright
   ```

4. **Push to `main`** — GitHub Actions will build and deploy automatically.

---

## 🔐 GPG Signing Setup

The repo is signed with GPG. You need to add two secrets to your GitHub repo:

| Secret | Description |
|--------|-------------|
| `PRIVATE_GPG_KEY` | Your exported private GPG key (armored) |
| `GPG_PASSPHRASE` | Passphrase for the key (or empty string if none) |

### Generate a GPG key:
```sh
gpg --full-generate-key
# Choose: RSA (4096 bits), no expiry, fill in name/email

# Export private key
gpg --armor --export-secret-keys YOUR_KEY_ID > private.asc
# Paste contents of private.asc into GitHub secret: PRIVATE_GPG_KEY
```

### Add the public key to Uncode IDE:
```sh
# On your development machine:
gpg --armor --export YOUR_KEY_ID

# In Uncode IDE terminal, import it:
curl -fsSL https://YOUR_GITHUB_USERNAME.github.io/YOUR_REPO_NAME/public.key | apt-key add -
```

---

## 🔄 How It Works

```
Push to main
    │
    ▼
GitHub Actions
    ├─ Validate all packages/*/DEBIAN/control
    ├─ Build .deb with dpkg-deb -Zxz
    ├─ Sign repo with GPG via termux-apt-repo
    ├─ Generate HTML index (scripts/gen_index.py)
    └─ Deploy repo/ → gh-pages branch
            │
            ▼
    GitHub Pages
    https://username.github.io/repo-name/
    dists/uncode-stable/main/...
```

---

## 📋 Control File Fields Reference

| Field | Required | Example |
|-------|----------|---------|
| `Package` | ✓ | `bash` |
| `Version` | ✓ | `5.2.21-1` |
| `Architecture` | ✓ | `aarch64` |
| `Maintainer` | ✓ | `Uncode IDE <packages@uncode.ide>` |
| `Description` | ✓ | `GNU Bourne Again SHell` |
| `Installed-Size` | recommended | `2048` (in KB) |
| `Depends` | optional | `libc (>= 2.17), libssl` |
| `Section` | optional | `utils`, `shells`, `editors` |
| `Priority` | optional | `required`, `optional` |
| `Homepage` | optional | `https://example.com` |

---

## 🛠️ Local Testing

```sh
# Build all packages locally
mkdir -p debs
for pkg_dir in packages/*/; do
  [ -f "${pkg_dir}/DEBIAN/control" ] || continue
  [ "$pkg_dir" = "packages/TEMPLATE/" ] && continue
  dpkg-deb -b -Zxz "$pkg_dir" debs/
done

ls -lh debs/
```
