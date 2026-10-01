import atexit
import ctypes
import sys
import urllib.error
import urllib.request
import winreg
from ctypes import wintypes
from pathlib import Path

import webview

from due_core import DueCore, DueError, apply_windows_startup, bundle_root, focus_title, run_hidden
from tray import DueTray

_instance_mutex = None


def pick_png() -> str:
    import clr

    clr.AddReference("System.Windows.Forms")
    from System.Threading import ApartmentState, Thread, ThreadStart
    from System.Windows.Forms import DialogResult, OpenFileDialog
    holder: dict[str, str] = {}

    def show() -> None:
        dialog = OpenFileDialog()
        dialog.Title = "Logo PNG"
        dialog.Filter = "Logo PNG (*.png)|*.png"
        dialog.Multiselect = False
        dialog.CheckFileExists = True
        if dialog.ShowDialog() == DialogResult.OK and dialog.FileName:
            holder["path"] = str(dialog.FileName)

    thread = Thread(ThreadStart(show))
    thread.SetApartmentState(ApartmentState.STA)
    thread.Start()
    thread.Join()
    return holder.get("path", "")


def claim_single_instance() -> None:
    global _instance_mutex
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    _instance_mutex = kernel.CreateMutexW(None, False, "Local\\Due.Desk")
    if ctypes.get_last_error() == 183:
        focus_title("Zalo Due")
        sys.exit(0)


class Api:
    def __init__(self) -> None:
        self.core = DueCore()
        self.core.start_housekeeping()
        self._window = None
        self._maximized = False
        self._quitting = False
        try:
            apply_windows_startup(bool(self.core.settings.get("startWithWindows")))
        except OSError as exc:
            self.core.log(f"startup registry: {exc}")
        self.core.launch_startup_accounts()

    def attach(self, window) -> None:
        self._window = window
        window.events.maximized += lambda: self._sync_maximized(True)
        window.events.restored += lambda: self._sync_maximized(False)
        window.events.closing += self._on_closing

    def _on_closing(self) -> bool:
        if self._quitting:
            return True
        self.hide_window()
        return False

    def hide_window(self) -> None:
        if self._window is not None:
            self._window.hide()

    def reveal_window(self) -> None:
        if self._window is not None:
            self._window.show()
        focus_title("Zalo Due")

    def quit_app(self) -> None:
        self._quitting = True
        try:
            self.core.stop_zalo()
        except Exception as exc:
            self.core.log(f"quit: {exc}")
        if self._window is not None:
            self._window.destroy()

    def _sync_maximized(self, enabled: bool) -> None:
        self._maximized = enabled
        if self._window is None:
            return
        try:
            self._window.evaluate_js(f"window.setMaximized({str(enabled).lower()})")
        except Exception:
            return

    def minimize(self) -> dict:
        if self._window is not None:
            self._window.minimize()
        return {"ok": True}

    def toggle_maximize(self) -> dict:
        if self._window is None:
            return {"ok": True, "maximized": False}
        if self._maximized:
            self._window.restore()
        else:
            self._window.maximize()
        return {"ok": True, "maximized": not self._maximized}

    def close_window(self) -> dict:
        self.hide_window()
        return {"ok": True}

    def state(self) -> dict:
        return self.core.state()

    def add_account(self, name: str) -> dict:
        return self._call(lambda: self.core.add_account(name))

    def rename_account(self, account_id: str, name: str) -> dict:
        return self._call(lambda: self.core.rename_account(account_id, name))

    def remove_account(self, account_id: str) -> dict:
        return self._call(lambda: self.core.remove_account(account_id))

    def open_account(self, account_id: str) -> dict:
        return self._call(lambda: self.core.open_account(account_id))

    def close_account(self, account_id: str) -> dict:
        return self._call(lambda: self.core.close_account(account_id))

    def install_zalo(self) -> dict:
        return self._call(lambda: self.core.start_install(update=False))

    def update_zalo(self) -> dict:
        return self._call(lambda: self.core.start_install(update=True))

    def set_setting(self, key: str, enabled: bool) -> dict:
        return self._call(lambda: self.core.set_setting(key, enabled))

    def set_account_startup(self, account_id: str, enabled: bool) -> dict:
        return self._call(lambda: self.core.set_account_startup(account_id, enabled))

    def clear_cache(self, account_id: str) -> dict:
        return self._call(lambda: self.core.clear_cache(account_id))

    def open_folder(self, account_id: str) -> dict:
        return self._call(lambda: self.core.open_folder(account_id))

    def choose_icon(self, account_id: str) -> dict:
        def pick() -> dict:
            path = pick_png()
            if not path:
                return {}
            self.core.set_account_icon(account_id, path)
            return {}

        return self._call(pick)

    def _call(self, action) -> dict:
        try:
            result = action()
            if isinstance(result, dict):
                return {"ok": True, **result}
            return {"ok": True}
        except DueError as exc:
            self.core.last_error = str(exc)
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            self.core.last_error = str(exc)
            return {"ok": False, "error": str(exc)}


def ui_file() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "ui" / "index.html"
    return Path(__file__).resolve().parent / "ui" / "index.html"


def webview2_ready() -> bool:
    client = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    paths = [
        rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{client}",
        rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{client}",
    ]
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for path in paths:
            try:
                with winreg.OpenKey(hive, path) as key:
                    version, _ = winreg.QueryValueEx(key, "pv")
            except OSError:
                continue
            if version and version != "0.0.0.0":
                return True
    return False


def ensure_webview2(cache: Path) -> None:
    if webview2_ready():
        return
    cache.mkdir(parents=True, exist_ok=True)
    setup = cache / "MicrosoftEdgeWebview2Setup.exe"
    request = urllib.request.Request(
        "https://go.microsoft.com/fwlink/p/?LinkId=2124703",
        headers={"User-Agent": "ZaloDue"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response, setup.open("wb") as handle:
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
    except (urllib.error.URLError, OSError):
        ctypes.windll.user32.MessageBoxW(
            None,
            "Máy này chưa có WebView2. Hãy nối mạng rồi mở lại Zalo Due.",
            "Zalo Due",
            0x10,
        )
        sys.exit(1)
    run_hidden([str(setup), "/silent", "/install"], check=False)
    if not webview2_ready():
        ctypes.windll.user32.MessageBoxW(
            None,
            "Chưa cài được WebView2. Mở lại Zalo Due khi máy đã có mạng.",
            "Zalo Due",
            0x10,
        )
        sys.exit(1)


def prefer_dark_menus() -> None:
    try:
        uxtheme = ctypes.WinDLL("uxtheme", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetProcAddress.argtypes = [wintypes.HMODULE, ctypes.c_void_p]
        kernel.GetProcAddress.restype = ctypes.c_void_p
        allow_dark = kernel.GetProcAddress(uxtheme._handle, ctypes.c_void_p(135))
        if not allow_dark:
            return
        ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int)(allow_dark)(1)
        flush = kernel.GetProcAddress(uxtheme._handle, ctypes.c_void_p(136))
        if flush:
            ctypes.WINFUNCTYPE(None)(flush)()
    except Exception:
        return


def main() -> None:
    prefer_dark_menus()
    claim_single_instance()
    api = Api()
    ensure_webview2(api.core.cache)
    icon = bundle_root() / "assets" / "zalo.ico"
    window = webview.create_window(
        "Zalo Due",
        url=ui_file().as_uri(),
        js_api=api,
        width=1080,
        height=720,
        min_size=(880, 600),
        background_color="#030304",
        frameless=True,
        easy_drag=False,
        shadow=False,
        hidden="--tray" in sys.argv,
    )
    api.attach(window)
    atexit.register(api.core.stop_zalo)
    tray = DueTray(api, icon)
    tray.start()
    try:
        webview.start(storage_path=str(api.core.home / "webview"), icon=str(icon) if icon.is_file() else None)
    finally:
        tray.stop()


if __name__ == "__main__":
    main()
