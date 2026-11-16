from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


APP_DATA_FOLDER = "ToDoX"
DATA_FILES = ("tarefas.json", "configuracoes.json")


def migrate_legacy_data(legacy_directory: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for filename in DATA_FILES:
        source = legacy_directory / filename
        target = destination / filename
        if source.is_file() and not target.exists():
            shutil.copy2(source, target)


def application_data_directory(source_directory: Path) -> Path:
    if not getattr(sys, "frozen", False):
        return source_directory.parent

    local_app_data = os.environ.get("LOCALAPPDATA")
    base_directory = (
        Path(local_app_data)
        if local_app_data
        else Path.home() / "AppData" / "Local"
    )
    destination = base_directory / APP_DATA_FOLDER
    migrate_legacy_data(Path(sys.executable).resolve().parent, destination)
    return destination
