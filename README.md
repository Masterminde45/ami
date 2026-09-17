# AMI — Archlinux Multi Installer

A single command that installs packages from **both** the official Pacman
repositories and the AUR, so you don't need a separate AUR helper (yay,
paru, ...) alongside Pacman.

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
`makepkg`) — see the AUR `PKGBUILD` for the full dependency list.

## Notes

Console output is currently in Norwegian.

## License

GPL-3.0-or-later — see `COPYING`.
