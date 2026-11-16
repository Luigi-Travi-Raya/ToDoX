from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, TypedDict

from .errors import AppError


class HotkeySettings(TypedDict):
    ctrl: bool
    alt: bool
    shift: bool
    tecla: str


Theme = Literal["dark", "light"]
Locale = Literal["en", "ja", "de", "pt-BR", "es"]


class AppSettings(HotkeySettings):
    tema: Theme
    locale: Locale


DEFAULT_HOTKEY: HotkeySettings = {
    "ctrl": True,
    "alt": True,
    "shift": False,
    "tecla": "T",
}
DEFAULT_THEME: Theme = "dark"
DEFAULT_LOCALE: Locale = "en"
DEFAULT_SETTINGS: AppSettings = {
    **DEFAULT_HOTKEY,
    "tema": DEFAULT_THEME,
    "locale": DEFAULT_LOCALE,
}
ALLOWED_KEYS = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + tuple(
    f"F{number}" for number in range(1, 13)
)


def validate_hotkey(value: Any) -> HotkeySettings:
    if not isinstance(value, dict):
        raise AppError("INVALID_HOTKEY")

    ctrl = value.get("ctrl")
    alt = value.get("alt")
    shift = value.get("shift")
    key = value.get("tecla")
    if not all(isinstance(item, bool) for item in (ctrl, alt, shift)):
        raise AppError("INVALID_HOTKEY_MODIFIERS")
    if not any((ctrl, alt, shift)):
        raise AppError("HOTKEY_MODIFIER_REQUIRED")
    if not isinstance(key, str) or key.upper() not in ALLOWED_KEYS:
        raise AppError("INVALID_HOTKEY_KEY")

    return {"ctrl": ctrl, "alt": alt, "shift": shift, "tecla": key.upper()}


def validate_theme(value: Any) -> Theme:
    if value not in ("dark", "light"):
        raise AppError("INVALID_THEME")
    return value


def validate_locale(value: Any) -> Locale:
    if value not in ("en", "ja", "de", "pt-BR", "es"):
        raise AppError("INVALID_LOCALE")
    return value


def hotkey_from_settings(settings: AppSettings) -> HotkeySettings:
    return {
        "ctrl": settings["ctrl"],
        "alt": settings["alt"],
        "shift": settings["shift"],
        "tecla": settings["tecla"],
    }


def validate_settings(value: Any) -> AppSettings:
    hotkey = validate_hotkey(value)
    theme = validate_theme(value.get("tema"))
    locale = validate_locale(value.get("locale"))
    return {**hotkey, "tema": theme, "locale": locale}


def load_settings(path: Path) -> AppSettings:
    if not path.exists():
        return DEFAULT_SETTINGS.copy()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AppError("INVALID_SETTINGS_FILE")
    hotkey = validate_hotkey(data.get("atalho_popup"))
    theme = validate_theme(data.get("tema", DEFAULT_THEME))
    locale = validate_locale(data.get("locale", DEFAULT_LOCALE))
    return {**hotkey, "tema": theme, "locale": locale}


def save_settings(path: Path, settings: AppSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    content = {
        "atalho_popup": hotkey_from_settings(settings),
        "tema": settings["tema"],
        "locale": settings["locale"],
    }
    try:
        temporary.write_text(
            json.dumps(content, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def hotkey_code(settings: HotkeySettings) -> str:
    parts: list[str] = []
    if settings["ctrl"]:
        parts.append("<ctrl>")
    if settings["alt"]:
        parts.append("<alt>")
    if settings["shift"]:
        parts.append("<shift>")
    key = settings["tecla"].lower()
    parts.append(key if len(key) == 1 else f"<{key}>")
    return "+".join(parts)


def hotkey_description(settings: HotkeySettings) -> str:
    parts: list[str] = []
    if settings["ctrl"]:
        parts.append("Ctrl")
    if settings["alt"]:
        parts.append("Alt")
    if settings["shift"]:
        parts.append("Shift")
    parts.append(settings["tecla"])
    return " + ".join(parts)
