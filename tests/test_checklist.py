import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from backend.api import AppApi
from backend.errors import AppError
from backend.tasks import (
    add_checklist_item, complete_task, create_task, delete_checklist_item,
    delete_task, load_completed_tasks, load_tasks,
    set_checklist_item_completed, toggle_task_timer, update_checklist_item,
    update_task_name, update_task_priority, update_task_tags,
)


class ChecklistTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "tasks.json"
        self.task = create_task(self.path, "Parent #work", "medium")[0]
        self.task_id = self.task["id"]

    def test_legacy_tasks_get_empty_checklist_without_losing_history(self) -> None:
        complete_task(self.path, self.task_id)
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        saved[0].pop("checklist")
        self.path.write_text(json.dumps(saved), encoding="utf-8")
        completed = load_completed_tasks(self.path)[0]
        self.assertEqual(completed["checklist"], [])
        for key, value in saved[0].items():
            self.assertEqual(completed[key], value)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))[0]["checklist"], [])

    def test_mutations_persist_ids_order_state_unicode_and_literal_tags(self) -> None:
        tasks = add_checklist_item(self.path, self.task_id, "  First\nstep #literal  ")
        first = tasks[0]["checklist"][0]
        self.assertEqual(first["nome"], "First step #literal")
        self.assertEqual(tasks[0]["tags"], ["work"])
        add_checklist_item(self.path, self.task_id, "次の項目")
        update_checklist_item(self.path, self.task_id, first["id"], "😀" * 120)
        set_checklist_item_completed(self.path, self.task_id, first["id"], True)
        set_checklist_item_completed(self.path, self.task_id, first["id"], True)
        checklist = load_tasks(self.path)[0]["checklist"]
        self.assertEqual(checklist[0], {"id": first["id"], "nome": "😀" * 120, "concluido": True})
        self.assertEqual(checklist[1]["nome"], "次の項目")
        for key, value in self.task.items():
            if key not in {"checklist", "cronometro_iniciado_em", "atividade_iniciada"}:
                self.assertEqual(load_tasks(self.path)[0][key], value)
        self.assertIsNotNone(load_tasks(self.path)[0]["cronometro_iniciado_em"])
        self.assertTrue(load_tasks(self.path)[0]["atividade_iniciada"])

    def test_delete_preserves_remaining_items_order_and_marks(self) -> None:
        for name in ("First", "Second", "Third"):
            add_checklist_item(self.path, self.task_id, name)
        original = load_tasks(self.path)[0]["checklist"]
        item = original[1]
        set_checklist_item_completed(self.path, self.task_id, item["id"], True)
        item["concluido"] = True
        delete_checklist_item(self.path, self.task_id, item["id"])
        self.assertEqual(load_tasks(self.path)[0]["checklist"], [original[0], original[2]])
        before = self.path.read_bytes()
        with self.assertRaisesRegex(AppError, "CHECKLIST_ITEM_NOT_FOUND"):
            delete_checklist_item(self.path, self.task_id, item["id"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_first_completed_item_starts_timer_even_out_of_order(self) -> None:
        add_checklist_item(self.path, self.task_id, "First row")
        second = add_checklist_item(self.path, self.task_id, "Second row")[0]["checklist"][1]
        fixed_now = datetime(2026, 11, 16, 18, 0, tzinfo=timezone.utc)
        with patch("backend.tasks.datetime", wraps=datetime) as clock:
            clock.now.return_value = fixed_now
            task = set_checklist_item_completed(self.path, self.task_id, second["id"], True)[0]
        self.assertEqual(datetime.fromisoformat(task["cronometro_iniciado_em"]), fixed_now)
        self.assertTrue(task["atividade_iniciada"])
        self.assertEqual(task["tempo_acumulado_segundos"], 0)
        self.assertFalse(task["checklist"][0]["concluido"])
        self.assertTrue(task["checklist"][1]["concluido"])
        self.assertIsNone(task["completedAt"])
        self.assertEqual(load_tasks(self.path)[0], task)

    def test_first_completion_resumes_paused_activity_preserving_accumulated_time(self) -> None:
        fixed_now = datetime(2026, 11, 16, 18, 0, tzinfo=timezone.utc)
        for accumulated in (0, 145):
            with self.subTest(accumulated=accumulated):
                self.path.write_text(json.dumps([self.task]), encoding="utf-8")
                task = add_checklist_item(self.path, self.task_id, "Step")[0]
                task.update(tempo_acumulado_segundos=accumulated, atividade_iniciada=True)
                self.path.write_text(json.dumps([task]), encoding="utf-8")
                with patch("backend.tasks.datetime", wraps=datetime) as clock:
                    clock.now.return_value = fixed_now
                    updated = set_checklist_item_completed(self.path, self.task_id, task["checklist"][0]["id"], True)[0]
                self.assertEqual(datetime.fromisoformat(updated["cronometro_iniciado_em"]), fixed_now)
                self.assertEqual(updated["tempo_acumulado_segundos"], accumulated)
                self.assertTrue(updated["atividade_iniciada"])

    def test_first_completion_does_not_reset_running_timer(self) -> None:
        task = add_checklist_item(self.path, self.task_id, "Step")[0]
        fixed_now = datetime(2026, 11, 16, 18, 0, tzinfo=timezone.utc)
        started_at = (fixed_now - timedelta(minutes=5)).isoformat()
        task.update(cronometro_iniciado_em=started_at, atividade_iniciada=True, tempo_acumulado_segundos=65)
        self.path.write_text(json.dumps([task]), encoding="utf-8")
        with patch("backend.tasks.datetime", wraps=datetime) as clock:
            clock.now.return_value = fixed_now
            updated = set_checklist_item_completed(self.path, self.task_id, task["checklist"][0]["id"], True)[0]
        self.assertEqual(updated["cronometro_iniciado_em"], started_at)
        self.assertEqual(updated["tempo_acumulado_segundos"], 65)

    def test_repeated_marks_later_completions_and_unchecking_do_not_resume_timer(self) -> None:
        add_checklist_item(self.path, self.task_id, "First")
        first, second = add_checklist_item(self.path, self.task_id, "Second")[0]["checklist"]
        fixed_now = datetime(2026, 11, 16, 18, 0, tzinfo=timezone.utc)
        with patch("backend.tasks.datetime", wraps=datetime) as clock:
            clock.now.return_value = fixed_now
            set_checklist_item_completed(self.path, self.task_id, first["id"], True)
            toggle_task_timer(self.path, self.task_id)
            for item_id, completed in ((first["id"], True), (second["id"], True),
                                       (first["id"], False), (second["id"], False)):
                updated = set_checklist_item_completed(self.path, self.task_id, item_id, completed)[0]
                self.assertIsNone(updated["cronometro_iniciado_em"])
                self.assertEqual(updated["tempo_acumulado_segundos"], 0)
            updated = set_checklist_item_completed(self.path, self.task_id, second["id"], True)[0]
        self.assertIsNotNone(updated["cronometro_iniciado_em"])

    def test_timer_and_parent_changes_preserve_checklist_and_partial_history(self) -> None:
        item = add_checklist_item(self.path, self.task_id, "Pending")[0]["checklist"][0]
        update_task_name(self.path, self.task_id, "Renamed")
        update_task_priority(self.path, self.task_id, "high")
        update_task_tags(self.path, self.task_id, "#new", {})
        running = toggle_task_timer(self.path, self.task_id)[0]
        self.assertEqual(running["checklist"], [item])
        complete_task(self.path, self.task_id)
        completed = load_completed_tasks(self.path)[0]
        self.assertEqual(completed["checklist"], [item])
        self.assertIsNone(completed["cronometro_iniciado_em"])
        before = self.path.read_bytes()
        operations = [
            lambda: add_checklist_item(self.path, self.task_id, "New"),
            lambda: update_checklist_item(self.path, self.task_id, item["id"], "Edit"),
            lambda: set_checklist_item_completed(self.path, self.task_id, item["id"], True),
            lambda: delete_checklist_item(self.path, self.task_id, item["id"]),
        ]
        for operation in operations:
            with self.assertRaisesRegex(AppError, "COMPLETED_TASK_READ_ONLY"):
                operation()
        self.assertEqual(self.path.read_bytes(), before)

    def test_deleted_parent_rejects_checklist_mutations(self) -> None:
        add_checklist_item(self.path, self.task_id, "Keep")
        delete_task(self.path, self.task_id)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(AppError, "COMPLETED_TASK_READ_ONLY"):
            add_checklist_item(self.path, self.task_id, "New")
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_input_and_missing_item_leave_file_unchanged(self) -> None:
        before = self.path.read_bytes()
        for name in (None, 7, " ", "x" * 121, "😀" * 121):
            with self.assertRaises(AppError):
                add_checklist_item(self.path, self.task_id, name)
        with self.assertRaisesRegex(AppError, "CHECKLIST_ITEM_NOT_FOUND"):
            update_checklist_item(self.path, self.task_id, "missing", "Name")
        with self.assertRaises(AppError):
            set_checklist_item_completed(self.path, self.task_id, "missing", 1)
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_stored_checklists_never_trigger_partial_migration(self) -> None:
        item = {"id": "item", "nome": "Step", "concluido": False}
        invalid = [None, {}, "text", [None], [item, item], [{**item, "id": " "}],
                   [{**item, "concluido": 1}], [{**item, "nome": " "}],
                   [{**item, "nome": "x" * 121}], [{**item, "unknown": True}]]
        for checklist in invalid:
            with self.subTest(checklist=checklist):
                legacy = {"nome": "Legacy", "prioridade": "Média"}
                broken = {**self.task, "id": "broken", "checklist": checklist}
                self.path.write_text(json.dumps([legacy, broken]), encoding="utf-8")
                before = self.path.read_bytes()
                with self.assertRaises(ValueError):
                    load_tasks(self.path)
                self.assertEqual(self.path.read_bytes(), before)

    def test_disk_failure_does_not_report_success_or_replace_confirmed_file(self) -> None:
        item = add_checklist_item(self.path, self.task_id, "Step")[0]["checklist"][0]
        before = self.path.read_bytes()
        with patch("backend.tasks._save_tasks", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                set_checklist_item_completed(self.path, self.task_id, item["id"], True)
        self.assertEqual(self.path.read_bytes(), before)


class ChecklistApiTest(unittest.TestCase):
    def test_bridge_notifies_only_successful_mutations_and_preserves_return_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            desktop = Mock()
            api = AppApi(Path(directory) / "tasks.json", desktop)
            task_id = api.create_task("Parent", "medium")["tasks"][0]["id"]
            desktop.reset_mock()
            item = api.add_checklist_item(task_id, "Step")["tasks"][0]["checklist"][0]
            api.update_checklist_item(task_id, item["id"], "Renamed")
            updated = api.set_checklist_item_completed(task_id, item["id"], True)["tasks"][0]
            self.assertIsNotNone(updated["cronometro_iniciado_em"])
            self.assertTrue(updated["atividade_iniciada"])
            deletion = api.delete_checklist_item(task_id, item["id"])
            self.assertEqual(deletion["tasks"][0]["checklist"], [])
            self.assertEqual(deletion["revision"], 5)
            self.assertEqual(deletion["history_revision"], 0)
            self.assertEqual(desktop.notify_tasks_changed.call_count, 4)
            with self.assertRaises(AppError):
                api.add_checklist_item(task_id, "")
            self.assertEqual(desktop.notify_tasks_changed.call_count, 4)

    def test_concurrent_item_additions_are_serialized_without_lost_steps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            desktop = Mock()
            api = AppApi(Path(directory) / "tasks.json", desktop)
            task_id = api.create_task("Parent", "medium")["tasks"][0]["id"]
            with ThreadPoolExecutor(max_workers=4) as pool:
                updates = list(pool.map(lambda index: api.add_checklist_item(task_id, str(index)), range(12)))
            checklist = api.list_tasks()[0]["checklist"]
            self.assertEqual({item["nome"] for item in checklist}, {str(i) for i in range(12)})
            self.assertEqual(len({item["id"] for item in checklist}), 12)
            self.assertEqual(sorted(update["revision"] for update in updates), list(range(2, 14)))
            self.assertEqual(
                [call.args[0]["revision"] for call in desktop.notify_tasks_changed.call_args_list],
                list(range(1, 14)),
            )


if __name__ == "__main__":
    unittest.main()
