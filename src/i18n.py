# i18n.py
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

import importlib.util
import os

DEFAULT_LANG = "en"

# Locale codes that map to one of our packaged language files under a
# different name (e.g. most Norwegian systems report nb_NO or nn_NO, not
# no_NO).
LANG_ALIASES = {
    "nb": "no",
    "nn": "no",
}

_LANG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang")


def _available_languages():
    if not os.path.isdir(_LANG_DIR):
        return []
    return sorted(
        f[:-3] for f in os.listdir(_LANG_DIR)
        if f.endswith(".py") and not f.startswith("_")
    )


def _load_strings(lang_code):
    path = os.path.join(_LANG_DIR, f"{lang_code}.py")
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location(f"ami_lang_{lang_code}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "STRINGS", None)


def _detect_system_lang():
    """Auto-detect the wanted language from the environment.

    AMI_LANG (an explicit override) wins, then the normal POSIX locale
    variables in their usual precedence order. Returns None if the system
    exposes no language at all (e.g. everything unset).
    """
    for var in ("AMI_LANG", "LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        value = os.environ.get(var)
        if value and value.upper() != "C" and value.upper() != "POSIX":
            code = value.split(".")[0].split("_")[0].strip().lower()
            if code:
                return code
    return None


def _resolve_active_lang():
    requested = _detect_system_lang()
    if requested:
        code = LANG_ALIASES.get(requested, requested)
        if _load_strings(code) is not None:
            return code
    return DEFAULT_LANG


_lang_code = _resolve_active_lang()
_strings = _load_strings(_lang_code) or {}
_fallback_strings = _load_strings(DEFAULT_LANG) or {}


def t(key, **kwargs):
    """Return the translated string for the active language, falling back to
    English for any key a translation is missing."""
    template = _strings.get(key) or _fallback_strings.get(key, key)
    return template.format(**kwargs) if kwargs else template


def get_startup_notice():
    """Return a short, plain-language hint if the system's language isn't
    packaged yet (so ami is falling back to English), or None otherwise."""
    requested = _detect_system_lang()
    if not requested:
        return None
    code = LANG_ALIASES.get(requested, requested)
    if _load_strings(code) is not None:
        return None

    available = ", ".join(_available_languages()) or "none yet"
    return (
        f"(ami doesn't have a '{requested}' translation yet, so it's using English.\n"
        f" Packaged languages right now: {available}.\n"
        f" Adding your own is easy:\n"
        f"   1. Copy {_LANG_DIR}/en.py to {_LANG_DIR}/{requested}.py\n"
        f"   2. Translate only the text after each ':' below -- leave every dict key\n"
        f"      and {{word-in-curly-braces}} exactly as it is\n"
        f"   3. Save it -- ami will pick it up automatically next time you run it.)\n"
    )
