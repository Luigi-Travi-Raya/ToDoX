from __future__ import annotations

import ctypes
import json
import threading
from ctypes import wintypes
from pathlib import Path
from typing import Any, Callable

import pystray
import webview
from PIL import Image
from pynput import keyboard

from .api import AppApi
from .settings import (
    DEFAULT_SETTINGS,
    HotkeySettings,
    hotkey_code,
    hotkey_description,
    hotkey_from_settings,
    load_settings,
    save_settings,
    validate_settings,
)


TRAY_MENU_WIDTH = 340
TRAY_MENU_MIN_HEIGHT = 250
TRAY_MENU_MAX_HEIGHT = 460
TRAY_MENU_BASE_HEIGHT = 225
TRAY_MENU_ACTIVITY_HEIGHT = 66
TRAY_MENU_MARGIN = 8

NATIVE_STRINGS = {
    "en": {
        "quick_add_title": "ToDoX — New task",
        "background_notification": (
            "The app is still running. Use {shortcut} to add a task."
        ),
    },
    "ja": {
        "quick_add_title": "ToDoX — 新しいタスク",
        "background_notification": (
            "アプリは引き続き実行中です。{shortcut} でタスクを追加できます。"
        ),
    },
    "de": {
        "quick_add_title": "ToDoX — Neue Aufgabe",
        "background_notification": (
            "Die App läuft weiter. Mit {shortcut} können Sie eine Aufgabe hinzufügen."
        ),
    },
    "pt-BR": {
        "quick_add_title": "ToDoX — Nova tarefa",
        "background_notification": (
            "O aplicativo continua ativo. Use {shortcut} para adicionar uma tarefa."
        ),
    },
    "es": {
        "quick_add_title": "ToDoX — Nueva tarea",
        "background_notification": (
            "La aplicación sigue activa. Usa {shortcut} para añadir una tarea."
        ),
    },
}

WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205


class _Point(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class _Rect(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class _MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", _Rect),
        ("rcWork", _Rect),
        ("dwFlags", wintypes.DWORD),
    ]


class _ActionTrayIcon(pystray.Icon):
    """pystray icon that exposes both Windows mouse buttons as callbacks.

    pystray's Windows backend only opens a native menu on right click and does
    not expose that click through its public API. Keeping this small adapter in
    one place lets the rest of the application use a styled pywebview window.
    """

    def __init__(
        self,
        *args: Any,
        on_left_click: Callable[[], None],
        on_right_click: Callable[[], None],
        **kwargs: Any,
    ) -> None:
        self._on_left_click = on_left_click
        self._on_right_click = on_right_click
        super().__init__(*args, **kwargs)

    def _on_notify(self, wparam: int, lparam: int) -> None:
        if lparam == WM_LBUTTONUP:
            self._invoke_click(self._on_left_click)
            return
        if lparam == WM_RBUTTONUP:
            self._invoke_click(self._on_right_click)
            return
        super()._on_notify(wparam, lparam)

    def _invoke_click(self, callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception:
            self._log.exception("Tray click callback failed")


class DesktopApp:
    def __init__(
        self,
        frontend_url: str,
        tasks_path: Path,
        settings_path: Path,
        window_icon_path: Path,
        tray_icon_path: Path,
        debug: bool = False,
    ) -> None:
        self.frontend_url = frontend_url
        self.tasks_path = tasks_path
        self.settings_path = settings_path
        self.window_icon_path = window_icon_path
        self.tray_icon_path = tray_icon_path
        self.debug = debug
        self.main_window: Any = None
        self.quick_window: Any = None
        self.tray_window: Any = None
        self.hotkey_listener: Any = None
        self.tray_icon: Any = None
        self.tray_menu_open = False
        self._main_window_loaded = False
        self._tray_window_creating = False
        self._tray_window_ready = False
        self._tray_open_pending = False
        self._window_lock = threading.RLock()
        self._tray_anchor: tuple[int, int] | None = None
        self._tray_work_area: tuple[int, int, int, int] | None = None
        self._tray_deactivate_handler: Any = None
        self._tray_window_height: int | None = None
        self._notification_lock = threading.Lock()
        self._notification_thread: threading.Thread | None = None
        self._pending_tasks_update: dict[str, Any] | None = None
        self._pending_main_refresh = False
        self.exiting = False
        self.first_hide = True
        self.settings_open = False
        self.startup_warnings: list[dict[str, str]] = []

        try:
            loaded_settings = load_settings(settings_path)
            self.hotkey_settings = hotkey_from_settings(loaded_settings)
            self.theme = loaded_settings["tema"]
            self.locale = loaded_settings["locale"]
        except (OSError, ValueError) as error:
            self.hotkey_settings = hotkey_from_settings(DEFAULT_SETTINGS)
            self.theme = DEFAULT_SETTINGS["tema"]
            self.locale = DEFAULT_SETTINGS["locale"]
            self.startup_warnings.append(
                {"code": "SETTINGS_INVALID", "details": str(error)}
            )

        self.api = AppApi(tasks_path, self)

    def run(self) -> None:
        self.main_window = webview.create_window(
            "ToDoX",
            self.frontend_url,
            js_api=self.api,
            width=760,
            height=520,
            min_size=(760, 520),
            background_color="#090e1a",
        )
        self.main_window.events.closing += self._on_main_closing
        self.main_window.events.loaded += self._on_main_loaded
        self._start_integrations()
        window_icon = None
        if self.window_icon_path.is_file():
            window_icon = str(self.window_icon_path)
        else:
            self.startup_warnings.append(
                {
                    "code": "WINDOW_ICON_MISSING",
                    "details": str(self.window_icon_path),
                }
            )
        webview.start(debug=self.debug, icon=window_icon)
        self._stop_integrations()

    def get_settings(self) -> dict[str, Any]:
        return {
            **self.hotkey_settings,
            "tema": self.theme,
            "locale": self.locale,
            "description": hotkey_description(self.hotkey_settings),
        }

    def apply_settings(self, value: Any) -> dict[str, Any]:
        new_settings = validate_settings(value)
        new_hotkey = hotkey_from_settings(new_settings)
        new_listener = self._new_hotkey_listener(new_hotkey)
        new_listener.start()
        try:
            save_settings(self.settings_path, new_settings)
        except OSError:
            new_listener.stop()
            raise

        previous = self.hotkey_listener
        self.hotkey_listener = new_listener
        self.hotkey_settings = new_hotkey
        self.theme = new_settings["tema"]
        self.locale = new_settings["locale"]
        if previous is not None:
            previous.stop()
        if self.tray_menu_open:
            self._dispatch_window_event(self.tray_window, "tray-menu-shown")
        return self.get_settings()

    def get_startup_warnings(self) -> list[dict[str, str]]:
        return [warning.copy() for warning in self.startup_warnings]

    def set_settings_open(self, is_open: bool) -> None:
        self.settings_open = bool(is_open)

    def show_main_window(self) -> None:
        self.close_tray_menu()
        if self.main_window is None:
            return
        self.main_window.show()
        self.main_window.restore()
        self._focus_window(self.main_window)
        with self._notification_lock:
            self._pending_main_refresh = True
            self._start_notification_worker()

    def hide_main_window(self) -> None:
        self.close_tray_menu()
        if self.main_window is None:
            return
        self.close_quick_window()
        if self.tray_icon is None:
            self.main_window.minimize()
            return
        self.main_window.hide()
        if self.first_hide and self.tray_icon is not None:
            self.first_hide = False
            try:
                self.tray_icon.notify(
                    self._native_text(
                        "background_notification",
                        shortcut=hotkey_description(self.hotkey_settings),
                    ),
                    "ToDoX",
                )
            except (NotImplementedError, OSError):
                pass

    def open_quick_add(self) -> None:
        if self.exiting:
            return
        self.close_tray_menu()
        if self.quick_window is not None:
            self.quick_window.show()
            self.quick_window.restore()
            self._focus_window(self.quick_window)
            return

        self.quick_window = webview.create_window(
            self._native_text("quick_add_title"),
            f"{self.frontend_url}#quick-add",
            js_api=self.api,
            width=430,
            height=290,
            min_size=(430, 290),
            resizable=False,
            on_top=True,
            background_color="#090e1a",
        )
        self.quick_window.events.closed += self._on_quick_closed

    def close_quick_window(self) -> None:
        window = self.quick_window
        self.quick_window = None
        if window is not None:
            window.destroy()

    def open_tray_menu(self) -> None:
        with self._window_lock:
            if self.exiting:
                return
            if self.tray_menu_open or self._tray_open_pending:
                should_close = True
                window_ready = False
                main_loaded = False
            else:
                should_close = False
                self._tray_open_pending = True
                window_ready = self._tray_window_ready
                main_loaded = self._main_window_loaded

        if should_close:
            self.close_tray_menu()
            return

        if window_ready:
            self._show_tray_menu()
        elif main_loaded:
            self._ensure_tray_window()

    def _ensure_tray_window(self) -> None:
        with self._window_lock:
            if (
                self.exiting
                or not self._main_window_loaded
                or not self._tray_open_pending
                or self.tray_window is not None
                or self._tray_window_creating
            ):
                return
            self._tray_window_creating = True

        window: Any = None
        try:
            # pywebview's WinForms backend implements hidden windows by showing
            # and immediately hiding the form. That can cancel WebView2's
            # asynchronous controller initialization with E_ABORT. Create the
            # popover visibly but outside the desktop, then reveal it only after
            # the `loaded` event confirms that WebView2 is ready.
            window = webview.create_window(
                "ToDoX",
                f"{self.frontend_url}#tray-menu",
                js_api=self.api,
                width=TRAY_MENU_WIDTH,
                height=TRAY_MENU_MIN_HEIGHT,
                x=-32000,
                y=-32000,
                min_size=(TRAY_MENU_WIDTH, TRAY_MENU_MIN_HEIGHT),
                frameless=True,
                easy_drag=False,
                resizable=False,
                on_top=True,
                background_color=(
                    "#ffffff" if self.theme == "light" else "#101522"
                ),
            )
            if window is None:
                raise RuntimeError("pywebview nao criou a janela")

            with self._window_lock:
                if self.exiting:
                    self._tray_window_creating = False
                    window.destroy()
                    return
                self.tray_window = window
                self._tray_window_creating = False

            window.events.closing += self._on_tray_closing
            window.events.closed += self._on_tray_closed
            self._configure_tray_native_window()
            window.events.loaded += self._on_tray_loaded
            if window.events.loaded.is_set():
                self._on_tray_loaded()
        except Exception as error:
            with self._window_lock:
                if self.tray_window is window:
                    self.tray_window = None
                self._tray_window_creating = False
                self._tray_window_ready = False
                self._tray_open_pending = False
            if window is not None:
                try:
                    window.destroy()
                except Exception:
                    pass
            self.startup_warnings.append(
                {"code": "TRAY_MENU_CREATE_FAILED", "details": str(error)}
            )

    def _show_tray_menu(self) -> None:
        with self._window_lock:
            window = self.tray_window
            if (
                self.exiting
                or window is None
                or not self._tray_window_ready
                or not self._tray_open_pending
            ):
                return

        height = self._tray_menu_height()
        try:
            try:
                self._tray_anchor, self._tray_work_area = (
                    self._cursor_and_work_area()
                )
            except OSError:
                self._tray_anchor = None
                self._tray_work_area = None
            self._resize_and_position_tray_window(window, height)
            window.show()
            with self._window_lock:
                self.tray_menu_open = True
                self._tray_open_pending = False
            self._focus_window(window)
            self._dispatch_window_event(window, "tray-menu-shown")
        except Exception as error:
            with self._window_lock:
                self.tray_menu_open = False
                self._tray_open_pending = False
            self.startup_warnings.append(
                {"code": "TRAY_MENU_OPEN_FAILED", "details": str(error)}
            )

    def close_tray_menu(self) -> None:
        with self._window_lock:
            was_open = self.tray_menu_open
            self.tray_menu_open = False
            self._tray_open_pending = False
            self._tray_anchor = None
            self._tray_work_area = None
            window = self.tray_window
        if not was_open:
            return
        if window is not None:
            try:
                window.hide()
            except Exception:
                pass

    def notify_tasks_changed(self, update: dict[str, Any]) -> None:
        """Queue the latest saved task state without waiting for WebView2."""
        with self._notification_lock:
            pending = self._pending_tasks_update
            if pending is None or update["revision"] >= pending["revision"]:
                self._pending_tasks_update = update
            self._start_notification_worker()

    def _start_notification_worker(self) -> None:
        """Start at most one dispatcher; the caller holds the queue lock."""
        if self.exiting or self._notification_thread is not None:
            return
        self._notification_thread = threading.Thread(
            target=self._deliver_task_notifications,
            name="todox-task-notifications",
            daemon=True,
        )
        self._notification_thread.start()

    def _deliver_task_notifications(self) -> None:
        while True:
            with self._notification_lock:
                update = self._pending_tasks_update
                refresh_main = self._pending_main_refresh
                self._pending_tasks_update = None
                self._pending_main_refresh = False
                if self.exiting or (update is None and not refresh_main):
                    self._notification_thread = None
                    return

            # Never hold the queue or task lock while waiting for native UI work.
            if update is not None:
                window = self.tray_window
                if self.tray_menu_open and window is not None:
                    try:
                        height = self._tray_menu_height(update["tasks"])
                        if height != self._tray_window_height:
                            self._resize_and_position_tray_window(window, height)
                    except Exception:
                        pass
                if self._main_window_loaded:
                    self._dispatch_window_event(
                        self.main_window, "tasks-changed", update
                    )
                if self._tray_window_ready:
                    self._dispatch_window_event(
                        self.tray_window, "tasks-changed", update
                    )
            if refresh_main and self._main_window_loaded:
                self._dispatch_window_event(
                    self.main_window, "tasks-refresh-requested"
                )

    def request_exit(self) -> None:
        if self.exiting:
            return
        self.exiting = True
        self._stop_integrations()
        self.close_quick_window()
        with self._window_lock:
            tray_window = self.tray_window
            self.tray_window = None
            self.tray_menu_open = False
            self._tray_open_pending = False
            self._tray_window_ready = False
            self._tray_anchor = None
            self._tray_work_area = None
        if tray_window is not None:
            tray_window.destroy()
        if self.main_window is not None:
            self.main_window.destroy()

    def _on_main_closing(self) -> bool:
        if self.exiting:
            return True

        def notify_frontend() -> None:
            try:
                self.main_window.run_js(
                    "window.dispatchEvent(new Event('app-close-requested'))"
                )
            except Exception:
                pass

        threading.Thread(target=notify_frontend, daemon=True).start()
        return False

    def _on_main_loaded(self) -> None:
        with self._window_lock:
            self._main_window_loaded = True
            should_create = self._tray_open_pending
        if should_create:
            self._ensure_tray_window()

    def _on_quick_closed(self) -> None:
        self.quick_window = None

    def _on_tray_closing(self) -> bool:
        if self.exiting:
            return True
        self.close_tray_menu()
        return False

    def _on_tray_closed(self) -> None:
        with self._window_lock:
            self.tray_window = None
            self.tray_menu_open = False
            self._tray_window_creating = False
            self._tray_window_ready = False
            self._tray_open_pending = False
            self._tray_deactivate_handler = None
            self._tray_window_height = None

    def _on_tray_loaded(self) -> None:
        with self._window_lock:
            if self._tray_window_ready:
                return
            self._tray_window_ready = True
            should_open = self._tray_open_pending and not self.exiting
            window = self.tray_window
        if should_open:
            self._show_tray_menu()
        elif window is not None:
            try:
                window.hide()
            except Exception:
                pass

    def _configure_tray_native_window(self) -> None:
        """Hide the popover when its native Windows form loses focus."""
        window = self.tray_window
        if window is None or self._tray_deactivate_handler is not None:
            return

        try:
            handler = self._on_tray_deactivated

            def configure() -> None:
                native = window.native
                try:
                    self._hide_native_window_from_taskbar(native)
                except (OSError, RuntimeError):
                    pass
                native.Deactivate += handler

            self._invoke_on_window_thread(window, configure)
            # Keep the Python delegate alive for as long as the native form.
            self._tray_deactivate_handler = handler
        except Exception:
            # The native form may be disposed while this callback is waiting
            # for its UI thread. A later popover can attach its own handler.
            self._tray_deactivate_handler = None

    def _on_tray_deactivated(self, *_args: Any) -> None:
        self.close_tray_menu()

    def _tray_menu_height(self, tasks: list[dict[str, Any]] | None = None) -> int:
        if tasks is None:
            try:
                tasks = self.api.list_tasks()
            except (OSError, TypeError, ValueError):
                tasks = []
        activity_count = sum(task["atividade_iniciada"] for task in tasks)
        return min(
            TRAY_MENU_MAX_HEIGHT,
            max(
                TRAY_MENU_MIN_HEIGHT,
                TRAY_MENU_BASE_HEIGHT
                + TRAY_MENU_ACTIVITY_HEIGHT * activity_count,
            ),
        )

    def _resize_and_position_tray_window(
        self, window: Any, height: int
    ) -> None:
        def update() -> None:
            if window is not self.tray_window or self.exiting:
                return
            if height != self._tray_window_height:
                window.resize(TRAY_MENU_WIDTH, height)
                self._tray_window_height = height
            self._position_tray_window(window, TRAY_MENU_WIDTH, height)

        self._invoke_on_window_thread(window, update)

    @staticmethod
    def _invoke_on_window_thread(window: Any, callback: Callable[[], None]) -> None:
        """Run native WinForms work in the thread that owns the form."""
        native = window.native
        if native.InvokeRequired:
            # System is available after pywebview initializes its WinForms
            # backend. Func[Type] matches the delegate used by pywebview itself.
            from System import Func, Type

            native.Invoke(Func[Type](callback))
            return
        callback()

    @staticmethod
    def _hide_native_window_from_taskbar(native: Any) -> None:
        """Apply the Win32 tool-window style without recreating WebView2 handles."""
        handle = native.Handle.ToInt64()
        user32 = ctypes.windll.user32
        get_style = user32.GetWindowLongPtrW
        set_style = user32.SetWindowLongPtrW
        get_style.argtypes = [wintypes.HWND, ctypes.c_int]
        get_style.restype = ctypes.c_ssize_t
        set_style.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        set_style.restype = ctypes.c_ssize_t

        extended_style = int(get_style(handle, -20))
        extended_style = (extended_style | 0x00000080) & ~0x00040000
        set_style(handle, -20, extended_style)

        set_window_position = user32.SetWindowPos
        set_window_position.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        set_window_position.restype = wintypes.BOOL
        set_window_position(
            handle,
            None,
            0,
            0,
            0,
            0,
            0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020,
        )

    @staticmethod
    def _calculate_tray_position(
        anchor: tuple[int, int],
        work_area: tuple[int, int, int, int],
        size: tuple[int, int],
    ) -> tuple[int, int]:
        anchor_x, anchor_y = anchor
        work_left, work_top, work_right, work_bottom = work_area
        width, height = size

        minimum_x = work_left + TRAY_MENU_MARGIN
        maximum_x = max(minimum_x, work_right - width - TRAY_MENU_MARGIN)
        x = min(maximum_x, max(minimum_x, anchor_x - width))

        above = anchor_y - height - TRAY_MENU_MARGIN
        below = anchor_y + TRAY_MENU_MARGIN
        y = above if above >= work_top + TRAY_MENU_MARGIN else below
        minimum_y = work_top + TRAY_MENU_MARGIN
        maximum_y = max(minimum_y, work_bottom - height - TRAY_MENU_MARGIN)
        y = min(maximum_y, max(minimum_y, y))
        return x, y

    def _position_tray_window(
        self, window: Any, fallback_width: int, fallback_height: int
    ) -> None:
        try:
            if self._tray_anchor is None or self._tray_work_area is None:
                anchor, work_area = self._cursor_and_work_area()
            else:
                anchor, work_area = self._tray_anchor, self._tray_work_area
            native = window.native
            width = native.Width
            height = native.Height
            x, y = self._calculate_tray_position(
                anchor, work_area, (width, height)
            )
            handle = native.Handle.ToInt32()
            user32 = ctypes.windll.user32
            set_window_position = user32.SetWindowPos
            set_window_position.argtypes = [
                wintypes.HWND,
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.UINT,
            ]
            set_window_position.restype = wintypes.BOOL
            # Coordinates from GetCursorPos/GetMonitorInfo are physical pixels;
            # SetWindowPos avoids a second DPI conversion by pywebview.
            if not set_window_position(
                handle,
                None,
                x,
                y,
                0,
                0,
                0x0001 | 0x0004 | 0x0010,
            ):
                raise ctypes.WinError()
        except (OSError, RuntimeError):
            # A failed Win32 positioning call can still use pywebview's
            # positioning as a best-effort fallback.
            anchor = self._tray_anchor
            if anchor is None:
                try:
                    anchor = self._cursor_position()
                except OSError:
                    anchor = (fallback_width, fallback_height)
            window.move(
                max(0, anchor[0] - fallback_width),
                max(0, anchor[1] - fallback_height - TRAY_MENU_MARGIN),
            )

    @staticmethod
    def _cursor_position() -> tuple[int, int]:
        point = _Point()
        get_cursor_position = ctypes.windll.user32.GetCursorPos
        get_cursor_position.argtypes = [ctypes.POINTER(_Point)]
        get_cursor_position.restype = wintypes.BOOL
        if not get_cursor_position(ctypes.byref(point)):
            raise ctypes.WinError()
        return int(point.x), int(point.y)

    @classmethod
    def _cursor_and_work_area(
        cls,
    ) -> tuple[tuple[int, int], tuple[int, int, int, int]]:
        anchor = cls._cursor_position()
        point = _Point(*anchor)
        user32 = ctypes.windll.user32
        monitor_from_point = user32.MonitorFromPoint
        monitor_from_point.argtypes = [_Point, wintypes.DWORD]
        monitor_from_point.restype = wintypes.HANDLE
        monitor = monitor_from_point(point, 2)
        if not monitor:
            raise ctypes.WinError()

        info = _MonitorInfo()
        info.cbSize = ctypes.sizeof(_MonitorInfo)
        get_monitor_info = user32.GetMonitorInfoW
        get_monitor_info.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_MonitorInfo),
        ]
        get_monitor_info.restype = wintypes.BOOL
        if not get_monitor_info(monitor, ctypes.byref(info)):
            raise ctypes.WinError()
        work = info.rcWork
        return anchor, (
            int(work.left),
            int(work.top),
            int(work.right),
            int(work.bottom),
        )

    @staticmethod
    def _dispatch_window_event(
        window: Any, event_name: str, detail: dict[str, Any] | None = None
    ) -> None:
        if window is None:
            return
        try:
            if detail is None:
                script = f"window.dispatchEvent(new Event('{event_name}'))"
            else:
                script = (
                    f"window.dispatchEvent(new CustomEvent({json.dumps(event_name)},"
                    f"{{detail:{json.dumps(detail, separators=(',', ':'))}}}))"
                )
            window.run_js(script)
        except Exception:
            pass

    def _new_hotkey_listener(
        self, settings: HotkeySettings
    ) -> keyboard.GlobalHotKeys:
        return keyboard.GlobalHotKeys(
            {hotkey_code(settings): self._on_hotkey}
        )

    def _on_hotkey(self) -> None:
        if not self.settings_open:
            self.open_quick_add()

    @staticmethod
    def _focus_window(window: Any) -> None:
        try:
            def activate() -> None:
                window.native.Activate()

            DesktopApp._invoke_on_window_thread(window, activate)
        except Exception:
            pass

    def _start_integrations(self) -> None:
        try:
            self.hotkey_listener = self._new_hotkey_listener(self.hotkey_settings)
            self.hotkey_listener.start()
        except Exception as error:
            self.hotkey_listener = None
            self.startup_warnings.append(
                {"code": "GLOBAL_HOTKEY_UNAVAILABLE", "details": str(error)}
            )

        try:
            self.tray_icon = _ActionTrayIcon(
                "todox",
                self._create_tray_icon(),
                "ToDoX",
                on_left_click=self.show_main_window,
                on_right_click=self.open_tray_menu,
            )
            self.tray_icon.run_detached()
        except Exception as error:
            self.tray_icon = None
            self.startup_warnings.append(
                {"code": "TRAY_UNAVAILABLE", "details": str(error)}
            )

    def _native_text(self, key: str, **values: str) -> str:
        strings = NATIVE_STRINGS.get(self.locale, NATIVE_STRINGS["en"])
        template = strings.get(key, NATIVE_STRINGS["en"][key])
        return template.format(**values)

    def _stop_integrations(self) -> None:
        listener = self.hotkey_listener
        self.hotkey_listener = None
        if listener is not None:
            listener.stop()

        tray = self.tray_icon
        self.tray_icon = None
        if tray is not None:
            tray.stop()

    def _create_tray_icon(self) -> Image.Image:
        with Image.open(self.tray_icon_path) as image:
            return image.convert("RGBA")
