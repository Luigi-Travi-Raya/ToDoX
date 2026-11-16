import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend import tasks as task_storage
from backend.api import AppApi


class AppApiTest(unittest.TestCase):
    def test_internal_references_are_not_public_bridge_attributes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api = AppApi(Path(directory) / "tarefas.json", Mock())

            self.assertNotIn("desktop", vars(api))
            self.assertNotIn("tasks_path", vars(api))
            self.assertIn("_desktop", vars(api))
            self.assertIn("_tasks_path", vars(api))

    @patch("backend.api.reorder_tasks", return_value=[])
    @patch("backend.api.toggle_task_timer", return_value=[])
    @patch("backend.api.update_task_tags", return_value=[])
    @patch("backend.api.delete_task", return_value=[])
    @patch("backend.api.complete_task", return_value=[])
    @patch("backend.api.update_task_priority", return_value=[])
    @patch("backend.api.update_task_name", return_value=[])
    @patch("backend.api.create_task", return_value=[])
    def test_every_task_mutation_notifies_desktop(
        self,
        create_task,
        update_task_name,
        update_task_priority,
        complete_task,
        delete_task,
        update_task_tags,
        toggle_task_timer,
        reorder_tasks,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            desktop = Mock()
            api = AppApi(Path(directory) / "tarefas.json", desktop)

            api.create_task("Nova", "medium")
            api.update_task_name("1", "Novo nome")
            api.update_task_priority("1", "high")
            api.reorder_tasks(["1", "2"])
            api.complete_task("1")
            api.delete_task("1")
            api.toggle_task_timer("1")
            api.update_task_tags("1", "#tag", {})

            self.assertEqual(desktop.notify_tasks_changed.call_count, 8)
            self.assertEqual(
                [call.args[0]["revision"] for call in desktop.notify_tasks_changed.call_args_list],
                list(range(1, 9)),
            )
            create_task.assert_called_once()
            update_task_name.assert_called_once()
            update_task_priority.assert_called_once()
            complete_task.assert_called_once()
            delete_task.assert_called_once()
            toggle_task_timer.assert_called_once()
            update_task_tags.assert_called_once()
            reorder_tasks.assert_called_once()

    def test_task_state_reads_active_and_completed_tasks_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api = AppApi(Path(directory) / "tarefas.json", Mock())
            first = api.create_task("First", "medium")["tasks"][0]
            api.create_task("Second", "high")
            api.complete_task(first["id"])

            with patch(
                "backend.tasks._load_all_tasks", wraps=task_storage._load_all_tasks
            ) as load_all:
                state = api.get_task_state()

            load_all.assert_called_once_with(api._tasks_path)
            self.assertEqual(state["revision"], 3)
            self.assertEqual(state["history_revision"], 3)
            self.assertEqual([task["nome"] for task in state["tasks"]], ["Second"])
            self.assertEqual(
                [task["id"] for task in state["completed_tasks"]], [first["id"]]
            )

    def test_completion_reuses_its_loaded_tasks_and_versions_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            desktop = Mock()
            api = AppApi(Path(directory) / "tarefas.json", desktop)
            created = api.create_task("Task", "medium")
            task_id = created["tasks"][0]["id"]
            desktop.reset_mock()

            with patch(
                "backend.tasks._load_all_tasks", wraps=task_storage._load_all_tasks
            ) as load_all:
                update = api.complete_task(task_id)
                self.assertEqual(load_all.call_count, 1)
                history = api.list_completed_tasks()
                self.assertEqual(load_all.call_count, 2)

            self.assertEqual(update, {"revision": 2, "history_revision": 2, "tasks": []})
            desktop.notify_tasks_changed.assert_called_once_with(update)
            self.assertEqual(history["history_revision"], 2)
            self.assertEqual(history["tasks"][0]["id"], task_id)

    def test_active_edits_leave_history_version_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api = AppApi(Path(directory) / "tarefas.json", Mock())
            task_id = api.create_task("Task", "medium")["tasks"][0]["id"]
            updates = [
                api.toggle_task_timer(task_id),
                api.update_task_priority(task_id, "high"),
                api.update_task_name(task_id, "Renamed"),
                api.add_checklist_item(task_id, "Step"),
            ]

            self.assertEqual([update["revision"] for update in updates], [2, 3, 4, 5])
            self.assertTrue(all(update["history_revision"] == 0 for update in updates))
            completion = api.complete_task(task_id)
            next_creation = api.create_task("Next task", "low")
            self.assertEqual(completion["history_revision"], 6)
            self.assertEqual(next_creation["revision"], 7)
            self.assertEqual(next_creation["history_revision"], 6)

    def test_mutating_completed_task_invalidates_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api = AppApi(Path(directory) / "tarefas.json", Mock())
            task_id = api.create_task("Task", "medium")["tasks"][0]["id"]
            api.complete_task(task_id)

            priority_update = api.update_task_priority(task_id, "high")
            with patch(
                "backend.tasks._load_all_tasks", wraps=task_storage._load_all_tasks
            ) as load_all:
                timer_update = api.toggle_task_timer(task_id)

            self.assertEqual(load_all.call_count, 2)

            self.assertEqual(priority_update["history_revision"], 3)
            self.assertEqual(timer_update["history_revision"], 4)
            self.assertEqual(priority_update["tasks"], [])
            self.assertEqual(timer_update["tasks"], [])
            history = api.list_completed_tasks()
            self.assertEqual(history["history_revision"], 4)
            self.assertEqual(history["tasks"][0]["prioridade"], "high")
            self.assertTrue(history["tasks"][0]["atividade_iniciada"])

    def test_active_timer_uses_one_read_per_toggle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api = AppApi(Path(directory) / "tarefas.json", Mock())
            task_id = api.create_task("Task", "medium")["tasks"][0]["id"]

            with patch(
                "backend.tasks._load_all_tasks", wraps=task_storage._load_all_tasks
            ) as load_all:
                running = api.toggle_task_timer(task_id)
                self.assertEqual(load_all.call_count, 1)
                paused = api.toggle_task_timer(task_id)
                self.assertEqual(load_all.call_count, 2)

            self.assertIsNotNone(running["tasks"][0]["cronometro_iniciado_em"])
            self.assertIsNone(paused["tasks"][0]["cronometro_iniciado_em"])
            self.assertEqual(running["revision"], 2)
            self.assertEqual(paused["revision"], 3)
            self.assertEqual(paused["history_revision"], 0)

    def test_failed_mutation_does_not_advance_versions_or_notify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            desktop = Mock()
            api = AppApi(Path(directory) / "tarefas.json", desktop)
            task_id = api.create_task("Task", "medium")["tasks"][0]["id"]
            desktop.reset_mock()

            with self.assertRaisesRegex(ValueError, "TASK_NAME_REQUIRED"):
                api.update_task_name(task_id, " ")

            state = api.get_task_state()
            self.assertEqual(state["revision"], 1)
            self.assertEqual(state["history_revision"], 0)
            desktop.notify_tasks_changed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
