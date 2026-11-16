import tempfile
import unittest
from pathlib import Path

from backend.settings import (
    DEFAULT_HOTKEY,
    DEFAULT_SETTINGS,
    hotkey_code,
    hotkey_description,
    hotkey_from_settings,
    load_settings,
    save_settings,
    validate_hotkey,
    validate_settings,
)


class SettingsTest(unittest.TestCase):
    def test_uses_default_when_file_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "configuracoes.json"
            self.assertEqual(hotkey_from_settings(load_settings(path)), DEFAULT_HOTKEY)
            self.assertEqual(load_settings(path), DEFAULT_SETTINGS)

    def test_saves_and_loads_hotkey(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "configuracoes.json"
            settings = {
                "ctrl": True,
                "alt": False,
                "shift": True,
                "tecla": "F4",
            }
            save_settings(path, {**DEFAULT_SETTINGS, **settings})

            self.assertEqual(hotkey_from_settings(load_settings(path)), settings)
            self.assertEqual(hotkey_code(settings), "<ctrl>+<shift>+<f4>")
            self.assertEqual(hotkey_description(settings), "Ctrl + Shift + F4")

    def test_rejects_hotkey_without_modifier(self) -> None:
        with self.assertRaisesRegex(ValueError, "HOTKEY_MODIFIER_REQUIRED"):
            validate_hotkey(
                {"ctrl": False, "alt": False, "shift": False, "tecla": "T"}
            )

    def test_saves_and_loads_light_theme(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "configuracoes.json"
            settings = {
                "ctrl": True,
                "alt": True,
                "shift": False,
                "tecla": "T",
                "tema": "light",
                "locale": "de",
            }

            save_settings(path, settings)

            self.assertEqual(load_settings(path), settings)

    def test_uses_dark_theme_when_legacy_file_has_no_theme(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "configuracoes.json"
            path.write_text(
                '{"atalho_popup":{"ctrl":true,"alt":true,"shift":false,"tecla":"T"}}',
                encoding="utf-8",
            )

            self.assertEqual(load_settings(path)["tema"], "dark")
            self.assertEqual(load_settings(path)["locale"], "en")

    def test_rejects_invalid_theme(self) -> None:
        with self.assertRaisesRegex(ValueError, "INVALID_THEME"):
            validate_settings(
                {
                    "ctrl": True,
                    "alt": True,
                    "shift": False,
                    "tecla": "T",
                    "tema": "automatic",
                }
            )

    def test_rejects_unsupported_locale(self) -> None:
        with self.assertRaisesRegex(ValueError, "INVALID_LOCALE"):
            validate_settings(
                {
                    "ctrl": True,
                    "alt": True,
                    "shift": False,
                    "tecla": "T",
                    "tema": "dark",
                    "locale": "fr",
                }
            )


if __name__ == "__main__":
    unittest.main()
