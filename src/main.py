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

AUR_BASE_URL = "https://aur.archlinux.org/rpc/"
PACMAN_PATH = "/usr/bin/pacman"
PACCACHE_PATH = "/usr/bin/paccache"

# Nettverks-timeout (sekunder) for ALLE HTTP-kall mot AUR. Uten dette ville
# requests.get() henge i det uendelige hvis nettet/tunnelen er treg -> dette var
# årsaken til at AMI "hang etter synkronisering".
AUR_TIMEOUT = 15

# --- Patch-system (universelt) -------------------------------------------------
# AMI er en GENERELL installer. Noen pakker har kjente installasjonsproblemer i
# sin egen AUR-/byggprosess. Slike fikser legges inn her som "patcher" og kjøres
# KUN for den aktuelle pakken (aldri for andre). En patch er en funksjon som tar
# byggekatalogen som argument og kjøres ETTER kloning, FØR makepkg.

def _remove_conflicts(*packages):
    """Lager en patch som fjerner installerte konfliktpakker før bygging."""
    def _patch(build_dir):
        for pkg in packages:
            installed = subprocess.run(
                [PACMAN_PATH, "-Q", pkg],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            ).returncode == 0
            if installed:
                print(f"  [patch] Fjerner konfliktpakke: {pkg}")
                subprocess.run(["sudo", PACMAN_PATH, "-Rdd", "--noconfirm", pkg],
                               check=False)
    return _patch

# Register: pakkenavn -> liste av (beskrivelse, patch-funksjon).
# Legg nye kjente-problem-fikser her. De trigges bare for navnet de står under.
PATCHES = {
    # yay-git kolliderer med en eksisterende yay-installasjon.
    "yay-git": [
        ("Fjern yay/yay-debug-konflikt", _remove_conflicts("yay", "yay-debug")),
    ],
    # Kildebygd rustdesk: ny geocode-glib slår sammen geocode-glib-common,
    # makepkg stopper på "unresolvable package conflicts" med --noconfirm.
    "rustdesk": [
        ("Løs geocode-glib-common sammenslåingskonflikt",
         _remove_conflicts("geocode-glib-common")),
    ],
}

def apply_patches(pkgname, build_dir):
    """Kjør kun patchene som gjelder for denne pakken (om noen)."""
    patches = PATCHES.get(pkgname, [])
    if not patches:
        return
    print(f"Bruker {len(patches)} kjent(e) patch(er) for '{pkgname}'...")
    for desc, fn in patches:
        print(f"  -> {desc}")
        try:
            fn(build_dir)
        except Exception as e:
            print(f"  ADVARSEL: patch '{desc}' feilet: {e}")

# --- Hjelpefunksjoner ---

def search_pacman_repos(pkgname):
    """Sjekker om pakken finnes i offisielle Pacman-repositorier.

    Bruker '-Si' (ren spørring mot synk-databasen) i stedet for transaksjons-
    flagg som -Sp. Det starter ingen installasjon og kan ikke henge.
    """
    print(f"Sjekker offisielle repos for '{pkgname}'...")
    try:
        result = subprocess.run(
            [PACMAN_PATH, "-Si", pkgname],
            check=False, capture_output=True, text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        print(f"FATAL FEIL: '{PACMAN_PATH}' kommandoen ble ikke funnet i det hele tatt.")
        return False

def get_package_info(pkgname):
    """Henter detaljert info om en pakke fra AUR."""
    url = f"{AUR_BASE_URL}?v=5&type=info&arg[]={pkgname}"
    print(f"Slår opp '{pkgname}' i AUR...")
    try:
        response = requests.get(url, timeout=AUR_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if data.get('resultcount', 0) > 0:
            return data['results'][0]
        return None
    except requests.exceptions.Timeout:
        print(f"Tidsavbrudd ({AUR_TIMEOUT}s) ved henting av AUR-info. "
              "Sjekk nettverk/tunnel.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Nettverksfeil ved henting av AUR-info: {e}")
        return None

def clean_up_and_retry(pkgname, attempts=2):
    """Prøver installasjon på nytt uten å slette build-mappen.

    Git-repoet (og evt. lokale PKGBUILD-endringer) bevares. Bruker makepkg sin
    egen --cleanbuild for å fjerne et evt. korrupt delvis bygd srcdir, i stedet
    for å slette hele mappen (den forrige versjonen gjorde 'sudo rm -rf' på
    hvert forsøk, som forårsaket et reelt tap av bygg-fremdrift ved en tidligere
    OOM-hendelse).
    """
    for attempt in range(1, attempts + 1):
        print(f"\n--- Gjør nytt forsøk på installasjon ({attempt}/{attempts}) ---")
        try:
            install_aur_only(pkgname, clean_build=True)
            return True
        except subprocess.CalledProcessError:
            if attempt == attempts:
                print(f"Installasjonen feilet etter {attempts} forsøk. "
                      f"Build-mappen '{pkgname}' er beholdt (IKKE slettet) for feilsøking.")
                return False

    return False

def install_aur_only(pkgname, clean_build=False):
    """Utfører kun AUR-kloning og makepkg. Kaster feil hvis det feiler."""

    repo_url = f"https://aur.archlinux.org/{pkgname}.git"

    if not os.path.exists(pkgname):
        print(f"Kloner {repo_url}...")
        subprocess.run(["git", "clone", repo_url], check=True)
        print("Kloning fullført.")
    else:
        print(f"Mappen '{pkgname}' finnes. Oppdaterer fra Git...")
        subprocess.run(["git", "pull"], cwd=pkgname, check=True, stdout=subprocess.DEVNULL)

    # Kjør kun patcher som gjelder denne pakken (universelt patch-system).
    apply_patches(pkgname, pkgname)

    print(f"Starter bygging av {pkgname}...")
    makepkg_cmd = ["makepkg", "-si", "--noconfirm"]
    if clean_build:
        makepkg_cmd.append("--cleanbuild")
    subprocess.run(makepkg_cmd, cwd=pkgname, check=True)
    print(f"SUKSESS! '{pkgname}' er installert.")

# --- System Oppryddingsfunksjon ---

def clean_system():
    """Rydder opp i Pacman cache og fjerner foreldreløse pakker."""
    print("--- Starter Systemopprydding (AMI Clean) ---")

    # 1. RENSE LÅS
    lock_file = "/var/lib/pacman/db.lck"
    if os.path.exists(lock_file):
        print(f"Fant Pacman-låsefil: {lock_file}. Sletter...")
        try:
            subprocess.run(["sudo", "rm", "-f", lock_file], check=True)
            print("Låsefil slettet.")
        except subprocess.CalledProcessError:
            print("Advarsel: Klarte ikke å slette låsefilen.")

    # 2. Fjern foreldreløse pakker
    print("\n[1/2] Fjerner foreldreløse pakker...")
    try:
        orphans = subprocess.run([PACMAN_PATH, "-Qtdq"], capture_output=True, text=True, check=False)
        orphan_names = orphans.stdout.split()
        if orphan_names:
            print(f"Fant {len(orphan_names)} foreldreløse pakke(r). Fjerner...")
            subprocess.run(["sudo", PACMAN_PATH, "-Rns", "--noconfirm", *orphan_names],
                            check=True, capture_output=True, text=True)
            print("Fjerning av foreldreløse pakker fullført.")
        else:
            print("Ingen foreldreløse pakker funnet.")
    except subprocess.CalledProcessError as e:
        print(f"FEIL under fjerning av foreldreløse pakker: {e.stderr}")

    # 3. Rydde opp i Pacman Cache
    print("\n[2/2] Rydder opp i Pacman Cache (/var/cache/pacman/pkg)...")
    try:
        subprocess.run([PACCACHE_PATH, "-r"], check=True)
        print("Pacman Cache-opprydding fullført. Eldre pakker er slettet.")
    except FileNotFoundError:
        print(f"FEIL: '{PACCACHE_PATH}' ble ikke funnet. Dette verktøyet er del av 'pacman-contrib'.")
        print("Vennligst installer pakken manuelt: 'sudo pacman -S pacman-contrib'")
    except subprocess.CalledProcessError as e:
        print(f"FEIL under Cache-opprydding: {e}")

    print("\nOpprydding fullført!")

# --- Hovedfunksjon med Synkronisering ---

def install_package(pkgname):
    """Sjekker Pacman, deretter AUR, og installerer pakken."""

    # 1. RENSE LÅS
    lock_file = "/var/lib/pacman/db.lck"
    if os.path.exists(lock_file):
        print(f"Fant Pacman-låsefil: {lock_file}. Sletter...")
        try:
            subprocess.run(["sudo", "rm", "-f", lock_file], check=True)
            print("Låsefil slettet. Fortsetter.")
        except subprocess.CalledProcessError:
            print("Advarsel: Klarte ikke å slette låsefilen. Fortsetter.")

    # 2. SYNKRONISERING
    print("Synkroniserer Pacman-databasen...")
    try:
        subprocess.run(["sudo", PACMAN_PATH, "-Sy", "--noconfirm"], check=True, stdout=subprocess.DEVNULL)
        print("Synkronisering fullført.")
    except subprocess.CalledProcessError:
        print("Advarsel: Klarte ikke å synkronisere Pacman-databasen. Fortsetter med installasjon...")

    # Prioritet 1: Pacman
    if search_pacman_repos(pkgname):
        print(f"Fant '{pkgname}' i offisielle Pacman-repositorier. Installerer via Pacman...")
        try:
            subprocess.run(["sudo", PACMAN_PATH, "-S", "--noconfirm", pkgname], check=True)
            print(f"SUKSESS! '{pkgname}' er installert via Pacman.")
            return
        except subprocess.CalledProcessError as e:
            print(f"FEIL under Pacman-installasjon. Sjekk om systemet er oppdatert. {e}")
            return

    # Prioritet 2: AUR
    info = get_package_info(pkgname)

    if not info:
        print(f"Feil: Finner verken Pacman- eller AUR-informasjon for '{pkgname}'. Avbryter.")
        return

    print(f"Fant '{pkgname}' i AUR. Starter bygging fra kildekode...")

    # Første forsøk på AUR-installasjon
    try:
        install_aur_only(pkgname)
    except subprocess.CalledProcessError:
        clean_up_and_retry(pkgname)


def main(argv):
    """Entrypoint kalt av 'ami'-wrapperen (src/ami.in) etter installasjon."""
    if len(argv) > 1:
        command = argv[1]

        if command == 'clean':
            clean_system()
        elif command == 'install':
            if len(argv) > 2:
                pkg_to_install = argv[2]
                install_package(pkg_to_install)
            else:
                print("FEIL: Mangler pakkenavn. Bruk: ami install <pakkenavn>")
        else:
            pkg_to_install = command
            install_package(pkg_to_install)
    else:
        print("--- AMI (Archlinux Multi Installer) ---")
        print("Bruk: ami <pakkenavn> (for å installere)")
        print("Bruk: ami clean (for å rydde opp systemet)")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
