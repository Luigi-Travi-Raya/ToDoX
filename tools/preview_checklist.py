r"""Open the real frontend/bridge with disposable checklist data for native QA.

Run from new/: .\.venv\Scripts\python.exe -m tools.preview_checklist
No user data, tray integration or global shortcut is loaded.
"""

from __future__ import annotations

import argparse
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

import webview

from backend.api import AppApi
from backend.settings import DEFAULT_SETTINGS, hotkey_description, validate_settings


class PreviewDesktop:
    def __init__(self, theme: str, locale: str) -> None:
        self.window: Any = None
        self.settings = {**DEFAULT_SETTINGS, "tema": theme, "locale": locale}

    def get_settings(self) -> dict[str, Any]:
        return {**self.settings, "description": hotkey_description(self.settings)}

    def apply_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        self.settings = validate_settings(settings)
        return self.get_settings()

    def get_startup_warnings(self) -> list[Any]:
        return []

    def set_settings_open(self, is_open: bool) -> None:
        pass

    def notify_tasks_changed(self, update: dict[str, Any]) -> None:
        window = self.window
        if window is None:
            return

        def notify() -> None:
            try:
                window.run_js(
                    "window.dispatchEvent(new CustomEvent('tasks-changed',"
                    f"{{detail:{json.dumps(update)}}}))"
                )
            except Exception:
                pass

        threading.Thread(target=notify, daemon=True).start()

    def hide_main_window(self) -> None:
        self.request_exit()

    def show_main_window(self) -> None:
        self.window.show()

    def request_exit(self) -> None:
        self.window.destroy()


def fixture_tasks(stress: bool = False) -> list[dict[str, Any]]:
    now = datetime.now().astimezone()

    def item(name: str, completed: bool = False) -> dict[str, Any]:
        return {"id": str(uuid4()), "nome": name, "concluido": completed}

    def task(name: str, priority: str, order: int) -> dict[str, Any]:
        return {
            "id": str(uuid4()),
            "nome": name,
            "prioridade": priority,
            "ordem": order,
            "adicionada_em": now.isoformat(),
            "tags": [],
            "cores_tags": {},
            "tempo_acumulado_segundos": 0,
            "cronometro_iniciado_em": None,
            "atividade_iniciada": False,
            "deletedAt": None,
            "completedAt": None,
            "checklist": [],
        }

    first = task("Prepare project handoff", "high", 0)
    first.update(
        tags=["work", "release"],
        cores_tags={"work": "#7C5CFC", "release": "#6651DC"},
        cronometro_iniciado_em=(now - timedelta(minutes=24, seconds=10)).isoformat(),
        atividade_iniciada=True,
        checklist=[
            item("Review requirements", True),
            item("Collect assets", True),
            item("Write release notes"),
            item("Send handoff"),
        ],
    )
    second = task("Plan weekly priorities", "medium", 1)
    second.update(
        tags=["work"],
        cores_tags={"work": "#7C5CFC"},
        checklist=[item("Review last week", True), item("Choose priorities"), item("Share plan")],
    )
    third = task("Book team meeting", "low", 2)
    completed = task("Previous release", "low", 3)
    completed.update(
        completedAt=now.isoformat(),
        deletedAt=now.isoformat(),
        atividade_iniciada=True,
        tempo_acumulado_segundos=600,
        checklist=[item("Publish build", True), item("Write retrospective")],
    )
    if stress:
        first["nome"] = "Prepare project handoff — review outstanding decisions, release assets and the team's final delivery checklist"
        first["checklist"][-1]["nome"] = "担当者と最終確認を行い、リリースノートと添付資料をすべて確認する — review every outstanding decision before sharing the final handoff"
        first["tags"].extend(["design", "quality"])
        first["cores_tags"].update(design="#A4470F", quality="#176783")
    return [first, second, third, completed]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", choices=["dark", "light"], default="dark")
    parser.add_argument("--locale", choices=["en", "pt-BR", "es", "de", "ja"], default="en")
    parser.add_argument("--width", type=int, default=760)
    parser.add_argument("--height", type=int, default=520)
    parser.add_argument("--stress", action="store_true", help="Include long task/item names and multiple tags")
    args = parser.parse_args()
    frontend = Path(__file__).resolve().parents[1] / "frontend" / "dist" / "index.html"
    if not frontend.is_file():
        parser.error("Build the frontend first: npm run build --prefix frontend")

    with TemporaryDirectory(prefix="todox-checklist-qa-") as directory:
        tasks_path = Path(directory) / "tarefas.json"
        tasks_path.write_text(json.dumps(fixture_tasks(args.stress), ensure_ascii=False), encoding="utf-8")
        desktop = PreviewDesktop(args.theme, args.locale)
        api = AppApi(tasks_path, desktop)
        desktop.window = webview.create_window(
            "ToDoX — Checklist QA (temporary data)",
            str(frontend),
            js_api=api,
            width=args.width,
            height=args.height,
            min_size=(320, 360),
            background_color="#090e1a" if args.theme == "dark" else "#eef2f7",
        )
        print(f"Disposable fixture: {tasks_path}", flush=True)
        webview.start()


if __name__ == "__main__":
    main()
