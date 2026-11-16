import tempfile
import unittest
from pathlib import Path

from backend.data_paths import migrate_legacy_data


class DataPathsTest(unittest.TestCase):
    def test_migrates_legacy_files_without_overwriting_existing_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "legacy"
            destination = root / "local" / "ToDoX"
            legacy.mkdir()
            destination.mkdir(parents=True)
            (legacy / "tarefas.json").write_text("legacy tasks", encoding="utf-8")
            (legacy / "configuracoes.json").write_text("legacy settings", encoding="utf-8")
            (destination / "tarefas.json").write_text("current tasks", encoding="utf-8")

            migrate_legacy_data(legacy, destination)

            self.assertEqual(
                (destination / "tarefas.json").read_text(encoding="utf-8"),
                "current tasks",
            )
            self.assertEqual(
                (destination / "configuracoes.json").read_text(encoding="utf-8"),
                "legacy settings",
            )


if __name__ == "__main__":
    unittest.main()
