import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from PIL import Image

from backend.desktop import (
    TRAY_MENU_MAX_HEIGHT,
    TRAY_MENU_MIN_HEIGHT,
    TRAY_MENU_WIDTH,
    WM_LBUTTONUP,
    WM_RBUTTONUP,
    DesktopApp,
    _ActionTrayIcon,
)


class DesktopAppTest(unittest.TestCase):
    def make_app(self, directory: str) -> DesktopApp:
        root = Path(directory)
        return DesktopApp(
            "frontend/dist/index.html",
            root / "tarefas.json",
            root / "configuracoes.json",
            root / "todox.ico",
            root / "todox-tray.png",
        )

    @patch("backend.desktop.webview.start")
    @patch("backend.desktop.webview.create_window")
    def test_run_uses_the_brand_icon_for_windows(
        self, create_window: Mock, start: Mock
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(directory)
            app.window_icon_path.touch()
            create_window.return_value = MagicMock()
            app._start_integrations = Mock()
            app._stop_integrations = Mock()

            app.run()

            start.assert_called_once_with(
                debug=False, icon=str(app.window_icon_path)
            )

            create_window.assert_called_once()
            self.assertEqual(create_window.call_args.args[:2], (
                "ToDoX",
                "frontend/dist/index.html",
            ))
            self.assertIsNone(app.tray_window)

    @patch("backend.desktop.webview.create_window")
    def test_tray_window_is_created_on_demand_without_hidden_mode(
        self, create_window: Mock
    ) -> None:
        class WindowEvent:
            def __init__(self) -> None:
                self.handlers = []

            def __iadd__(self, handler):
                self.handlers.append(handler)
                return self

            def is_set(self) -> bool:
                return False

        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(directory)
            native = type("NativeWindow", (), {})()
            native.InvokeRequired = False
            native.Deactivate = WindowEvent()
            window = MagicMock(native=native)
            window.events = type(
                "WindowEvents",
                (),
                {
                    "closing": WindowEvent(),
                    "closed": WindowEvent(),
                    "loaded": WindowEvent(),
                },
            )()
            create_window.return_value = window
            app._main_window_loaded = True
            app._hide_native_window_from_taskbar = Mock()

            app.open_tray_menu()

            create_window.assert_called_once()
            tray_call = create_window.call_args
            self.assertEqual(
                tray_call.args, ("ToDoX", "frontend/dist/index.html#tray-menu")
            )
            self.assertEqual(tray_call.kwargs["width"], TRAY_MENU_WIDTH)
            self.assertEqual(
                tray_call.kwargs["height"], TRAY_MENU_MIN_HEIGHT
            )
            self.assertEqual(tray_call.kwargs["x"], -32000)
            self.assertEqual(tray_call.kwargs["y"], -32000)
            self.assertNotIn("hidden", tray_call.kwargs)
            self.assertNotIn("focus", tray_call.kwargs)
            self.assertTrue(tray_call.kwargs["frameless"])
            self.assertTrue(tray_call.kwargs["on_top"])
            self.assertFalse(tray_call.kwargs["resizable"])
            self.assertIs(app.tray_window, window)
            self.assertIsNotNone(app._tray_deactivate_handler)

    def test_right_click_before_main_load_is_deferred(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(directory)
            app._ensure_tray_window = Mock()

            app.open_tray_menu()

            self.assertTrue(app._tray_open_pending)
            app._ensure_tray_window.assert_not_called()

            app._on_main_loaded()

            app._ensure_tray_window.assert_called_once_with()

    @patch(
        "backend.desktop.webview.create_window",
        side_effect=RuntimeError("controller failed"),
    )
    def test_tray_window_creation_failure_allows_a_retry(
        self, create_window: Mock
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(directory)
            app._main_window_loaded = True

            app.open_tray_menu()

            create_window.assert_called_once()
            self.assertIsNone(app.tray_window)
            self.assertFalse(app._tray_window_creating)
            self.assertFalse(app._tray_window_ready)
            self.assertFalse(app._tray_open_pending)
            self.assertEqual(
                app.startup_warnings[-1],
                {
                    "code": "TRAY_MENU_CREATE_FAILED",
                    "details": "controller failed",
                },
            )

    def test_loads_the_brand_icon_for_the_tray(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(directory)
            expected = Image.new("RGBA", (64, 64), (124, 92, 252, 255))
            expected.save(app.tray_icon_path)

            result = app._create_tray_icon()

            self.assertEqual(result.size, (64, 64))
            self.assertEqual(result.mode, "RGBA")
            self.assertEqual(result.getpixel((32, 32)), (124, 92, 252, 255))

    def test_minimizes_when_tray_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(directory)
            app.main_window = Mock()
            app.tray_icon = None

            app.hide_main_window()

            app.main_window.minimize.assert_called_once_with()
            app.main_window.hide.assert_not_called()

    def test_hides_and_notifies_only_once_when_tray_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(directory)
            app.main_window = Mock()
            app.tray_icon = Mock()

            app.hide_main_window()
            app.hide_main_window()

            self.assertEqual(app.main_window.hide.call_count, 2)
            app.tray_icon.notify.assert_called_once()

    def test_ignores_hotkey_while_settings_are_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(directory)
            app.open_quick_add = Mock()

            app.settings_open = True
            app._on_hotkey()
            app.open_quick_add.assert_not_called()

            app.settings_open = False
            app._on_hotkey()
            app.open_quick_add.assert_called_once_with()

    def test_applies_new_listener_before_stopping_previous_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(directory)
            previous_listener = Mock()
            new_listener = Mock()
            app.hotkey_listener = previous_listener
            app.tray_icon = Mock()
            app._new_hotkey_listener = Mock(return_value=new_listener)

            result = app.apply_settings(
                {
                    "ctrl": True, "alt": False, "shift": True, "tecla": "F4",
                    "tema": "dark", "locale": "en",
                }
            )

            new_listener.start.assert_called_once_with()
            previous_listener.stop.assert_called_once_with()
            app.tray_icon.update_menu.assert_not_called()
            self.assertEqual(result["description"], "Ctrl + Shift + F4")
            self.assertEqual(result["tema"], "dark")
            self.assertEqual(result["locale"], "en")
            self.assertTrue((Path(directory) / "configuracoes.json").exists())

    def test_tray_click_adapter_routes_left_and_right_clicks(self) -> None:
        left = Mock()
        right = Mock()
        icon = object.__new__(_ActionTrayIcon)
        icon._on_left_click = left
        icon._on_right_click = right
        icon._log = Mock()
        icon._running = False
        icon._release_icon = Mock()

        icon._on_notify(0, WM_LBUTTONUP)
        icon._on_notify(0, WM_RBUTTONUP)

        left.assert_called_once_with()
        right.assert_called_once_with()

    def test_tray_position_is_clamped_to_the_monitor_work_area(self) -> None:
        result = DesktopApp._calculate_tray_position(
            (1920, 1080),
            (-1920, 0, 1920, 1040),
            (340, 460),
        )
        self.assertEqual(result, (1572, 572))

        top_left = DesktopApp._calculate_tray_position(
            (-1915, 3),
            (-1920, 0, 0, 1040),
            (340, 460),
        )
        self.assertEqual(top_left, (-1912, 11))

    def test_tray_height_includes_paused_activity_marker_and_is_capped(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(directory)
            app.api.list_tasks = Mock(
                return_value=[
                    {
                        "atividade_iniciada": True,
                        "cronometro_iniciado_em": None,
                        "tempo_acumulado_segundos": 0,
                    }
                    for _ in range(20)
                ]
            )

            self.assertEqual(app._tray_menu_height(), TRAY_MENU_MAX_HEIGHT)

    def test_task_refresh_reuses_original_tray_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(directory)
            window = Mock()
            app.tray_window = window
            app.tray_menu_open = True
            app._tray_anchor = (1800, 1000)
            app._tray_work_area = (0, 0, 1920, 1040)
            app._tray_menu_height = Mock(return_value=291)
            app._cursor_and_work_area = Mock(
                side_effect=AssertionError("cursor must not be read again")
            )
            app._position_tray_window = Mock(
                wraps=app._position_tray_window
            )
            window.native = Mock(InvokeRequired=False, Width=TRAY_MENU_WIDTH, Height=291)
            window.native.Handle.ToInt32.return_value = 1
            app._cursor_position = Mock(return_value=(1, 1))

            with (
                patch("backend.desktop.ctypes.windll.user32.SetWindowPos", return_value=True),
                patch("backend.desktop.threading.Thread"),
            ):
                app.notify_tasks_changed({"revision": 1, "history_revision": 1, "tasks": []})
                app._deliver_task_notifications()

            window.resize.assert_called_once_with(TRAY_MENU_WIDTH, 291)
            app._cursor_and_work_area.assert_not_called()

    def test_task_notifications_group_pending_updates_and_reuse_the_task_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(directory)
            app.main_window = Mock()
            app.tray_window = Mock()
            app._main_window_loaded = True
            app._tray_window_ready = True
            app.api.list_tasks = Mock(side_effect=AssertionError("must reuse task payload"))
            app._dispatch_window_event = Mock()
            first = {"revision": 1, "history_revision": 1, "tasks": []}
            latest = {"revision": 2, "history_revision": 1, "tasks": [{"atividade_iniciada": True}]}

            with patch("backend.desktop.threading.Thread") as thread:
                app.notify_tasks_changed(first)
                app.notify_tasks_changed(latest)
                thread.assert_called_once()
                app._dispatch_window_event.assert_not_called()
                app._deliver_task_notifications()

            self.assertEqual(app._dispatch_window_event.call_count, 2)
            app._dispatch_window_event.assert_any_call(app.main_window, "tasks-changed", latest)
            app._dispatch_window_event.assert_any_call(app.tray_window, "tasks-changed", latest)
            app.api.list_tasks.assert_not_called()

    def test_task_notification_avoids_resizing_an_unchanged_popover(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(directory)
            app.tray_window = Mock()
            app.tray_menu_open = True
            app._tray_window_height = 291
            app._resize_and_position_tray_window = Mock()
            app.api.list_tasks = Mock(side_effect=AssertionError("must reuse task payload"))

            with patch("backend.desktop.threading.Thread"):
                app.notify_tasks_changed({
                    "revision": 1, "history_revision": 0,
                    "tasks": [{"atividade_iniciada": True}],
                })
                app._deliver_task_notifications()

            app._resize_and_position_tray_window.assert_not_called()
            app.api.list_tasks.assert_not_called()

    def test_open_tray_menu_toggles_and_dispatches_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(directory)
            window = Mock(native=Mock(InvokeRequired=False))
            app.tray_window = window
            app._tray_window_ready = True
            app._tray_menu_height = Mock(return_value=291)
            app._position_tray_window = Mock()
            app._cursor_and_work_area = Mock(
                return_value=((1800, 1000), (0, 0, 1920, 1040))
            )
            app._focus_window = Mock()

            app.open_tray_menu()

            window.resize.assert_called_once_with(TRAY_MENU_WIDTH, 291)
            app._position_tray_window.assert_called_once_with(
                window, TRAY_MENU_WIDTH, 291
            )
            window.show.assert_called_once_with()
            window.run_js.assert_called_with(
                "window.dispatchEvent(new Event('tray-menu-shown'))"
            )
            self.assertTrue(app.tray_menu_open)
            self.assertEqual(app._tray_anchor, (1800, 1000))

            app.open_tray_menu()
            window.hide.assert_called_once_with()
            self.assertFalse(app.tray_menu_open)
            self.assertIsNone(app._tray_anchor)

    def test_native_tray_window_stays_out_of_taskbar_and_closes_on_blur(
        self,
    ) -> None:
        class NativeEvent:
            def __init__(self) -> None:
                self.handlers = []

            def __iadd__(self, handler):
                self.handlers.append(handler)
                return self

        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(directory)
            native = type("NativeWindow", (), {})()
            native.InvokeRequired = False
            native.Deactivate = NativeEvent()
            app.tray_window = Mock(native=native)
            app._hide_native_window_from_taskbar = Mock()

            app._configure_tray_native_window()

            app._hide_native_window_from_taskbar.assert_called_once_with(native)
            self.assertEqual(
                native.Deactivate.handlers, [app._on_tray_deactivated]
            )
            self.assertIsNotNone(app._tray_deactivate_handler)

    def test_close_tray_menu_is_idempotent_and_exit_destroys_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(directory)
            tray_window = Mock()
            main_window = Mock()
            app.tray_window = tray_window
            app.main_window = main_window
            app.tray_menu_open = True
            app._stop_integrations = Mock()

            app.close_tray_menu()
            app.close_tray_menu()
            tray_window.hide.assert_called_once_with()

            app.request_exit()
            tray_window.destroy.assert_called_once_with()
            main_window.destroy.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
