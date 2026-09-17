# AMI — Archlinux Multi Installer

A single command that installs packages from **both** the official Pacman
repositories and the AUR, so you don't need a separate AUR helper (yay,
paru, ...) alongside Pacman.

## Install

**Homebrew / Linuxbrew:**

```
brew tap Masterminde45/ami
brew install ami
```

**Universal installer** (auto-picks Homebrew if present, otherwise builds
directly on Arch, otherwise builds to `$HOME/.local` on any Linux/Unix
system with `meson`/`ninja`/`python3`):

```
curl -fsSL https://raw.githubusercontent.com/Masterminde45/ami/main/install.sh | bash
```

Read `install.sh` before piping it to `bash` if you'd rather not trust a
one-liner blindly — it's plain, short, commented bash. It verifies every
source download's SHA256 checksum (and GPG signature, if `gpg` is
installed) against the release before building or installing anything, and
refuses to proceed on a mismatch.

**AUR:** `PKGBUILD`/`.SRCINFO` exist and are kept current, but AUR account
registration has been closed since mid-2026 due to a wave of automated
account creation — the package isn't published there yet. Once it's up,
it'll be installable the normal way (`yay -S ami`, `paru -S ami`, or a
manual `git clone`+`makepkg -si` from the AUR).

## Verifying a download

Every release from v0.1.1 onward publishes a `SHA256SUMS.txt` and a
detached GPG signature `SHA256SUMS.txt.asc` alongside the source tarball.

```
curl -fsSLO https://github.com/Masterminde45/ami/archive/refs/tags/v0.1.1.tar.gz
curl -fsSLO https://github.com/Masterminde45/ami/releases/download/v0.1.1/SHA256SUMS.txt
sha256sum -c SHA256SUMS.txt
```

To also verify the signature (proves the checksums file itself came from
the actual maintainer, not just that the tarball matches *some* checksums
file):

```
curl -fsSL https://raw.githubusercontent.com/Masterminde45/ami/main/ami-signing-key.asc | gpg --import
curl -fsSLO https://github.com/Masterminde45/ami/releases/download/v0.1.1/SHA256SUMS.txt.asc
gpg --verify SHA256SUMS.txt.asc SHA256SUMS.txt
```

Signing key fingerprint (check this matches what `gpg` reports after
importing, don't just trust the import blindly):

```
139B A2EB A036 0987 7660  10B6 97A1 B834 AD2A C40B
```

## Usage

```
ami <package>            # install a package (repo first, falls back to AUR)
ami install <package>    # same as above
ami clean                # remove orphaned packages and clear the Pacman cache
```

When a package isn't in the official repos, `ami` looks it up on the AUR,
clones its build files, and runs `makepkg -si` for you. A small built-in
per-package patch registry works around known build issues in specific AUR
packages (e.g. dependency conflicts) without affecting any other package.

## Requirements

`python`, `python-requests`, `git`, `pacman`, and `base-devel` (for
`makepkg`) — see the AUR `PKGBUILD` for the full dependency list. `ami`
itself only drives `pacman`/`makepkg`/the AUR, so it only does anything
useful on a system that actually has those (Arch Linux or an Arch-based
distro) — installing it via Homebrew or `install.sh` on a non-Arch system
gets you the CLI, not pacman/AUR support.

## Language

`ami` auto-detects your system language (`LC_ALL`/`LC_MESSAGES`/`LANG`, or
set `AMI_LANG` to override) and falls back to English if nothing is set or
your language isn't packaged yet. Currently packaged: English, Norwegian.

Don't see your language? Adding one takes a couple of minutes:

1. Copy `src/lang/en.py` to `src/lang/<your-2-letter-code>.py`
2. Translate only the text after each `:` — leave every key and
   `{placeholder}` exactly as it is
3. Open a PR, or drop the file into the installed `lang/` folder yourself
   (`ami` loads language files from disk at runtime, so no rebuild needed
   for a local copy)

## License

GPL-3.0-or-later — see `COPYING`.
