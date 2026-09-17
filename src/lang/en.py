# en.py -- English strings for ami (the reference / fallback language)
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# To add a new language: copy this file to <your-2-letter-code>.py in this
# same folder (e.g. de.py for German, fr.py for French), translate only the
# text after each ':' below, and leave every dict key and {placeholder}
# exactly as it is. Save it here and ami will pick it up automatically the
# next time it runs -- no rebuild needed.

STRINGS = {
    "clean_start": "--- Starting system cleanup (AMI Clean) ---",
    "lockfile_found": "Found Pacman lock file: {path}. Removing...",
    "lockfile_removed": "Lock file removed.",
    "lockfile_removed_continue": "Lock file removed. Continuing.",
    "lockfile_remove_failed": "Warning: could not remove the lock file.",
    "lockfile_remove_failed_continue": "Warning: could not remove the lock file. Continuing.",
    "orphans_step": "\n[1/2] Removing orphan packages...",
    "orphans_found": "Found {count} orphan package(s). Removing...",
    "orphans_removed": "Orphan package removal complete.",
    "orphans_none": "No orphan packages found.",
    "orphans_error": "ERROR while removing orphan packages: {error}",
    "cache_step": "\n[2/2] Cleaning up the Pacman cache (/var/cache/pacman/pkg)...",
    "cache_done": "Pacman cache cleanup complete. Older packages removed.",
    "paccache_missing": "ERROR: '{path}' was not found. This tool is part of 'pacman-contrib'.",
    "paccache_missing_hint": "Please install the package manually: 'sudo pacman -S pacman-contrib'",
    "cache_error": "ERROR during cache cleanup: {error}",
    "clean_done": "\nCleanup complete!",
    "sync_start": "Syncing the Pacman database...",
    "sync_done": "Sync complete.",
    "sync_failed": "Warning: could not sync the Pacman database. Continuing with install...",
    "pacman_search": "Checking official repos for '{pkg}'...",
    "pacman_missing": "FATAL ERROR: the '{path}' command was not found at all.",
    "pacman_found_installing": "Found '{pkg}' in the official Pacman repos. Installing via Pacman...",
    "pacman_success": "SUCCESS! '{pkg}' installed via Pacman.",
    "pacman_install_failed": "ERROR during Pacman install. Check if the system is up to date. {error}",
    "aur_lookup": "Looking up '{pkg}' on the AUR...",
    "aur_timeout": "Timed out ({timeout}s) fetching AUR info. Check network/tunnel.",
    "aur_network_error": "Network error fetching AUR info: {error}",
    "not_found_anywhere": "Error: found neither Pacman nor AUR info for '{pkg}'. Aborting.",
    "aur_found_building": "Found '{pkg}' on the AUR. Building from source...",
    "retry_attempt": "\n--- Retrying install ({attempt}/{attempts}) ---",
    "retry_failed_final": "Install failed after {attempts} attempt(s). Build dir '{pkg}' kept (NOT deleted) for troubleshooting.",
    "clone_start": "Cloning {url}...",
    "clone_done": "Clone complete.",
    "dir_exists_updating": "Directory '{pkg}' exists. Updating from Git...",
    "patch_applying": "Applying {count} known patch(es) for '{pkg}'...",
    "patch_warning": "  WARNING: patch '{desc}' failed: {error}",
    "conflict_removing": "  [patch] Removing conflicting package: {pkg}",
    "build_start": "Starting build of {pkg}...",
    "build_success": "SUCCESS! '{pkg}' installed.",
    "banner_title": "--- AMI (Archlinux Multi Installer) ---",
    "banner_usage_install": "Usage: ami <package name> (to install)",
    "banner_usage_clean": "Usage: ami clean (to clean up the system)",
    "missing_pkgname": "ERROR: missing package name. Usage: ami install <package name>",
    "patch_yay_conflict": "Remove yay/yay-debug conflict",
    "patch_rustdesk_conflict": "Resolve geocode-glib-common merge conflict",
    "pkgbuild_changed_header": "\nThe PKGBUILD for '{pkg}' has changed since your last build -- review before continuing:",
    "pkgbuild_changed_prompt": "Build this updated PKGBUILD? [y/N] ",
    "pkgbuild_changed_auto_confirmed": "PKGBUILD for '{pkg}' changed -- auto-confirmed (AMI_AUTO_CONFIRM_PKGBUILD_CHANGES=1).",
    "pkgbuild_review_aborted": "Aborted: '{pkg}' was not built because the PKGBUILD change wasn't confirmed.",
    "build_logged": "Build recorded in {path}",
}
