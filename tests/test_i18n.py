import json
import re
import tempfile
import unittest
from pathlib import Path

from backend.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIRECTORY = ROOT / "frontend" / "src" / "i18n" / "locales"
LOCALE_FILES = ("en.json", "ja.json", "de.json", "pt-BR.json", "es.json")
PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z0-9_]+)\}")


def flatten_messages(value: object, prefix: str = "") -> dict[str, str]:
    if not isinstance(value, dict):
        raise AssertionError(f"Expected a message object at {prefix or '<root>'}")

    flattened: dict[str, str] = {}
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(child, dict):
            flattened.update(flatten_messages(child, path))
        elif isinstance(child, str):
            flattened[path] = child
        else:
            raise AssertionError(f"Message {path} must be a string")
    return flattened


class InternationalizationTest(unittest.TestCase):
    def load_catalog(self, filename: str) -> dict[str, str]:
        data = json.loads(
            (LOCALES_DIRECTORY / filename).read_text(encoding="utf-8")
        )
        return flatten_messages(data)

    def test_all_catalogs_have_the_same_keys_and_placeholders(self) -> None:
        english = self.load_catalog("en.json")
        for filename in LOCALE_FILES[1:]:
            with self.subTest(locale=filename):
                catalog = self.load_catalog(filename)
                self.assertEqual(set(catalog), set(english))
                for key, english_message in english.items():
                    self.assertEqual(
                        set(PLACEHOLDER_PATTERN.findall(catalog[key])),
                        set(PLACEHOLDER_PATTERN.findall(english_message)),
                        key,
                    )

    def test_legacy_priority_labels_are_migrated_to_stable_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "nome": "Legacy",
                            "prioridade": "Urgente",
                            "deletedAt": None,
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            tasks = load_tasks(path)
            persisted = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(tasks[0]["prioridade"], "urgent")
            self.assertEqual(persisted[0]["prioridade"], "urgent")


if __name__ == "__main__":
    unittest.main()

