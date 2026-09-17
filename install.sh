#!/usr/bin/env bash
# install.sh -- universal installer for ami
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Masterminde45/ami/main/install.sh | bash
#
# For a reproducible, inspectable install, pin to a specific commit instead
# of the mutable main branch, e.g.:
#   curl -fsSL https://raw.githubusercontent.com/Masterminde45/ami/<commit-sha>/install.sh | bash
# or just download and read this script yourself before running it -- it's
# plain bash, nothing hidden.
#
# Picks the best available install method for this system, in order:
#   1. Homebrew/Linuxbrew, if `brew` is on PATH
#   2. Arch Linux (pacman present) -- direct meson build+install to /usr/local
#   3. Generic fallback -- build+install to $HOME/.local, no root needed
#
# Every source download in methods 2 and 3 is verified against that
# release's published SHA256SUMS.txt before anything is extracted or built.
# Verification failure aborts -- this script never installs something it
# couldn't verify.
#
# Set AMI_VERSION to pin a specific release tag (default: latest release).

set -euo pipefail

REPO="Masterminde45/ami"
AMI_VERSION="${AMI_VERSION:-}"

info()  { printf '==> %s\n' "$*"; }
error() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    else
        error "Need sha256sum or shasum to verify the download -- neither found."
    fi
}

resolve_version() {
    if [ -n "$AMI_VERSION" ]; then
        printf '%s' "$AMI_VERSION"
        return
    fi
    # Capture the full response before grep/sed touch it -- piping curl
    # straight into `grep -m1` lets grep close the pipe as soon as it finds
    # a match, which sends curl a SIGPIPE and makes it print a spurious
    # "Failure writing output" error even though the result is still correct.
    local api_response
    api_response="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest")"
    printf '%s' "$api_response" | grep -m1 '"tag_name"' | sed -E 's/.*"tag_name": *"([^"]+)".*/\1/'
}

# --- Method 1: Homebrew / Linuxbrew --------------------------------------
if command -v brew >/dev/null 2>&1; then
    info "Homebrew detected -- installing via the ami tap."
    brew tap Masterminde45/ami
    brew install ami
    info "Done. Run 'ami' to get started."
    exit 0
fi

# --- Methods 2 & 3: build from the versioned, checksum-verified tarball --
VERSION="$(resolve_version)"
[ -n "$VERSION" ] || error "Could not resolve a release version. Set AMI_VERSION explicitly (e.g. AMI_VERSION=v0.1.1)."
info "Installing ami ${VERSION} from source."

for dep in curl tar meson ninja python3; do
    command -v "$dep" >/dev/null 2>&1 || error "Missing required tool: $dep"
done

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
cd "$WORKDIR"

TARBALL="ami-${VERSION#v}.tar.gz"
TARBALL_URL="https://github.com/${REPO}/archive/refs/tags/${VERSION}.tar.gz"
SUMS_URL="https://github.com/${REPO}/releases/download/${VERSION}/SHA256SUMS.txt"

info "Downloading ${TARBALL_URL}"
curl -fsSL -o "$TARBALL" "$TARBALL_URL"

info "Downloading checksums and verifying"
if curl -fsSL -o SHA256SUMS.txt "$SUMS_URL"; then
    EXPECTED="$(grep "  ${TARBALL}\$" SHA256SUMS.txt | awk '{print $1}' || true)"
    if [ -z "$EXPECTED" ]; then
        error "No checksum entry for ${TARBALL} in ${VERSION}'s SHA256SUMS.txt -- refusing to install unverified."
    fi
    ACTUAL="$(sha256_of "$TARBALL")"
    [ "$EXPECTED" = "$ACTUAL" ] || error "Checksum mismatch for ${TARBALL}! Expected ${EXPECTED}, got ${ACTUAL}. Aborting -- do not trust this download."
    info "Checksum OK (${ACTUAL})"
else
    error "Could not fetch SHA256SUMS.txt for ${VERSION} -- refusing to install an unverified download. (Releases before v0.1.1 have no checksums file; try AMI_VERSION=v0.1.1 or newer.)"
fi

# GPG signature check on top of the checksum (defense in depth). The
# signing key's fingerprint is pinned right here, so even a tampered key
# file fetched over the wire would be caught before it's trusted.
SIGNING_KEY_FINGERPRINT="139BA2EBA0360987766010B697A1B834AD2AC40B"
if command -v gpg >/dev/null 2>&1; then
    SIG_URL="https://github.com/${REPO}/releases/download/${VERSION}/SHA256SUMS.txt.asc"
    KEY_URL="https://raw.githubusercontent.com/${REPO}/main/ami-signing-key.asc"
    if curl -fsSL -o SHA256SUMS.txt.asc "$SIG_URL" 2>/dev/null && curl -fsSL -o ami-signing-key.asc "$KEY_URL" 2>/dev/null; then
        mkdir -m 700 gnupghome
        FPR="$(GNUPGHOME="$PWD/gnupghome" gpg --batch --with-colons --import-options show-only --import ami-signing-key.asc 2>/dev/null | awk -F: '/^fpr:/ {print $10; exit}')"
        if [ "$FPR" != "$SIGNING_KEY_FINGERPRINT" ]; then
            error "Signing key fingerprint mismatch! Expected ${SIGNING_KEY_FINGERPRINT}, got '${FPR:-none}'. Aborting -- do not trust this download."
        fi
        GNUPGHOME="$PWD/gnupghome" gpg --batch --import ami-signing-key.asc >/dev/null 2>&1
        if GNUPGHOME="$PWD/gnupghome" gpg --batch --verify SHA256SUMS.txt.asc SHA256SUMS.txt >/dev/null 2>&1; then
            info "GPG signature OK (verified against pinned key ${SIGNING_KEY_FINGERPRINT})"
        else
            error "GPG signature verification FAILED -- do not trust this download."
        fi
    else
        info "No GPG signature published for ${VERSION} yet -- continuing on the SHA256 checksum alone."
    fi
else
    info "gpg not installed -- skipping signature verification, relying on the SHA256 checksum alone."
fi

tar xf "$TARBALL"
SRC_DIR="$(find . -maxdepth 1 -type d -name 'ami-*')"
cd "$SRC_DIR"

if command -v pacman >/dev/null 2>&1; then
    info "Arch Linux detected -- checking build dependencies via pacman."
    MISSING=""
    for pkg in python python-requests git; do
        pacman -Qi "$pkg" >/dev/null 2>&1 || MISSING="$MISSING $pkg"
    done
    if [ -n "$MISSING" ]; then
        info "Installing missing dependencies:${MISSING}"
        sudo pacman -S --needed --noconfirm $MISSING
    fi
    PREFIX="/usr/local"
    info "Building and installing to ${PREFIX} (needs sudo for the install step)."
    meson setup build --prefix="$PREFIX"
    meson compile -C build
    sudo meson install -C build
else
    info "No pacman or Homebrew found -- installing to \$HOME/.local (no root needed)."
    PREFIX="${HOME}/.local"
    VENV="${PREFIX}/share/ami-venv"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet requests
    export PATH="$VENV/bin:$PATH"
    meson setup build --prefix="$PREFIX"
    meson compile -C build
    meson install -C build
    info "Installed. Make sure ${PREFIX}/bin is on your PATH."
    info "NOTE: ami drives pacman, makepkg, and the AUR directly -- its"
    info "install/search/clean commands need those Arch Linux tools present"
    info "to actually do anything. This just gets the CLI itself installed."
fi

info "Done. Run 'ami' to get started."
