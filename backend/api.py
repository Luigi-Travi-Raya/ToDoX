import threading
from pathlib import Path
from typing import Any, TypedDict

from .tasks import (
    add_checklist_item,
    complete_task,
    create_task,
    delete_checklist_item,
    delete_task,
    load_completed_tasks,
    load_task_state,
    load_tasks,
    reorder_tasks,
    set_checklist_item_completed,
    toggle_task_timer,
    update_checklist_item,
    update_task_name,
    update_task_priority,
    update_task_tags,
)


class TaskUpdate(TypedDict):
    revision: int
    history_revision: int
    tasks: list[dict[str, Any]]


class TaskState(TaskUpdate):
    completed_tasks: list[dict[str, Any]]


class CompletedTaskState(TypedDict):
    history_revision: int
    tasks: list[dict[str, Any]]


class AppApi:
    """Pequena superfície exposta pelo Python ao Vue."""

    def __init__(self, tasks_path: Path, desktop: Any) -> None:
        self._tasks_path = tasks_path
        self._desktop = desktop
        self._tasks_lock = threading.RLock()
        self._revision = 0
        self._history_revision = 0

    def list_tasks(self) -> list[dict[str, Any]]:
        with self._tasks_lock:
            return load_tasks(self._tasks_path)

    def get_task_state(self) -> TaskState:
        with self._tasks_lock:
            state = load_task_state(self._tasks_path)
            return {
                "revision": self._revision,
                "history_revision": self._history_revision,
                "tasks": state["tasks"],
                "completed_tasks": state["completed_tasks"],
            }

    def list_completed_tasks(self) -> CompletedTaskState:
        with self._tasks_lock:
            return {
                "history_revision": self._history_revision,
                "tasks": load_completed_tasks(self._tasks_path),
            }

    def create_task(
        self, name: str, priority: str
    ) -> TaskUpdate:
        with self._tasks_lock:
            tasks = create_task(self._tasks_path, name, priority)
            return self._publish_tasks(tasks)

    def update_task_priority(
        self, task_id: str, priority: str
    ) -> TaskUpdate:
        with self._tasks_lock:
            tasks = update_task_priority(self._tasks_path, task_id, priority)
            history_changed = not any(task["id"] == task_id for task in tasks)
            return self._publish_tasks(tasks, history_changed=history_changed)

    def update_task_name(
        self, task_id: str, name: str
    ) -> TaskUpdate:
        with self._tasks_lock:
            tasks = update_task_name(self._tasks_path, task_id, name)
            return self._publish_tasks(tasks)

    def reorder_tasks(self, ordered_task_ids: list[str]) -> TaskUpdate:
        with self._tasks_lock:
            tasks = reorder_tasks(self._tasks_path, ordered_task_ids)
            return self._publish_tasks(tasks)

    def complete_task(self, task_id: str) -> TaskUpdate:
        with self._tasks_lock:
            tasks = complete_task(self._tasks_path, task_id)
            return self._publish_tasks(tasks, history_changed=True)

    def delete_task(self, task_id: str) -> TaskUpdate:
        with self._tasks_lock:
            tasks = delete_task(self._tasks_path, task_id)
            return self._publish_tasks(tasks, history_changed=True)

    def toggle_task_timer(self, task_id: str) -> TaskUpdate:
        with self._tasks_lock:
            tasks = toggle_task_timer(self._tasks_path, task_id)
            history_changed = not any(task["id"] == task_id for task in tasks)
            return self._publish_tasks(tasks, history_changed=history_changed)

    def update_task_tags(
        self,
        task_id: str,
        tags: str,
        color_overrides: dict[str, str] | None = None,
    ) -> TaskUpdate:
        with self._tasks_lock:
            tasks = update_task_tags(
                self._tasks_path, task_id, tags, color_overrides
            )
            return self._publish_tasks(tasks, history_changed=True)

    def add_checklist_item(self, task_id: str, name: str) -> TaskUpdate:
        with self._tasks_lock:
            tasks = add_checklist_item(self._tasks_path, task_id, name)
            return self._publish_tasks(tasks)

    def update_checklist_item(
        self, task_id: str, item_id: str, name: str
    ) -> TaskUpdate:
        with self._tasks_lock:
            tasks = update_checklist_item(self._tasks_path, task_id, item_id, name)
            return self._publish_tasks(tasks)

    def set_checklist_item_completed(
        self, task_id: str, item_id: str, completed: bool
    ) -> TaskUpdate:
        with self._tasks_lock:
            tasks = set_checklist_item_completed(
                self._tasks_path, task_id, item_id, completed
            )
            return self._publish_tasks(tasks)

    def delete_checklist_item(self, task_id: str, item_id: str) -> TaskUpdate:
        with self._tasks_lock:
            tasks = delete_checklist_item(self._tasks_path, task_id, item_id)
            return self._publish_tasks(tasks)

    def get_settings(self) -> dict[str, Any]:
        return self._desktop.get_settings()

    def save_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        return self._desktop.apply_settings(settings)

    def get_startup_warnings(self) -> list[dict[str, str]]:
        return self._desktop.get_startup_warnings()

    def set_settings_open(self, is_open: bool) -> None:
        self._desktop.set_settings_open(is_open)

    def open_quick_add(self) -> None:
        self._desktop.open_quick_add()

    def close_quick_window(self) -> None:
        self._desktop.close_quick_window()

    def close_tray_menu(self) -> None:
        self._desktop.close_tray_menu()

    def hide_main_window(self) -> None:
        self._desktop.hide_main_window()

    def show_main_window(self) -> None:
        self._desktop.show_main_window()

    def exit_app(self) -> None:
        self._desktop.request_exit()

    def _publish_tasks(
        self, tasks: list[dict[str, Any]], *, history_changed: bool = False
    ) -> TaskUpdate:
        # Call only while _tasks_lock is held, so responses and queued events
        # describe mutations in the same order across all windows.
        self._revision += 1
        if history_changed:
            self._history_revision = self._revision
        update: TaskUpdate = {
            "revision": self._revision,
            "history_revision": self._history_revision,
            "tasks": tasks,
        }
        self._desktop.notify_tasks_changed(update)
        return update
