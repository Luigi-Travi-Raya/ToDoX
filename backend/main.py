from __future__ import annotations

import sys
from pathlib import Path

from backend.desktop import DesktopApp
from backend.data_paths import application_data_directory


SOURCE_DIR = Path(__file__).resolve().parents[1]
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", SOURCE_DIR))
DATA_DIR = application_data_directory(SOURCE_DIR)
FRONTEND_DIST = RESOURCE_DIR / "frontend" / "dist" / "index.html"
TASKS_FILE = DATA_DIR / "tarefas.json"
SETTINGS_FILE = DATA_DIR / "configuracoes.json"
WINDOW_ICON_FILE = RESOURCE_DIR / "assets" / "branding" / "todox.ico"
TRAY_ICON_FILE = RESOURCE_DIR / "assets" / "branding" / "todox-tray.png"


def frontend_url() -> str:
    if "--dev" in sys.argv:
        return "http://localhost:5173"
    if not FRONTEND_DIST.exists():
        raise SystemExit(
            "Frontend do ToDoX não compilado. Execute `npm run build` em new/frontend."
        )
    return str(FRONTEND_DIST)


def main() -> None:
    DesktopApp(
        frontend_url(),
        TASKS_FILE,
        SETTINGS_FILE,
        WINDOW_ICON_FILE,
        TRAY_ICON_FILE,
        debug="--dev" in sys.argv,
    ).run()


if __name__ == "__main__":
    main()
