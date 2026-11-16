import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.tasks import (
    complete_task,
    create_task,
    delete_task,
    load_completed_tasks,
    load_task_state,
    load_tasks,
    reorder_tasks,
    toggle_task_timer,
    update_task_name,
    update_task_tags,
    update_task_priority,
)


class LoadTasksTest(unittest.TestCase):
    def test_writes_compact_json_without_losing_unicode_or_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            tasks = create_task(path, "Revisão 日本語 #trabalho", "medium")

            content = path.read_text(encoding="utf-8")

            self.assertEqual(json.loads(content), tasks)
            self.assertEqual(len(content.splitlines()), 1)
            self.assertTrue(content.endswith("\n"))
            self.assertIn("Revisão 日本語", content)

    def test_combined_state_shares_active_and_history_ordering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            completed_id = create_task(path, "Completed", "low")[0]["id"]
            complete_task(path, completed_id)
            create_task(path, "Later priority", "low")
            create_task(path, "Earlier priority", "urgent")

            state = load_task_state(path)

            self.assertEqual(state["tasks"], load_tasks(path))
            self.assertEqual(state["completed_tasks"], load_completed_tasks(path))
            self.assertEqual(
                [task["nome"] for task in state["tasks"]],
                ["Earlier priority", "Later priority"],
            )
            self.assertEqual(state["completed_tasks"][0]["id"], completed_id)

    def test_adds_ids_and_returns_only_active_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            path.write_text(
                json.dumps(
                    [
                        {"nome": "Ativa", "prioridade": "Alta", "deletedAt": None},
                        {
                            "nome": "Excluída",
                            "prioridade": "Baixa",
                            "deletedAt": "2026-01-01T00:00:00+00:00",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            active_tasks = load_tasks(path)
            saved_tasks = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual([task["nome"] for task in active_tasks], ["Ativa"])
            self.assertTrue(all(task.get("id") for task in saved_tasks))

    def test_sorts_by_priority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            path.write_text(
                json.dumps(
                    [
                        {"id": "1", "nome": "Baixa", "prioridade": "Baixa", "deletedAt": None},
                        {"id": "2", "nome": "Urgente", "prioridade": "Urgente", "deletedAt": None},
                    ]
                ),
                encoding="utf-8",
            )

            tasks = load_tasks(path)

            self.assertEqual([task["nome"] for task in tasks], ["Urgente", "Baixa"])

    def test_migrates_existing_tasks_preserving_their_chronological_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "id": "later",
                            "nome": "Mais tarde",
                            "prioridade": "Alta",
                            "adicionada_em": "2026-08-04T11:00:00-03:00",
                        },
                        {
                            "id": "earlier",
                            "nome": "Mais cedo",
                            "prioridade": "Alta",
                            "adicionada_em": "2026-08-04T09:00:00-03:00",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            tasks = load_tasks(path)
            saved = {
                task["id"]: task
                for task in json.loads(path.read_text(encoding="utf-8"))
            }

            self.assertEqual([task["id"] for task in tasks], ["earlier", "later"])
            self.assertEqual(saved["earlier"]["ordem"], 0)
            self.assertEqual(saved["later"]["ordem"], 1)

    def test_creates_task_with_tags_and_complete_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"

            tasks = create_task(path, "Comprar leite #mercado #Mercado", "high")

            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["nome"], "Comprar leite")
            self.assertEqual(tasks[0]["tags"], ["mercado"])
            self.assertEqual(tasks[0]["prioridade"], "high")
            self.assertIsNone(tasks[0]["deletedAt"])
            self.assertIsNone(tasks[0]["completedAt"])
            self.assertFalse(tasks[0]["atividade_iniciada"])
            self.assertTrue(tasks[0]["id"])
            self.assertRegex(
                tasks[0]["cores_tags"]["mercado"],
                r"^#[0-9A-F]{6}$",
            )

    @patch("backend.tasks._random_tag_color", return_value="#A1B2C3")
    def test_assigns_random_tag_color_once_and_persists_it(
        self, random_tag_color
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"

            created = create_task(path, "Tarefa #aleatoria", "medium")[0]
            reloaded = load_tasks(path)[0]
            saved = json.loads(path.read_text(encoding="utf-8"))[0]

            self.assertEqual(created["cores_tags"]["aleatoria"], "#A1B2C3")
            self.assertEqual(reloaded["cores_tags"]["aleatoria"], "#A1B2C3")
            self.assertEqual(saved["cores_tags"]["aleatoria"], "#A1B2C3")
            random_tag_color.assert_called_once_with()

    @patch("backend.tasks._random_tag_color", return_value="#2468AC")
    def test_reuses_known_tag_color_without_new_random_draw(
        self, random_tag_color
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"

            create_task(path, "Primeira #Compartilhada", "medium")
            tasks = create_task(path, "Segunda #compartilhada", "medium")

            colors = {
                task["cores_tags"]["compartilhada"]
                for task in tasks
                if "compartilhada" in task["tags"]
            }
            self.assertEqual(colors, {"#2468AC"})
            random_tag_color.assert_called_once_with()

    def test_rejects_invalid_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"

            with self.assertRaisesRegex(ValueError, "TASK_NAME_REQUIRED"):
                create_task(path, "#somente-tag", "medium")
            with self.assertRaisesRegex(ValueError, "INVALID_PRIORITY"):
                create_task(path, "Tarefa", "Desconhecida")

    def test_updates_completes_and_deletes_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            first = create_task(path, "Primeira", "low")[0]

            updated = update_task_priority(path, first["id"], "urgent")
            self.assertEqual(updated[0]["prioridade"], "urgent")
            self.assertEqual(complete_task(path, first["id"]), [])
            self.assertEqual(
                [task["id"] for task in load_completed_tasks(path)],
                [first["id"]],
            )

            second = create_task(path, "Segunda", "medium")[0]
            self.assertEqual(delete_task(path, second["id"]), [])

            saved = json.loads(path.read_text(encoding="utf-8"))
            completed = next(task for task in saved if task["id"] == first["id"])
            deleted = next(task for task in saved if task["id"] == second["id"])
            self.assertEqual(completed["completedAt"], completed["deletedAt"])
            self.assertIsNone(deleted["completedAt"])
            self.assertIsNotNone(deleted["deletedAt"])

    def test_updates_task_name_and_validates_editing_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            task = create_task(path, "Nome antigo #existente", "medium")[0]

            updated = update_task_name(path, task["id"], "  Nome atualizado  ")[0]

            self.assertEqual(updated["nome"], "Nome atualizado")
            self.assertEqual(updated["tags"], ["existente"])
            self.assertEqual(updated["prioridade"], "medium")

            invalid_names = ("   ", "x" * 121, "Nome com #tag")
            for invalid_name in invalid_names:
                with self.subTest(invalid_name=invalid_name):
                    with self.assertRaises(ValueError):
                        update_task_name(path, task["id"], invalid_name)

            complete_task(path, task["id"])
            with self.assertRaisesRegex(ValueError, "COMPLETED_TASK_READ_ONLY"):
                update_task_name(path, task["id"], "Outro nome")

    def test_reorders_and_persists_tasks_of_the_same_priority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            create_task(path, "Primeira", "medium")
            create_task(path, "Segunda", "medium")
            create_task(path, "Terceira", "medium")
            create_task(path, "Outra prioridade", "low")
            by_name = {task["nome"]: task for task in load_tasks(path)}

            reordered = reorder_tasks(
                path,
                [
                    by_name["Terceira"]["id"],
                    by_name["Primeira"]["id"],
                    by_name["Segunda"]["id"],
                ],
            )

            self.assertEqual(
                [task["nome"] for task in reordered],
                ["Terceira", "Primeira", "Segunda", "Outra prioridade"],
            )
            self.assertEqual(
                [task["nome"] for task in load_tasks(path)],
                ["Terceira", "Primeira", "Segunda", "Outra prioridade"],
            )

    def test_rejects_reordering_tasks_from_different_priorities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            medium = create_task(path, "Média", "medium")[0]
            low = next(
                task
                for task in create_task(path, "Baixa", "low")
                if task["nome"] == "Baixa"
            )
            original = path.read_text(encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "REORDER_SAME_PRIORITY_ONLY"):
                reorder_tasks(path, [medium["id"], low["id"]])

            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_rejects_an_incomplete_priority_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            first = create_task(path, "Primeira", "medium")[0]
            create_task(path, "Segunda", "medium")

            with self.assertRaisesRegex(
                ValueError, "REORDER_ALL_PRIORITY_TASKS_REQUIRED"
            ):
                reorder_tasks(path, [first["id"]])

    def test_changing_priority_appends_task_to_the_new_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            create_task(path, "Alta 1", "high")
            create_task(path, "Alta 2", "high")
            medium = next(
                task
                for task in create_task(path, "Média", "medium")
                if task["nome"] == "Média"
            )

            updated = update_task_priority(path, medium["id"], "high")

            self.assertEqual(
                [task["nome"] for task in updated],
                ["Alta 1", "Alta 2", "Média"],
            )

    def test_starts_and_pauses_timer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            task = create_task(path, "Cronometrada", "medium")[0]

            running = toggle_task_timer(path, task["id"])[0]
            self.assertIsNotNone(running["cronometro_iniciado_em"])
            self.assertTrue(running["atividade_iniciada"])

            paused = toggle_task_timer(path, task["id"])[0]
            self.assertIsNone(paused["cronometro_iniciado_em"])
            self.assertGreaterEqual(paused["tempo_acumulado_segundos"], 0)
            self.assertTrue(paused["atividade_iniciada"])

    def test_edits_tags_and_preserves_color_by_position(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            task = create_task(path, "Tarefa #antiga", "medium")[0]
            previous_color = task["cores_tags"]["antiga"]

            updated_tasks = update_task_tags(path, task["id"], "#nova #extra #nova")
            updated = next(item for item in updated_tasks if item["id"] == task["id"])

            self.assertEqual(updated["tags"], ["nova", "extra"])
            self.assertEqual(updated["cores_tags"]["nova"], previous_color)
            with self.assertRaisesRegex(ValueError, "INVALID_TAG_FORMAT"):
                update_task_tags(path, task["id"], "tag-sem-cerquilha")

    def test_renaming_to_known_tag_keeps_its_existing_color(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            first = create_task(path, "Primeira #antiga", "medium")[0]
            tasks = create_task(path, "Segunda #existente", "low")
            existing = next(task for task in tasks if task["nome"] == "Segunda")
            existing_color = existing["cores_tags"]["existente"]

            updated = update_task_tags(path, first["id"], "#existente")

            self.assertEqual(
                {task["cores_tags"]["existente"] for task in updated},
                {existing_color},
            )

    @patch("backend.tasks._random_tag_color", return_value="#13579B")
    def test_color_override_is_propagated_to_completed_tasks(
        self, _random_tag_color
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            active = create_task(path, "Ativa #compartilhada", "medium")[0]
            completed = next(
                task
                for task in create_task(
                    path, "Concluída #compartilhada", "medium"
                )
                if task["nome"] == "Concluída"
            )
            complete_task(path, completed["id"])

            updated = update_task_tags(
                path,
                active["id"],
                "#compartilhada",
                {"compartilhada": "#a1b2c3"},
            )
            completed_after_update = load_completed_tasks(path)[0]
            saved = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(
                updated[0]["cores_tags"]["compartilhada"], "#A1B2C3"
            )
            self.assertEqual(
                completed_after_update["cores_tags"]["compartilhada"],
                "#A1B2C3",
            )
            self.assertTrue(
                all(
                    task["cores_tags"]["compartilhada"] == "#A1B2C3"
                    for task in saved
                )
            )

    @patch("backend.tasks._random_tag_color", return_value="#13579B")
    def test_rejects_invalid_or_unknown_color_overrides(
        self, _random_tag_color
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            task = create_task(path, "Tarefa #conhecida", "medium")[0]
            original = path.read_text(encoding="utf-8")
            invalid_overrides = (
                {"conhecida": -1},
                {"conhecida": 0},
                {"conhecida": True},
                {"conhecida": 1.5},
                {"conhecida": "1"},
                {"conhecida": "red"},
                {"conhecida": "#123"},
                {"conhecida": "#12345G"},
                {"conhecida": "#1234567"},
                {"desconhecida": "#ABCDEF"},
            )

            for color_overrides in invalid_overrides:
                with self.subTest(color_overrides=color_overrides):
                    with self.assertRaises(ValueError):
                        update_task_tags(
                            path,
                            task["id"],
                            "#conhecida",
                            color_overrides,
                        )
                    self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_migrates_legacy_color_indexes_to_hex_palette(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            expected_colors = {
                "tag0": "#3B245C",
                "tag1": "#193B59",
                "tag2": "#12433A",
                "tag3": "#4A3512",
                "tag4": "#54291D",
                "tag5": "#51232F",
                "tag6": "#263E5A",
                "tag7": "#183F4A",
            }
            path.write_text(
                json.dumps(
                    [
                        {
                            "id": "legacy-colors",
                            "nome": "Tarefa legada",
                            "prioridade": "Média",
                            "adicionada_em": "2026-08-04T09:00:00-03:00",
                            "tags": list(expected_colors),
                            "cores_tags": {
                                tag: index
                                for index, tag in enumerate(expected_colors)
                            },
                            "tempo_acumulado_segundos": 0,
                            "cronometro_iniciado_em": None,
                            "deletedAt": None,
                            "completedAt": None,
                        }
                    ]
                ),
                encoding="utf-8",
            )

            loaded = load_tasks(path)[0]
            saved = json.loads(path.read_text(encoding="utf-8"))[0]

            self.assertEqual(loaded["cores_tags"], expected_colors)
            self.assertEqual(saved["cores_tags"], expected_colors)

    def test_normalizes_persisted_hex_colors_to_uppercase(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "id": "lowercase-color",
                            "nome": "Tarefa colorida",
                            "prioridade": "Média",
                            "adicionada_em": "2026-08-04T09:00:00-03:00",
                            "tags": ["colorida"],
                            "cores_tags": {"colorida": "#a1b2c3"},
                            "tempo_acumulado_segundos": 0,
                            "cronometro_iniciado_em": None,
                            "deletedAt": None,
                            "completedAt": None,
                        }
                    ]
                ),
                encoding="utf-8",
            )

            loaded = load_tasks(path)[0]
            saved = json.loads(path.read_text(encoding="utf-8"))[0]

            self.assertEqual(loaded["cores_tags"]["colorida"], "#A1B2C3")
            self.assertEqual(saved["cores_tags"]["colorida"], "#A1B2C3")

    def test_migrates_legacy_task_to_complete_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            completed_at = "2026-08-04T12:00:00-03:00"
            path.write_text(
                json.dumps(
                    [
                        {
                            "nome": "Comprar pão #Casa #casa",
                            "prioridade": "Alta",
                            "tags": ["MERCADO", "mercado"],
                            "completedAt": completed_at,
                        }
                    ]
                ),
                encoding="utf-8",
            )

            completed = load_completed_tasks(path)
            saved = json.loads(path.read_text(encoding="utf-8"))[0]

            self.assertEqual(len(completed), 1)
            self.assertEqual(saved["nome"], "Comprar pão")
            self.assertEqual(saved["tags"], ["mercado", "casa"])
            self.assertEqual(saved["deletedAt"], completed_at)
            self.assertEqual(saved["tempo_acumulado_segundos"], 0)
            self.assertIsNone(saved["cronometro_iniciado_em"])
            self.assertFalse(saved["atividade_iniciada"])
            self.assertTrue(saved["id"])
            self.assertEqual(set(saved["cores_tags"]), {"mercado", "casa"})

    def test_migrates_and_normalizes_activity_started_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "id": "paused",
                            "nome": "Pausada",
                            "prioridade": "Média",
                            "adicionada_em": "2026-08-04T09:00:00-03:00",
                            "tags": [],
                            "cores_tags": {},
                            "tempo_acumulado_segundos": 10,
                            "cronometro_iniciado_em": None,
                            "atividade_iniciada": False,
                            "deletedAt": None,
                            "completedAt": None,
                        }
                    ]
                ),
                encoding="utf-8",
            )

            loaded = load_tasks(path)[0]
            saved = json.loads(path.read_text(encoding="utf-8"))[0]

            self.assertTrue(loaded["atividade_iniciada"])
            self.assertTrue(saved["atividade_iniciada"])

    def test_rejects_invalid_activity_started_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "nome": "Inválida",
                            "prioridade": "Média",
                            "atividade_iniciada": "sim",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            original = path.read_text(encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "estado de atividade"):
                load_tasks(path)

            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_consolidates_running_timer_of_deleted_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "nome": "Removida",
                            "prioridade": "Média",
                            "adicionada_em": "2026-08-04T09:00:00-03:00",
                            "tags": [],
                            "cores_tags": {},
                            "tempo_acumulado_segundos": 10,
                            "cronometro_iniciado_em": "2026-08-04T10:00:00-03:00",
                            "deletedAt": "2026-08-04T10:01:00-03:00",
                            "completedAt": None,
                        }
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(load_tasks(path), [])
            saved = json.loads(path.read_text(encoding="utf-8"))[0]
            self.assertEqual(saved["tempo_acumulado_segundos"], 70)
            self.assertIsNone(saved["cronometro_iniciado_em"])
            self.assertTrue(saved["atividade_iniciada"])

    def test_invalid_file_is_rejected_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            original = json.dumps(
                [
                    {
                        "nome": "Inválida",
                        "prioridade": "Média",
                        "adicionada_em": "2026-08-04T09:00:00",
                    }
                ]
            )
            path.write_text(original, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "fuso horário"):
                load_tasks(path)

            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_rejects_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tarefas.json"
            path.write_text("{não é json", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "JSON válido"):
                load_tasks(path)


if __name__ == "__main__":
    unittest.main()
