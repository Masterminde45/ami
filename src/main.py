# main.py
#
# Copyright 2025 Mats
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later
import sys
import requests
import json
import subprocess
import os
import difflib
import hashlib
from datetime import datetime, timezone

try:
    from . import i18n
except ImportError:
    import i18n

t = i18n.t

AUR_BASE_URL = "https://aur.archlinux.org/rpc/"
PACMAN_PATH = "/usr/bin/pacman"
PACCACHE_PATH = "/usr/bin/paccache"

# Network timeout (seconds) for ALL HTTP calls to the AUR. Without this,
# requests.get() would hang forever if the network/tunnel is slow -- this was
# the cause of AMI "hanging after sync".
AUR_TIMEOUT = 15


class PkgbuildReviewDeclined(Exception):
    """Raised when the user declines to build a package whose PKGBUILD changed."""


# --- Patch system (universal) ---------------------------------------------
# AMI is a GENERAL installer. Some packages have known install problems in
# their own AUR/build process. Such fixes go here as "patches" and only run
# for that specific package (never for others). A patch is a function that
# takes the build directory as an argument and runs AFTER cloning, BEFORE
# makepkg.

def _remove_conflicts(*packages):
    """Builds a patch that removes installed conflicting packages before building."""
    def _patch(build_dir):
        for pkg in packages:
            installed = subprocess.run(
                [PACMAN_PATH, "-Q", pkg],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            ).returncode == 0
            if installed:
                print(t("conflict_removing", pkg=pkg))
                subprocess.run(["sudo", PACMAN_PATH, "-Rdd", "--noconfirm", pkg],
                               check=False)
    return _patch

# Registry: package name -> list of (description key, patch function).
# Add new known-issue fixes here. They only trigger for the name they're under.
PATCHES = {
    # yay-git conflicts with an existing yay install.
    "yay-git": [
        ("patch_yay_conflict", _remove_conflicts("yay", "yay-debug")),
    ],
    # Source-built rustdesk: a newer geocode-glib merges geocode-glib-common,
    # makepkg stops on "unresolvable package conflicts" with --noconfirm.
    "rustdesk": [
        ("patch_rustdesk_conflict", _remove_conflicts("geocode-glib-common")),
    ],
}

def apply_patches(pkgname, build_dir):
    """Runs only the patches that apply to this package (if any)."""
    patches = PATCHES.get(pkgname, [])
    if not patches:
        return
    print(t("patch_applying", count=len(patches), pkg=pkgname))
    for desc_key, fn in patches:
        print(f"  -> {t(desc_key)}")
        try:
            fn(build_dir)
        except Exception as e:
            print(t("patch_warning", desc=t(desc_key), error=e))

# --- Helper functions ---

def search_pacman_repos(pkgname):
    """Checks if the package exists in the official Pacman repos.

    Uses '-Si' (a plain query against the sync database) instead of a
    transaction flag like -Sp. It starts no install and cannot hang.
    """
    print(t("pacman_search", pkg=pkgname))
    try:
        result = subprocess.run(
            [PACMAN_PATH, "-Si", pkgname],
            check=False, capture_output=True, text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        print(t("pacman_missing", path=PACMAN_PATH))
        return False

def get_package_info(pkgname):
    """Fetches detailed info about a package from the AUR."""
    url = f"{AUR_BASE_URL}?v=5&type=info&arg[]={pkgname}"
    print(t("aur_lookup", pkg=pkgname))
    try:
        response = requests.get(url, timeout=AUR_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if data.get('resultcount', 0) > 0:
            return data['results'][0]
        return None
    except requests.exceptions.Timeout:
        print(t("aur_timeout", timeout=AUR_TIMEOUT))
        return None
    except requests.exceptions.RequestException as e:
        print(t("aur_network_error", error=e))
        return None

def _pkgbuild_diff_confirmed(pkgname, old_content, new_content):
    """Shows a PKGBUILD diff and asks for confirmation before building it.

    Returns True if it's OK to proceed. Real AUR compromises have shipped as
    ordinary-looking PKGBUILD edits (a maintainer account taken over, or a
    malicious co-maintainer), so a changed PKGBUILD on an existing clone is
    exactly the moment blind --noconfirm auto-building is riskiest. Set
    AMI_AUTO_CONFIRM_PKGBUILD_CHANGES=1 to skip this prompt deliberately.
    """
    if old_content == new_content:
        return True
    if os.environ.get("AMI_AUTO_CONFIRM_PKGBUILD_CHANGES") == "1":
        print(t("pkgbuild_changed_auto_confirmed", pkg=pkgname))
        return True
    print(t("pkgbuild_changed_header", pkg=pkgname))
    diff = difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile="PKGBUILD (previous)",
        tofile="PKGBUILD (new)",
    )
    sys.stdout.writelines(diff)
    answer = input(t("pkgbuild_changed_prompt")).strip().lower()
    return answer in ("y", "yes")

def _log_build_checksums(pkgname, build_dir):
    """Appends the sha256 of each package file this build produced to a
    local audit log, so there's a durable record of exactly what was
    installed and when -- useful after the fact even though there's no
    external authority to compare an arbitrary AUR package's hash against
    up front."""
    try:
        built_files = [f for f in os.listdir(build_dir)
                       if f.endswith((".pkg.tar.zst", ".pkg.tar.xz"))]
        if not built_files:
            return
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=build_dir,
            capture_output=True, text=True, check=False
        ).stdout.strip() or "unknown"
        log_dir = os.path.expanduser("~/.local/state/ami")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "build-log.txt")
        with open(log_path, "a") as log:
            for fname in built_files:
                fpath = os.path.join(build_dir, fname)
                with open(fpath, "rb") as f:
                    digest = hashlib.sha256(f.read()).hexdigest()
                timestamp = datetime.now(timezone.utc).isoformat()
                log.write(f"{timestamp}  pkg={pkgname}  commit={commit}  "
                          f"file={fname}  sha256={digest}\n")
        print(t("build_logged", path=log_path))
    except OSError:
        pass

def clean_up_and_retry(pkgname, attempts=2):
    """Retries the install without deleting the build directory.

    The git repo (and any local PKGBUILD edits) are preserved. Uses
    makepkg's own --cleanbuild to clear a corrupted/partial srcdir, instead
    of deleting the whole directory (the previous version did 'sudo rm -rf'
    on every attempt, which caused a real loss of build progress during a
    past OOM incident).
    """
    for attempt in range(1, attempts + 1):
        print(t("retry_attempt", attempt=attempt, attempts=attempts))
        try:
            install_aur_only(pkgname, clean_build=True)
            return True
        except PkgbuildReviewDeclined:
            print(t("pkgbuild_review_aborted", pkg=pkgname))
            return False
        except subprocess.CalledProcessError:
            if attempt == attempts:
                print(t("retry_failed_final", attempts=attempts, pkg=pkgname))
                return False

    return False

def install_aur_only(pkgname, clean_build=False):
    """Performs only the AUR clone and makepkg. Raises if it fails, or if
    the user declines to build a PKGBUILD that changed since last time."""

    repo_url = f"https://aur.archlinux.org/{pkgname}.git"
    pkgbuild_path = os.path.join(pkgname, "PKGBUILD")

    if not os.path.exists(pkgname):
        print(t("clone_start", url=repo_url))
        subprocess.run(["git", "clone", repo_url], check=True)
        print(t("clone_done"))
    else:
        print(t("dir_exists_updating", pkg=pkgname))
        old_pkgbuild = ""
        if os.path.exists(pkgbuild_path):
            with open(pkgbuild_path, "r", errors="replace") as f:
                old_pkgbuild = f.read()
        subprocess.run(["git", "pull"], cwd=pkgname, check=True, stdout=subprocess.DEVNULL)
        new_pkgbuild = ""
        if os.path.exists(pkgbuild_path):
            with open(pkgbuild_path, "r", errors="replace") as f:
                new_pkgbuild = f.read()
        if not _pkgbuild_diff_confirmed(pkgname, old_pkgbuild, new_pkgbuild):
            raise PkgbuildReviewDeclined(pkgname)

    # Only run the patches that apply to this package (universal patch system).
    apply_patches(pkgname, pkgname)

    print(t("build_start", pkg=pkgname))
    makepkg_cmd = ["makepkg", "-si", "--noconfirm"]
    if clean_build:
        makepkg_cmd.append("--cleanbuild")
    subprocess.run(makepkg_cmd, cwd=pkgname, check=True)
    print(t("build_success", pkg=pkgname))
    _log_build_checksums(pkgname, pkgname)

# --- System cleanup function ---

def clean_system():
    """Cleans up the Pacman cache and removes orphan packages."""
    print(t("clean_start"))

    # 1. CLEAR LOCK
    lock_file = "/var/lib/pacman/db.lck"
    if os.path.exists(lock_file):
        print(t("lockfile_found", path=lock_file))
        try:
            subprocess.run(["sudo", "rm", "-f", lock_file], check=True)
            print(t("lockfile_removed"))
        except subprocess.CalledProcessError:
            print(t("lockfile_remove_failed"))

    # 2. Remove orphan packages
    print(t("orphans_step"))
    try:
        orphans = subprocess.run([PACMAN_PATH, "-Qtdq"], capture_output=True, text=True, check=False)
        orphan_names = orphans.stdout.split()
        if orphan_names:
            print(t("orphans_found", count=len(orphan_names)))
            subprocess.run(["sudo", PACMAN_PATH, "-Rns", "--noconfirm", *orphan_names],
                            check=True, capture_output=True, text=True)
            print(t("orphans_removed"))
        else:
            print(t("orphans_none"))
    except subprocess.CalledProcessError as e:
        print(t("orphans_error", error=e.stderr))

    # 3. Clean up the Pacman cache
    print(t("cache_step"))
    try:
        subprocess.run([PACCACHE_PATH, "-r"], check=True)
        print(t("cache_done"))
    except FileNotFoundError:
        print(t("paccache_missing", path=PACCACHE_PATH))
        print(t("paccache_missing_hint"))
    except subprocess.CalledProcessError as e:
        print(t("cache_error", error=e))

    print(t("clean_done"))

# --- Main function with sync ---

def install_package(pkgname):
    """Checks Pacman, then the AUR, and installs the package."""

    # 1. CLEAR LOCK
    lock_file = "/var/lib/pacman/db.lck"
    if os.path.exists(lock_file):
        print(t("lockfile_found", path=lock_file))
        try:
            subprocess.run(["sudo", "rm", "-f", lock_file], check=True)
            print(t("lockfile_removed_continue"))
        except subprocess.CalledProcessError:
            print(t("lockfile_remove_failed_continue"))

    # 2. SYNC
    print(t("sync_start"))
    try:
        subprocess.run(["sudo", PACMAN_PATH, "-Sy", "--noconfirm"], check=True, stdout=subprocess.DEVNULL)
        print(t("sync_done"))
    except subprocess.CalledProcessError:
        print(t("sync_failed"))

    # Priority 1: Pacman (pacman itself verifies package signatures via its
    # own SigLevel config -- nothing extra to do here).
    if search_pacman_repos(pkgname):
        print(t("pacman_found_installing", pkg=pkgname))
        try:
            subprocess.run(["sudo", PACMAN_PATH, "-S", "--noconfirm", pkgname], check=True)
            print(t("pacman_success", pkg=pkgname))
            return
        except subprocess.CalledProcessError as e:
            print(t("pacman_install_failed", error=e))
            return

    # Priority 2: AUR
    info = get_package_info(pkgname)

    if not info:
        print(t("not_found_anywhere", pkg=pkgname))
        return

    print(t("aur_found_building", pkg=pkgname))

    # First AUR install attempt
    try:
        install_aur_only(pkgname)
    except PkgbuildReviewDeclined:
        print(t("pkgbuild_review_aborted", pkg=pkgname))
    except subprocess.CalledProcessError:
        clean_up_and_retry(pkgname)


def main(argv):
    """Entrypoint called by the 'ami' wrapper (src/ami.in) after install."""
    notice = i18n.get_startup_notice()
    if notice:
        print(notice)

    if len(argv) > 1:
        command = argv[1]

        if command == 'clean':
            clean_system()
        elif command == 'install':
            if len(argv) > 2:
                pkg_to_install = argv[2]
                install_package(pkg_to_install)
            else:
                print(t("missing_pkgname"))
        else:
            pkg_to_install = command
            install_package(pkg_to_install)
    else:
        print(t("banner_title"))
        print(t("banner_usage_install"))
        print(t("banner_usage_clean"))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
