# nguyenphi37
"""One tray icon for Zalo Due. Each account is a menu row, not its own icon."""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from pathlib import Path

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_NULL = 0x0000
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203
WM_CONTEXTMENU = 0x007B
WM_APP = 0x8000
WM_DUE_CLICK = WM_APP + 1
IDC_ARROW = 32512
NIM_ADD = 0x00000000
NIM_DELETE = 0x00000002
NIM_SETVERSION = 0x00000004
NOTIFYICON_VERSION_4 = 4
NIN_SELECT = 0x0400
NIN_KEYSELECT = 0x0401
HWND_MESSAGE = wintypes.HWND(-3)
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
MF_GRAYED = 0x00000001
MIIM_ID = 0x00000002
MIIM_STRING = 0x00000040
MIIM_BITMAP = 0x00000080
MIIM_FTYPE = 0x00000100
MFT_STRING = 0x00000000
TPM_RIGHTALIGN = 0x0008
TPM_BOTTOMALIGN = 0x0020
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080
SM_CXSCREEN = 0
SM_CXSMICON = 49
DI_NORMAL = 0x0003
WS_EX_TOOLWINDOW = 0x00000080
WS_POPUP = 0x80000000
ID_SHOW = 1
ID_QUIT = 2
ID_ACCOUNT = 10

for _name in ("HCURSOR", "HBRUSH", "HMENU", "HBITMAP", "HDC", "HGDIOBJ", "ATOM"):
    if not hasattr(wintypes, _name):
        setattr(wintypes, _name, wintypes.HANDLE)

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


class MENUITEMINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("fMask", wintypes.UINT),
        ("fType", wintypes.UINT),
        ("fState", wintypes.UINT),
        ("wID", wintypes.UINT),
        ("hSubMenu", wintypes.HMENU),
        ("hbmpChecked", wintypes.HBITMAP),
        ("hbmpUnchecked", wintypes.HBITMAP),
        ("dwItemData", ctypes.c_size_t),
        ("dwTypeData", wintypes.LPWSTR),
        ("cch", wintypes.UINT),
        ("hbmpItem", wintypes.HBITMAP),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 1)]


user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.TranslateMessage.restype = wintypes.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.LoadImageW.argtypes = [
    wintypes.HINSTANCE,
    wintypes.LPCWSTR,
    wintypes.UINT,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.LoadImageW.restype = wintypes.HANDLE
user32.DestroyIcon.argtypes = [wintypes.HICON]
user32.DestroyIcon.restype = wintypes.BOOL
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.DestroyMenu.restype = wintypes.BOOL
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.AppendMenuW.restype = wintypes.BOOL
user32.InsertMenuItemW.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.BOOL, ctypes.POINTER(MENUITEMINFOW)]
user32.InsertMenuItemW.restype = wintypes.BOOL
user32.TrackPopupMenu.argtypes = [
    wintypes.HMENU,
    wintypes.UINT,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    ctypes.c_void_p,
]
user32.TrackPopupMenu.restype = wintypes.UINT
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetCursor.argtypes = [wintypes.HCURSOR]
user32.SetCursor.restype = wintypes.HCURSOR
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int
user32.DrawIconEx.argtypes = [
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HICON,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
    wintypes.HBRUSH,
    wintypes.UINT,
]
user32.DrawIconEx.restype = wintypes.BOOL
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
user32.LoadCursorW.restype = wintypes.HCURSOR
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC,
    ctypes.POINTER(BITMAPINFO),
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p),
    wintypes.HANDLE,
    wintypes.DWORD,
]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


def _bitmap_from_icon(hicon, size: int):
    screen = user32.GetDC(None)
    if not screen:
        return None
    info = BITMAPINFO()
    info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.bmiHeader.biWidth = size
    info.bmiHeader.biHeight = -size
    info.bmiHeader.biPlanes = 1
    info.bmiHeader.biBitCount = 32
    bits = ctypes.c_void_p()
    bitmap = gdi32.CreateDIBSection(screen, ctypes.byref(info), 0, ctypes.byref(bits), None, 0)
    if not bitmap or not bits:
        user32.ReleaseDC(None, screen)
        return None
    memory = gdi32.CreateCompatibleDC(screen)
    previous = gdi32.SelectObject(memory, bitmap)
    user32.DrawIconEx(memory, 0, 0, hicon, size, size, 0, None, DI_NORMAL)
    gdi32.SelectObject(memory, previous)
    gdi32.DeleteDC(memory)
    user32.ReleaseDC(None, screen)
    raw = (ctypes.c_ubyte * (size * size * 4)).from_address(bits.value)
    for index in range(0, size * size * 4, 4):
        blue = raw[index]
        green = raw[index + 1]
        red = raw[index + 2]
        alpha = raw[index + 3]
        if alpha == 0 and (blue or green or red):
            alpha = 255
            raw[index + 3] = 255
        if alpha < 255:
            raw[index] = blue * alpha // 255
            raw[index + 1] = green * alpha // 255
            raw[index + 2] = red * alpha // 255
    return bitmap


def _load_icon(path: Path, size: int):
    handle = user32.LoadImageW(None, str(path), IMAGE_ICON, size, size, LR_LOADFROMFILE)
    return handle or None


class DueTray:
    def __init__(self, api, icon: Path) -> None:
        self._api = api
        self._icon_path = Path(icon)
        self._thread: threading.Thread | None = None
        self._hwnd = None
        self._ready = threading.Event()
        self._added = False
        self._proc = WNDPROC(self._wndproc)
        self._nid = NOTIFYICONDATAW()
        self._class_name = ctypes.create_unicode_buffer("ZaloDue.Tray")
        self._arrow = user32.LoadCursorW(None, IDC_ARROW)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="due-tray", daemon=True)
        self._thread.start()
        self._ready.wait(5)

    def stop(self) -> None:
        hwnd = self._hwnd
        if hwnd:
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(2)

    def _log(self, message: str) -> None:
        try:
            self._api.core.log(message)
        except Exception:
            return

    def _run(self) -> None:
        instance = kernel32.GetModuleHandleW(None)
        window_class = WNDCLASSEXW()
        window_class.cbSize = ctypes.sizeof(WNDCLASSEXW)
        window_class.lpfnWndProc = self._proc
        window_class.hInstance = instance
        window_class.lpszClassName = ctypes.cast(self._class_name, wintypes.LPCWSTR)
        window_class.hCursor = self._arrow
        user32.RegisterClassExW(ctypes.byref(window_class))
        self._hwnd = user32.CreateWindowExW(
            0,
            self._class_name,
            "DueTray",
            0,
            0,
            0,
            0,
            0,
            HWND_MESSAGE,
            None,
            instance,
            None,
        )
        if not self._hwnd:
            self._log(f"tray window failed {ctypes.get_last_error()}")
            self._ready.set()
            return
        self._add_icon()
        self._ready.set()
        message = MSG()
        while True:
            code = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
            if code <= 0:
                break
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        self._remove_icon()

    def _add_icon(self) -> None:
        icon = _load_icon(self._icon_path, 32) if self._icon_path.is_file() else None
        data = self._nid
        data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        data.hWnd = self._hwnd
        data.uID = 1
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        data.uCallbackMessage = WM_APP
        data.hIcon = icon
        data.szTip = "Zalo Due"
        if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data)):
            self._log(f"tray icon failed {ctypes.get_last_error()}")
            return
        self._added = True
        data.uVersion = NOTIFYICON_VERSION_4
        shell32.Shell_NotifyIconW(NIM_SETVERSION, ctypes.byref(data))

    def _remove_icon(self) -> None:
        if not self._added or not self._hwnd:
            return
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
        self._added = False
        if self._nid.hIcon:
            user32.DestroyIcon(self._nid.hIcon)
            self._nid.hIcon = None

    def _restore_cursor(self) -> None:
        if self._arrow:
            user32.SetCursor(self._arrow)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_APP:
            # Explorer sets the loading cursor until this returns. Do no work here.
            self._restore_cursor()
            event = int(lparam) & 0xFFFF
            if event in (WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP, WM_CONTEXTMENU, NIN_SELECT, NIN_KEYSELECT):
                user32.PostMessageW(hwnd, WM_DUE_CLICK, event, 0)
            return 0
        if msg == WM_DUE_CLICK:
            self._restore_cursor()
            try:
                self._dispatch_click(hwnd, int(wparam) & 0xFFFF)
            except Exception as exc:
                self._log(f"tray click: {exc}")
            self._restore_cursor()
            return 0
        if msg == WM_CLOSE:
            self._remove_icon()
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            self._remove_icon()
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _dispatch_click(self, hwnd, click: int) -> None:
        if click in (WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP, WM_CONTEXTMENU):
            self._show_menu(hwnd)

    def _show_menu(self, hwnd) -> None:
        accounts = []
        try:
            accounts = self._api.core.tray_accounts()
        except Exception as exc:
            self._log(f"tray accounts: {exc}")
        menu = user32.CreatePopupMenu()
        if not menu:
            return
        bitmaps = []
        chosen: dict[int, str] = {}
        command = 0
        try:
            size = user32.GetSystemMetrics(SM_CXSMICON) or 16
            for index, account in enumerate(accounts):
                item_id = ID_ACCOUNT + index
                chosen[item_id] = account["id"]
                bitmap = self._account_bitmap(account.get("icon") or "", size)
                if bitmap:
                    bitmaps.append(bitmap)
                self._insert_account(menu, index, item_id, account["name"], bitmap)
            if not accounts:
                user32.AppendMenuW(menu, MF_STRING | MF_GRAYED, 3, "Chưa có tài khoản")
            user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(menu, MF_STRING, ID_SHOW, "Hiện cửa sổ")
            user32.AppendMenuW(menu, MF_STRING, ID_QUIT, "Thoát hết")
            point = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            align = TPM_RIGHTALIGN if point.x > user32.GetSystemMetrics(SM_CXSCREEN) - 240 else 0
            user32.SetForegroundWindow(hwnd)
            self._restore_cursor()
            command = user32.TrackPopupMenu(
                menu,
                align | TPM_BOTTOMALIGN | TPM_RETURNCMD | TPM_NONOTIFY,
                point.x,
                point.y,
                0,
                hwnd,
                None,
            )
            user32.PostMessageW(hwnd, WM_NULL, 0, 0)
            self._restore_cursor()
        finally:
            user32.DestroyMenu(menu)
            for bitmap in bitmaps:
                gdi32.DeleteObject(bitmap)
        if command == ID_SHOW:
            self._api.reveal_window()
        elif command == ID_QUIT:
            self._remove_icon()
            self._api.quit_app()
        elif command in chosen:
            self._activate_account(chosen[command])

    def _insert_account(self, menu, index: int, item_id: int, name: str, bitmap) -> None:
        label = name.replace("&", "&&")
        text = ctypes.create_unicode_buffer(label)
        info = MENUITEMINFOW()
        info.cbSize = ctypes.sizeof(MENUITEMINFOW)
        info.fMask = MIIM_ID | MIIM_STRING | MIIM_FTYPE
        info.fType = MFT_STRING
        info.wID = item_id
        info.dwTypeData = ctypes.cast(text, wintypes.LPWSTR)
        info.cch = len(label)
        if bitmap:
            info.fMask |= MIIM_BITMAP
            info.hbmpItem = bitmap
        if not user32.InsertMenuItemW(menu, index, True, ctypes.byref(info)):
            self._log(f"tray menu item failed {ctypes.get_last_error()}")

    def _account_bitmap(self, path: str, size: int):
        if not path or not Path(path).is_file():
            return None
        icon = _load_icon(Path(path), size)
        if not icon:
            return None
        try:
            return _bitmap_from_icon(icon, size)
        finally:
            user32.DestroyIcon(icon)

    def _activate_account(self, account_id: str) -> None:
        self._restore_cursor()
        self._open_account(account_id)

    def _open_account(self, account_id: str) -> None:
        def work() -> None:
            try:
                self._api.core.open_account(account_id)
            except Exception as exc:
                self._api.core.last_error = str(exc)
                self._log(f"tray open: {exc}")
                self._api.reveal_window()

        threading.Thread(target=work, name="due-tray-open", daemon=True).start()
