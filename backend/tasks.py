from __future__ import annotations

import json
import re
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .errors import AppError


PRIORITY_ORDER = {
    "urgent": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "very_low": 4,
}
LEGACY_PRIORITIES = {
    "Urgente": "urgent",
    "Alta": "high",
    "Média": "medium",
    "Baixa": "low",
    "Muito baixa": "very_low",
}
TAG_PATTERN = re.compile(r"#([\w-]+)", re.UNICODE)
HEX_COLOR_PATTERN = re.compile(r"#[0-9A-Fa-f]{6}")
LEGACY_TAG_COLORS = (
    "#3B245C",
    "#193B59",
    "#12433A",
    "#4A3512",
    "#54291D",
    "#51232F",
    "#263E5A",
    "#183F4A",
)


def _validate_priority(value: Any) -> str:
    if not isinstance(value, str) or value not in PRIORITY_ORDER:
        raise AppError("INVALID_PRIORITY")
    return value


def _save_tasks(path: Path, tasks: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(tasks, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def _load_all_tasks(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("O arquivo de tarefas não contém um JSON válido.") from error
    if not isinstance(data, list):
        raise ValueError("A raiz do arquivo de tarefas deve ser uma lista.")

    migration_base = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
    known_colors: dict[str, str] = {}
    used_ids: set[str] = set()
    normalized_tasks: list[dict[str, Any]] = []
    changed = False
    for index, raw_task in enumerate(data, start=1):
        if not isinstance(raw_task, dict):
            raise ValueError(f"A tarefa {index} não é um objeto.")

        task_id = raw_task.get("id")
        if task_id is None:
            task_id = str(uuid.uuid4())
            changed = True
        elif not isinstance(task_id, str) or not task_id.strip():
            raise ValueError(f"A tarefa {index} não possui um id válido.")
        elif task_id in used_ids:
            task_id = str(uuid.uuid4())
            changed = True
        used_ids.add(task_id)

        raw_name = raw_task.get("nome")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ValueError(f"A tarefa {index} não possui um nome válido.")

        raw_priority = raw_task.get("prioridade")
        try:
            priority = _validate_priority(LEGACY_PRIORITIES.get(raw_priority, raw_priority))
        except ValueError as error:
            raise ValueError(
                f"A tarefa {index} possui uma prioridade inválida."
            ) from error
        if priority != raw_priority:
            changed = True

        added_at = raw_task.get("adicionada_em")
        if added_at is None:
            added_at = (
                migration_base + timedelta(microseconds=index - 1)
            ).isoformat(timespec="microseconds")
            changed = True
        else:
            added_at = _validate_datetime(added_at, index, "data de adição")

        raw_order = raw_task.get("ordem")
        if raw_order is None:
            order: int | None = None
            changed = True
        elif (
            isinstance(raw_order, bool)
            or not isinstance(raw_order, int)
            or raw_order < 0
        ):
            raise ValueError(f"A tarefa {index} possui uma ordem inválida.")
        else:
            order = raw_order

        accumulated = raw_task.get("tempo_acumulado_segundos")
        if accumulated is None:
            accumulated = 0
            changed = True
        elif isinstance(accumulated, bool) or not isinstance(accumulated, int) or accumulated < 0:
            raise ValueError(f"A tarefa {index} possui um tempo acumulado inválido.")

        if "cronometro_iniciado_em" not in raw_task:
            timer_started_at = None
            changed = True
        else:
            timer_started_at = _validate_optional_datetime(
                raw_task.get("cronometro_iniciado_em"), index, "início do cronômetro"
            )

        if "atividade_iniciada" not in raw_task:
            activity_started = timer_started_at is not None or accumulated > 0
            changed = True
        else:
            activity_started = raw_task.get("atividade_iniciada")
            if not isinstance(activity_started, bool):
                raise ValueError(
                    f"A tarefa {index} possui um estado de atividade inválido."
                )
            if (
                timer_started_at is not None or accumulated > 0
            ) and not activity_started:
                activity_started = True
                changed = True

        if "deletedAt" not in raw_task:
            deleted_at = None
            changed = True
        else:
            deleted_at = _validate_optional_datetime(
                raw_task.get("deletedAt"), index, "data de exclusão"
            )

        if "completedAt" not in raw_task:
            completed_at = None
            changed = True
        else:
            completed_at = _validate_optional_datetime(
                raw_task.get("completedAt"), index, "data de conclusão"
            )
        if completed_at is not None and deleted_at is None:
            deleted_at = completed_at
            changed = True

        name, tags_in_name = _split_name_and_tags(raw_name)
        if not name:
            raise ValueError(f"A tarefa {index} não possui um nome além das tags.")

        raw_tags = raw_task.get("tags")
        tags: list[str] = []
        if raw_tags is None:
            changed = True
        elif not isinstance(raw_tags, list):
            raise ValueError(f"A tarefa {index} não possui uma lista de tags válida.")
        else:
            for raw_tag in raw_tags:
                tag = _normalize_tag(raw_tag, index)
                if tag not in tags:
                    tags.append(tag)
                else:
                    changed = True
                if tag != raw_tag:
                    changed = True
        for tag in tags_in_name:
            if tag not in tags:
                tags.append(tag)
        if tags_in_name or name != raw_name.strip():
            changed = True

        raw_colors_value = raw_task.get("cores_tags")
        raw_colors: dict[str, str] = {}
        if raw_colors_value is None:
            changed = True
        elif not isinstance(raw_colors_value, dict):
            raise ValueError(f"A tarefa {index} possui cores de tags inválidas.")
        else:
            for raw_tag, color in raw_colors_value.items():
                tag = _normalize_tag(raw_tag, index)
                normalized_color = _normalize_stored_tag_color(color, index)
                if (
                    tag in raw_colors
                    or tag != raw_tag
                    or normalized_color != color
                ):
                    changed = True
                raw_colors[tag] = normalized_color

        colors: dict[str, str] = {}
        for tag in tags:
            if tag in known_colors:
                color = known_colors[tag]
            elif tag in raw_colors:
                color = raw_colors[tag]
                known_colors[tag] = color
            else:
                color = _random_tag_color()
                known_colors[tag] = color
            colors[tag] = color
        if colors != raw_colors:
            changed = True

        checklist = _validate_checklist(raw_task.get("checklist", []))
        task = {
            "id": task_id,
            "nome": name,
            "prioridade": priority,
            "adicionada_em": added_at,
            "ordem": order,
            "tags": tags,
            "cores_tags": colors,
            "tempo_acumulado_segundos": accumulated,
            "cronometro_iniciado_em": timer_started_at,
            "atividade_iniciada": activity_started,
            "deletedAt": deleted_at,
            "completedAt": completed_at,
            "checklist": checklist,
        }
        if deleted_at is not None and timer_started_at is not None:
            _finish_running_timer(task, datetime.fromisoformat(deleted_at))
            changed = True
        if task != raw_task:
            changed = True
        normalized_tasks.append(task)

    for priority in PRIORITY_ORDER:
        priority_tasks = [
            task
            for task in normalized_tasks
            if task["prioridade"] == priority
        ]
        missing_order = [task for task in priority_tasks if task["ordem"] is None]
        if not missing_order:
            continue

        next_order = max(
            (
                int(task["ordem"])
                for task in priority_tasks
                if task["ordem"] is not None
            ),
            default=-1,
        ) + 1
        for task in sorted(
            missing_order,
            key=lambda item: datetime.fromisoformat(str(item["adicionada_em"])),
        ):
            task["ordem"] = next_order
            next_order += 1

    if changed:
        _save_tasks(path, normalized_tasks)
    return normalized_tasks


def _validate_datetime(value: Any, index: int, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"A tarefa {index} possui {field} inválida.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"A tarefa {index} possui {field} inválida.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"A {field} da tarefa {index} não possui fuso horário.")
    return value


def _validate_optional_datetime(value: Any, index: int, field: str) -> str | None:
    if value is None:
        return None
    return _validate_datetime(value, index, field)


def _normalize_tag(value: Any, index: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"A tarefa {index} possui uma tag inválida.")
    tag = value.removeprefix("#").casefold()
    if not tag or TAG_PATTERN.fullmatch(f"#{tag}") is None:
        raise ValueError(f"A tarefa {index} possui uma tag inválida.")
    return tag


def _split_name_and_tags(value: str) -> tuple[str, list[str]]:
    name_parts: list[str] = []
    tags: list[str] = []
    for part in value.split():
        match = TAG_PATTERN.fullmatch(part)
        if match is None:
            name_parts.append(part)
            continue

        tag = match.group(1).casefold()
        if tag not in tags:
            tags.append(tag)
    return " ".join(name_parts), tags


def _parse_tags(value: str) -> list[str]:
    if not value.strip():
        return []

    tags: list[str] = []
    for part in value.split():
        match = TAG_PATTERN.fullmatch(part)
        if match is None:
            raise AppError("INVALID_TAG_FORMAT")
        tag = match.group(1).casefold()
        if TAG_PATTERN.fullmatch(f"#{tag}") is None:
            raise AppError("INVALID_TAG_FORMAT")
        if tag not in tags:
            tags.append(tag)
    return tags


def _normalize_stored_tag_color(value: Any, index: int) -> str:
    """Valida a cor persistida e migra os índices usados pelo schema anterior."""
    if isinstance(value, bool):
        raise ValueError(f"A tarefa {index} possui uma cor de tag inválida.")
    if isinstance(value, int):
        if 0 <= value < len(LEGACY_TAG_COLORS):
            return LEGACY_TAG_COLORS[value]
        raise ValueError(f"A tarefa {index} possui uma cor de tag inválida.")
    if not isinstance(value, str) or HEX_COLOR_PATTERN.fullmatch(value) is None:
        raise ValueError(f"A tarefa {index} possui uma cor de tag inválida.")
    return value.upper()


def _random_tag_color() -> str:
    """Sorteia uma cor RGB completa para a primeira associação de uma tag."""
    return f"#{secrets.randbelow(1 << 24):06X}"


def _validate_tag_color_overrides(
    value: Any, tags: list[str]
) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise AppError("INVALID_TAG_COLORS")

    valid_tags = set(tags)
    overrides: dict[str, str] = {}
    for raw_tag, color in value.items():
        if not isinstance(raw_tag, str):
            raise AppError("INVALID_TAG_COLORS")
        tag = raw_tag.removeprefix("#").casefold()
        if not tag or TAG_PATTERN.fullmatch(f"#{tag}") is None:
            raise AppError("INVALID_TAG_COLORS")
        if tag not in valid_tags:
            raise AppError("INVALID_TAG_COLORS")
        if tag in overrides:
            raise AppError("INVALID_TAG_COLORS")
        if not isinstance(color, str) or HEX_COLOR_PATTERN.fullmatch(color) is None:
            raise AppError("INVALID_TAG_COLORS")
        overrides[tag] = color.upper()
    return overrides


def _find_task(tasks: list[dict[str, Any]], task_id: str) -> dict[str, Any]:
    for task in tasks:
        if task["id"] == task_id:
            return task
    raise AppError("TASK_NOT_FOUND")


def _finish_running_timer(task: dict[str, Any], now: datetime) -> None:
    started_at = task["cronometro_iniciado_em"]
    if started_at is None:
        return

    elapsed = max(0, int((now - datetime.fromisoformat(started_at)).total_seconds()))
    task["tempo_acumulado_segundos"] += elapsed
    task["cronometro_iniciado_em"] = None


def _active_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filtra e ordena tarefas que já passaram pelo carregador."""
    active_tasks = [
        task
        for task in tasks
        if task["deletedAt"] is None
    ]
    return sorted(
        active_tasks,
        key=lambda task: (
            PRIORITY_ORDER[task["prioridade"]],
            task["ordem"],
            datetime.fromisoformat(task["adicionada_em"]),
        ),
    )


def load_tasks(path: Path) -> list[dict[str, Any]]:
    """Carrega apenas as tarefas ativas usando o JSON atual do aplicativo."""
    return _active_tasks(_load_all_tasks(path))


def _completed_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks = [
        task
        for task in tasks
        if task["completedAt"] is not None
    ]
    return sorted(
        tasks,
        key=lambda task: datetime.fromisoformat(task["completedAt"]),
        reverse=True,
    )


def load_completed_tasks(path: Path) -> list[dict[str, Any]]:
    return _completed_tasks(_load_all_tasks(path))


def load_task_state(path: Path) -> dict[str, list[dict[str, Any]]]:
    tasks = _load_all_tasks(path)
    return {
        "tasks": _active_tasks(tasks),
        "completed_tasks": _completed_tasks(tasks),
    }


def _known_tag_colors(tasks: list[dict[str, Any]]) -> dict[str, str]:
    return {
        tag: color
        for task in tasks
        for tag, color in task["cores_tags"].items()
    }


def create_task(path: Path, raw_name: str, priority: str) -> list[dict[str, Any]]:
    priority = _validate_priority(priority)
    if not isinstance(raw_name, str):
        raise AppError("TASK_NAME_INVALID")

    name, tags = _split_name_and_tags(raw_name)
    if not name:
        raise AppError("TASK_NAME_REQUIRED")
    if len(name) > 120:
        raise AppError("TASK_NAME_TOO_LONG")
    if any(TAG_PATTERN.fullmatch(f"#{tag}") is None for tag in tags):
        raise AppError("INVALID_TAG_FORMAT")

    tasks = _load_all_tasks(path)
    next_order = max(
        (
            task["ordem"]
            for task in tasks
            if task["prioridade"] == priority
        ),
        default=-1,
    ) + 1
    known_colors = _known_tag_colors(tasks)

    tag_colors: dict[str, str] = {}
    for tag in tags:
        if tag in known_colors:
            tag_colors[tag] = known_colors[tag]
        else:
            tag_colors[tag] = _random_tag_color()

    tasks.append(
        {
            "id": str(uuid.uuid4()),
            "nome": name,
            "prioridade": priority,
            "adicionada_em": datetime.now().astimezone().isoformat(timespec="microseconds"),
            "ordem": next_order,
            "tags": tags,
            "cores_tags": tag_colors,
            "tempo_acumulado_segundos": 0,
            "cronometro_iniciado_em": None,
            "atividade_iniciada": False,
            "deletedAt": None,
            "completedAt": None,
            "checklist": [],
        }
    )
    _save_tasks(path, tasks)
    return _active_tasks(tasks)


def _checklist_name(value: Any) -> str:
    if not isinstance(value, str):
        raise AppError("CHECKLIST_NAME_INVALID")
    name = re.sub(r"[\r\n]+", " ", value).strip()
    if not name:
        raise AppError("CHECKLIST_NAME_REQUIRED")
    if len(name) > 120:
        raise AppError("CHECKLIST_NAME_TOO_LONG")
    return name


def _validate_checklist(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise AppError("CHECKLIST_INVALID")
    ids: set[str] = set()
    result = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"id", "nome", "concluido"}:
            raise AppError("CHECKLIST_INVALID")
        item_id = item["id"]
        if not isinstance(item_id, str) or not item_id.strip() or item_id in ids:
            raise AppError("CHECKLIST_INVALID")
        if type(item["concluido"]) is not bool:
            raise AppError("CHECKLIST_INVALID")
        name = _checklist_name(item["nome"])
        if name != item["nome"]:
            raise AppError("CHECKLIST_INVALID")
        ids.add(item_id)
        result.append(dict(item))
    return result


def _checklist_task(tasks: list[dict[str, Any]], task_id: str) -> dict[str, Any]:
    task = _find_task(tasks, task_id)
    if task["deletedAt"] is not None or task["completedAt"] is not None:
        raise AppError("COMPLETED_TASK_READ_ONLY")
    return task


def _checklist_item(task: dict[str, Any], item_id: str) -> dict[str, Any]:
    for item in task["checklist"]:
        if item["id"] == item_id:
            return item
    raise AppError("CHECKLIST_ITEM_NOT_FOUND")


def add_checklist_item(path: Path, task_id: str, name: str) -> list[dict[str, Any]]:
    name = _checklist_name(name)
    tasks = _load_all_tasks(path)
    task = _checklist_task(tasks, task_id)
    task["checklist"].append({"id": str(uuid.uuid4()), "nome": name, "concluido": False})
    _save_tasks(path, tasks)
    return _active_tasks(tasks)


def update_checklist_item(path: Path, task_id: str, item_id: str, name: str) -> list[dict[str, Any]]:
    name = _checklist_name(name)
    tasks = _load_all_tasks(path)
    _checklist_item(_checklist_task(tasks, task_id), item_id)["nome"] = name
    _save_tasks(path, tasks)
    return _active_tasks(tasks)


def set_checklist_item_completed(path: Path, task_id: str, item_id: str, completed: bool) -> list[dict[str, Any]]:
    if type(completed) is not bool:
        raise AppError("CHECKLIST_INVALID")
    tasks = _load_all_tasks(path)
    task = _checklist_task(tasks, task_id)
    item = _checklist_item(task, item_id)
    first_completion = completed and not any(step["concluido"] for step in task["checklist"])
    item["concluido"] = completed
    if first_completion and task["cronometro_iniciado_em"] is None:
        task["cronometro_iniciado_em"] = datetime.now().astimezone().isoformat(timespec="microseconds")
        task["atividade_iniciada"] = True
    _save_tasks(path, tasks)
    return _active_tasks(tasks)


def delete_checklist_item(path: Path, task_id: str, item_id: str) -> list[dict[str, Any]]:
    tasks = _load_all_tasks(path)
    task = _checklist_task(tasks, task_id)
    item = _checklist_item(task, item_id)
    task["checklist"].remove(item)
    _save_tasks(path, tasks)
    return _active_tasks(tasks)


def update_task_name(
    path: Path, task_id: str, raw_name: str
) -> list[dict[str, Any]]:
    if not isinstance(raw_name, str):
        raise AppError("TASK_NAME_INVALID")

    name = raw_name.strip()
    if not name:
        raise AppError("TASK_NAME_REQUIRED")
    if len(name) > 120:
        raise AppError("TASK_NAME_TOO_LONG")
    normalized_name, tags = _split_name_and_tags(name)
    if tags:
        raise AppError("EDIT_TAGS_SEPARATELY")

    tasks = _load_all_tasks(path)
    task = _find_task(tasks, task_id)
    if task["completedAt"] is not None:
        raise AppError("COMPLETED_TASK_READ_ONLY")

    task["nome"] = normalized_name
    _save_tasks(path, tasks)
    return _active_tasks(tasks)


def update_task_priority(
    path: Path, task_id: str, priority: str
) -> list[dict[str, Any]]:
    priority = _validate_priority(priority)

    tasks = _load_all_tasks(path)
    task = _find_task(tasks, task_id)
    if task["prioridade"] != priority:
        task["prioridade"] = priority
        task["ordem"] = max(
            (
                item["ordem"]
                for item in tasks
                if item is not task and item["prioridade"] == priority
            ),
            default=-1,
        ) + 1
    _save_tasks(path, tasks)
    return _active_tasks(tasks)


def reorder_tasks(path: Path, ordered_task_ids: list[str]) -> list[dict[str, Any]]:
    if not isinstance(ordered_task_ids, list) or not ordered_task_ids:
        raise AppError("TASK_ORDER_REQUIRED")
    if any(
        not isinstance(task_id, str) or not task_id.strip()
        for task_id in ordered_task_ids
    ):
        raise AppError("TASK_ORDER_INVALID_ID")
    if len(set(ordered_task_ids)) != len(ordered_task_ids):
        raise AppError("TASK_ORDER_DUPLICATE")

    tasks = _load_all_tasks(path)
    ordered_tasks = [_find_task(tasks, task_id) for task_id in ordered_task_ids]
    if any(task["deletedAt"] is not None for task in ordered_tasks):
        raise AppError("ONLY_ACTIVE_TASKS_REORDERABLE")

    priorities = {task["prioridade"] for task in ordered_tasks}
    if len(priorities) != 1:
        raise AppError("REORDER_SAME_PRIORITY_ONLY")

    priority = priorities.pop()
    active_priority_ids = {
        task["id"]
        for task in tasks
        if task["deletedAt"] is None and task["prioridade"] == priority
    }
    if set(ordered_task_ids) != active_priority_ids:
        raise AppError("REORDER_ALL_PRIORITY_TASKS_REQUIRED")

    for order, task in enumerate(ordered_tasks):
        task["ordem"] = order

    _save_tasks(path, tasks)
    return _active_tasks(tasks)


def delete_task(path: Path, task_id: str) -> list[dict[str, Any]]:
    tasks = _load_all_tasks(path)
    task = _find_task(tasks, task_id)
    now = datetime.now().astimezone()
    _finish_running_timer(task, now)
    task["deletedAt"] = now.isoformat(timespec="microseconds")
    task["completedAt"] = None
    _save_tasks(path, tasks)
    return _active_tasks(tasks)


def complete_task(path: Path, task_id: str) -> list[dict[str, Any]]:
    tasks = _load_all_tasks(path)
    task = _find_task(tasks, task_id)
    now = datetime.now().astimezone()
    _finish_running_timer(task, now)
    timestamp = now.isoformat(timespec="microseconds")
    task["deletedAt"] = timestamp
    task["completedAt"] = timestamp
    _save_tasks(path, tasks)
    return _active_tasks(tasks)


def toggle_task_timer(path: Path, task_id: str) -> list[dict[str, Any]]:
    tasks = _load_all_tasks(path)
    task = _find_task(tasks, task_id)
    now = datetime.now().astimezone()

    if task["cronometro_iniciado_em"] is None:
        task["cronometro_iniciado_em"] = now.isoformat(timespec="microseconds")
        task["atividade_iniciada"] = True
    else:
        _finish_running_timer(task, now)

    _save_tasks(path, tasks)
    if task["deletedAt"] is not None:
        # Inactive IDs remain supported; their timer is consolidated at the
        # deletion timestamp by the loader before returning to the caller.
        return load_tasks(path)
    return _active_tasks(tasks)


def update_task_tags(
    path: Path,
    task_id: str,
    raw_tags: str,
    color_overrides: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    tasks = _load_all_tasks(path)
    task = _find_task(tasks, task_id)
    if task["completedAt"] is not None:
        raise AppError("COMPLETED_TASK_READ_ONLY")

    new_tags = _parse_tags(raw_tags)
    validated_overrides = _validate_tag_color_overrides(
        color_overrides, new_tags
    )
    previous_tags = task["tags"]
    previous_colors = task["cores_tags"]
    known_colors = _known_tag_colors(tasks)

    new_colors: dict[str, str] = {}
    for index, tag in enumerate(new_tags):
        if tag in previous_colors:
            new_colors[tag] = previous_colors[tag]
        elif tag in known_colors:
            new_colors[tag] = known_colors[tag]
        elif index < len(previous_tags) and previous_tags[index] not in new_tags:
            previous_tag = previous_tags[index]
            new_colors[tag] = previous_colors[previous_tag]
        else:
            new_colors[tag] = _random_tag_color()

    new_colors.update(validated_overrides)

    task["tags"] = new_tags
    task["cores_tags"] = new_colors
    for item in tasks:
        item_tags = item["tags"]
        item_colors = item["cores_tags"]
        for tag, color in new_colors.items():
            if tag in item_tags:
                item_colors[tag] = color
    _save_tasks(path, tasks)
    return _active_tasks(tasks)
