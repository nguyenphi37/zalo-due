"""Due keeps Zalo and every account inside the app folder."""

from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
import winreg
from ctypes import wintypes
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return SOURCE_ROOT


def bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return SOURCE_ROOT


BUILD_DIR = bundle_root() / "native" / "build"
DOWNLOAD_PAGE = "https://zalo.me/download/zalo-pc?utm=90000"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
STILL_ACTIVE = 259
IDLE_AFTER_SECONDS = 5 * 60
TRIM_EVERY_SECONDS = 30
UPDATE_CHECK_SECONDS = 10 * 60
UPDATE_RETRY_SECONDS = 10 * 60
PROCESS_SET_INFORMATION = 0x0200
PROCESS_SET_QUOTA = 0x0100
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_POWER_THROTTLING = 4
PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
NORMAL_PRIORITY_CLASS = 0x00000020
CALL_PROCESSES = {"zalocall.exe", "zavimeet.exe"}
USAGE_CACHE_SECONDS = 20
_CACHE_PARTS = {
    "cache",
    "code cache",
    "gpucache",
    "dawncache",
    "blob_storage",
    "service worker",
    "session storage",
}
_CACHE_RELATIVE = (
    ("Roaming", "ZaloData", "Cache"),
    ("Roaming", "ZaloData", "Code Cache"),
    ("Roaming", "ZaloData", "GPUCache"),
    ("Roaming", "ZaloData", "DawnCache"),
    ("Roaming", "ZaloData", "blob_storage"),
    ("Roaming", "ZaloData", "Service Worker"),
    ("Roaming", "ZaloData", "Session Storage"),
)

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
kernel32.GetFileAttributesW.restype = wintypes.DWORD
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.TerminateProcess.restype = wintypes.BOOL
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetExitCodeProcess.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.GetVolumeInformationW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPWSTR,
    wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.LPWSTR,
    wintypes.DWORD,
]
kernel32.GetVolumeInformationW.restype = wintypes.BOOL


class PROCESS_MEMORY_COUNTERS_EX2(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
        ("PrivateWorkingSetSize", ctypes.c_size_t),
        ("SharedCommitUsage", ctypes.c_ulonglong),
    ]


kernel32.K32GetProcessMemoryInfo.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.DWORD,
]
kernel32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.DeviceIoControl.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.LPVOID,
]
kernel32.DeviceIoControl.restype = wintypes.BOOL

user32 = ctypes.WinDLL("user32", use_last_error=True)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
user32.AllowSetForegroundWindow.restype = wintypes.BOOL
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.GetForegroundWindow.restype = wintypes.HWND

kernel32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.SetPriorityClass.restype = wintypes.BOOL
kernel32.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
kernel32.SetProcessInformation.restype = wintypes.BOOL
kernel32.K32EmptyWorkingSet.argtypes = [wintypes.HANDLE]
kernel32.K32EmptyWorkingSet.restype = wintypes.BOOL

version = ctypes.WinDLL("version", use_last_error=True)
version.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
version.GetFileVersionInfoSizeW.restype = wintypes.DWORD
version.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
version.GetFileVersionInfoW.restype = wintypes.BOOL
version.VerQueryValueW.argtypes = [
    wintypes.LPCVOID,
    wintypes.LPCWSTR,
    ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(wintypes.UINT),
]
version.VerQueryValueW.restype = wintypes.BOOL


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.restype = wintypes.BOOL


class DueError(Exception):
    pass


class _SetupUrl(Exception):
    def __init__(self, url: str) -> None:
        self.url = url


def is_reparse(path: Path) -> bool:
    attrs = kernel32.GetFileAttributesW(str(path))
    if attrs == INVALID_FILE_ATTRIBUTES:
        return False
    return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)


def volume_caption(drive: str) -> str:
    letter = (drive or "C:").rstrip("\\")
    if len(letter) == 1:
        letter = f"{letter}:"
    name = ctypes.create_unicode_buffer(261)
    system = ctypes.create_unicode_buffer(261)
    ok = kernel32.GetVolumeInformationW(letter + "\\", name, 261, None, None, None, system, 261)
    label = name.value.strip() if ok and name.value.strip() else "Windows"
    return f"{label} ({letter})"


def _storage_kind(relative: Path) -> str:
    parts = [part.casefold() for part in relative.parts]
    if not parts:
        return "other"
    if parts[0] == "downloads" or "zalo received files" in parts:
        return "media"
    if "zalodata" in parts:
        if any(part in _CACHE_PARTS for part in parts):
            return "cache"
        if "media" in parts:
            return "media"
        return "system"
    return "other"


def measure_profile(profile: Path) -> dict:
    totals = {"media": 0, "cache": 0, "system": 0, "other": 0}
    if not profile.exists() or is_reparse(profile):
        totals["total"] = 0
        return totals
    stack = [profile]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            path = Path(entry.path)
            try:
                if is_reparse(path):
                    continue
                if entry.is_file(follow_symlinks=False):
                    totals[_storage_kind(path.relative_to(profile))] += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False):
                    stack.append(path)
            except OSError:
                continue
    totals["total"] = totals["media"] + totals["cache"] + totals["system"] + totals["other"]
    return totals


def working_set(pid: int) -> int:
    """Private RAM, the same figure as Task Manager's Memory column."""
    handle = kernel32.OpenProcess(0x1010, False, pid)
    if not handle:
        return 0
    try:
        counters = PROCESS_MEMORY_COUNTERS_EX2()
        counters.cb = ctypes.sizeof(counters)
        if not kernel32.K32GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return 0
        return int(counters.PrivateWorkingSetSize)
    finally:
        kernel32.CloseHandle(handle)


def _deletable(path: Path) -> bool:
    absolute = os.path.normcase(os.path.abspath(str(path)))
    local = os.path.normcase(os.path.abspath(os.environ["LOCALAPPDATA"]))
    temp = os.path.normcase(os.path.abspath(tempfile.gettempdir()))
    folder = app_dir()
    roots = [
        os.path.normcase(os.path.abspath(folder / "data")),
        os.path.normcase(os.path.abspath(folder / "Due")),
        os.path.join(local, "due"),
        temp,
    ]
    return any(absolute == root or absolute.startswith(root + os.sep) for root in roots)


def safe_rmtree(path: Path) -> None:
    path = Path(path)
    if not _deletable(path):
        raise DueError("Từ chối xóa ngoài dữ liệu Due")
    if is_reparse(path):
        os.rmdir(path)
        return
    if not path.exists():
        return

    def unlink(target: Path) -> None:
        try:
            os.chmod(target, stat.S_IWRITE)
        except OSError:
            pass
        target.unlink(missing_ok=True)

    for current, dirs, files in os.walk(path, topdown=True):
        kept = []
        for name in dirs:
            child = Path(current) / name
            if is_reparse(child):
                os.rmdir(child)
            else:
                kept.append(name)
        dirs[:] = kept
        for name in files:
            unlink(Path(current) / name)

    for current, dirs, files in os.walk(path, topdown=False):
        for name in files:
            unlink(Path(current) / name)
        for name in dirs:
            child = Path(current) / name
            if is_reparse(child):
                os.rmdir(child)
            else:
                os.rmdir(child)
    os.rmdir(path)


def clean_name(name: str) -> str:
    text = " ".join((name or "").split())
    if not text:
        raise DueError("Nhập tên để phân biệt tài khoản")
    if len(text) > 40:
        raise DueError("Tên tối đa 40 ký tự")
    return text


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(text: str) -> GUID:
    parts = text.split("-")
    return GUID(
        int(parts[0], 16),
        int(parts[1], 16),
        int(parts[2], 16),
        (ctypes.c_ubyte * 8)(*bytes.fromhex(parts[3] + parts[4])),
    )


def _gdiplus():
    library = ctypes.WinDLL("gdiplus")
    library.GdiplusStartup.argtypes = [ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p, ctypes.c_void_p]
    library.GdipCreateBitmapFromScan0.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    library.GdipGetImageGraphicsContext.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    library.GdipSetSmoothingMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
    library.GdipCreateSolidFill.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
    library.GdipFillEllipseI.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    library.GdipDeleteBrush.argtypes = [ctypes.c_void_p]
    library.GdipCreateFontFamilyFromName.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    library.GdipCreateFont.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
    library.GdipCreateStringFormat.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
    library.GdipSetStringFormatAlign.argtypes = [ctypes.c_void_p, ctypes.c_int]
    library.GdipSetStringFormatLineAlign.argtypes = [ctypes.c_void_p, ctypes.c_int]
    library.GdipDrawString.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    library.GdipDeleteStringFormat.argtypes = [ctypes.c_void_p]
    library.GdipDeleteFont.argtypes = [ctypes.c_void_p]
    library.GdipDeleteFontFamily.argtypes = [ctypes.c_void_p]
    library.GdipDeleteGraphics.argtypes = [ctypes.c_void_p]
    library.GdipDisposeImage.argtypes = [ctypes.c_void_p]
    library.GdipSaveImageToFile.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p]
    library.GdipCreateBitmapFromFile.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)]
    library.GdipGetImageWidth.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    library.GdipGetImageHeight.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    library.GdipDrawImageRectI.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    library.GdipCreatePath.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
    library.GdipCreatePath.restype = ctypes.c_int
    library.GdipAddPathEllipseI.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    library.GdipAddPathEllipseI.restype = ctypes.c_int
    library.GdipSetClipPath.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
    library.GdipSetClipPath.restype = ctypes.c_int
    library.GdipDeletePath.argtypes = [ctypes.c_void_p]
    library.GdipDeletePath.restype = ctypes.c_int
    library.GdipGraphicsClear.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    library.GdipGraphicsClear.restype = ctypes.c_int
    library.GdipSetInterpolationMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
    library.GdipSetInterpolationMode.restype = ctypes.c_int
    library.GdiplusShutdown.argtypes = [ctypes.c_ulong]
    class GdiplusStartupInput(ctypes.Structure):
        _fields_ = [
            ("GdiplusVersion", ctypes.c_uint32),
            ("DebugEventCallback", ctypes.c_void_p),
            ("SuppressBackgroundThread", ctypes.c_int),
            ("SuppressExternalCodecs", ctypes.c_int),
        ]

    token = ctypes.c_ulong()
    startup = GdiplusStartupInput(1, None, 0, 0)
    if library.GdiplusStartup(ctypes.byref(token), ctypes.byref(startup), None) != 0:
        raise DueError("Không vẽ được icon")
    return library, token


def _wrap_png_icon(png: bytes, dest: Path) -> None:
    entry = struct.pack("<BBBBHHII", 32, 32, 0, 0, 1, 32, len(png), 22)
    dest.write_bytes(struct.pack("<HHH", 0, 1, 1) + entry + png)


def _draw_badge(library, letter: str, color: int):
    image = ctypes.c_void_p()
    graphics = ctypes.c_void_p()
    fill = ctypes.c_void_p()
    family = ctypes.c_void_p()
    font = ctypes.c_void_p()
    form = ctypes.c_void_p()
    library.GdipCreateBitmapFromScan0(32, 32, 0, 0x000E200B, None, ctypes.byref(image))
    library.GdipGetImageGraphicsContext(image, ctypes.byref(graphics))
    library.GdipSetSmoothingMode(graphics, 4)
    library.GdipCreateSolidFill(color, ctypes.byref(fill))
    library.GdipFillEllipseI(graphics, fill, 0, 0, 32, 32)
    library.GdipDeleteBrush(fill)
    library.GdipCreateFontFamilyFromName("Segoe UI", None, ctypes.byref(family))
    library.GdipCreateFont(family, 16.0, 1, 2, ctypes.byref(font))
    library.GdipCreateStringFormat(0, 0, ctypes.byref(form))
    library.GdipSetStringFormatAlign(form, 1)
    library.GdipSetStringFormatLineAlign(form, 1)
    ink = ctypes.c_void_p()
    library.GdipCreateSolidFill(0xFFFFFFFF, ctypes.byref(ink))

    class RectF(ctypes.Structure):
        _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float), ("w", ctypes.c_float), ("h", ctypes.c_float)]

    box = RectF(0, 1, 32, 30)
    library.GdipDrawString(graphics, letter, -1, font, ctypes.cast(ctypes.byref(box), ctypes.c_void_p), form, ink)
    for item in (ink, form, font, family, graphics):
        if item:
            pass
    library.GdipDeleteBrush(ink)
    library.GdipDeleteStringFormat(form)
    library.GdipDeleteFont(font)
    library.GdipDeleteFontFamily(family)
    library.GdipDeleteGraphics(graphics)
    return image


def _draw_photo(library, source: Path):
    photo = ctypes.c_void_p()
    if library.GdipCreateBitmapFromFile(str(source), ctypes.byref(photo)) != 0 or not photo:
        raise DueError("Không đọc được ảnh")
    width = ctypes.c_uint()
    height = ctypes.c_uint()
    library.GdipGetImageWidth(photo, ctypes.byref(width))
    library.GdipGetImageHeight(photo, ctypes.byref(height))
    image = ctypes.c_void_p()
    graphics = ctypes.c_void_p()
    library.GdipCreateBitmapFromScan0(32, 32, 0, 0x000E200B, None, ctypes.byref(image))
    library.GdipGetImageGraphicsContext(image, ctypes.byref(graphics))
    library.GdipSetSmoothingMode(graphics, 4)
    library.GdipSetInterpolationMode(graphics, 7)
    library.GdipGraphicsClear(graphics, 0)
    path = ctypes.c_void_p()
    if library.GdipCreatePath(0, ctypes.byref(path)) == 0 and path:
        library.GdipAddPathEllipseI(path, 0, 0, 32, 32)
        library.GdipSetClipPath(graphics, path, 0)
    short = min(width.value, height.value) or 1
    draw_w = max(32, int(width.value * 32 / short))
    draw_h = max(32, int(height.value * 32 / short))
    library.GdipDrawImageRectI(graphics, photo, (32 - draw_w) // 2, (32 - draw_h) // 2, draw_w, draw_h)
    library.GdipDeleteGraphics(graphics)
    if path:
        library.GdipDeletePath(path)
    library.GdipDisposeImage(photo)
    return image


def create_toast_shortcut(path: Path, target: Path, arguments: str, icon: Path, app_id: str, description: str) -> None:
    class PropertyKey(ctypes.Structure):
        _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]

    class PropVariant(ctypes.Structure):
        _fields_ = [
            ("vt", ctypes.c_ushort),
            ("r1", ctypes.c_ushort),
            ("r2", ctypes.c_ushort),
            ("r3", ctypes.c_ushort),
            ("psz", ctypes.c_wchar_p),
            ("pad", ctypes.c_ulonglong),
        ]

    ole = ctypes.OleDLL("ole32")
    ole.CoInitializeEx(None, 2)
    shell = ctypes.c_void_p()
    clsid = _guid("00021401-0000-0000-C000-000000000046")
    link_id = _guid("000214F9-0000-0000-C000-000000000046")
    if ole.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(link_id), ctypes.byref(shell)) != 0:
        raise DueError("Không tạo được shortcut thông báo")

    def vtable(unknown, index, restype, *argtypes):
        table = ctypes.cast(unknown, ctypes.POINTER(ctypes.c_void_p))
        slot = ctypes.cast(table[0], ctypes.POINTER(ctypes.c_void_p))[index]
        prototype = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
        return prototype(slot)

    set_path = vtable(shell, 20, ctypes.c_long, ctypes.c_wchar_p)
    set_args = vtable(shell, 11, ctypes.c_long, ctypes.c_wchar_p)
    set_dir = vtable(shell, 9, ctypes.c_long, ctypes.c_wchar_p)
    set_desc = vtable(shell, 7, ctypes.c_long, ctypes.c_wchar_p)
    set_icon = vtable(shell, 17, ctypes.c_long, ctypes.c_wchar_p, ctypes.c_int)
    query = vtable(shell, 0, ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
    release = vtable(shell, 2, ctypes.c_ulong)
    store = ctypes.c_void_p()
    store_id = _guid("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99")
    if query(shell, ctypes.cast(ctypes.byref(store_id), ctypes.c_void_p), ctypes.byref(store)) != 0:
        release(shell)
        raise DueError("Không gắn được tên tài khoản cho thông báo")
    key = PropertyKey(_guid("9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3"), 5)
    value = PropVariant()
    value.vt = 31
    value.psz = app_id
    set_value = vtable(store, 6, ctypes.c_long, ctypes.POINTER(PropertyKey), ctypes.POINTER(PropVariant))
    commit = vtable(store, 7, ctypes.c_long)
    release_store = vtable(store, 2, ctypes.c_ulong)
    set_path(shell, str(target))
    set_args(shell, arguments)
    set_dir(shell, str(target.parent))
    set_desc(shell, description)
    set_icon(shell, str(icon), 0)
    set_value(store, ctypes.byref(key), ctypes.byref(value))
    commit(store)
    file_ptr = ctypes.c_void_p()
    file_id = _guid("0000010b-0000-0000-C000-000000000046")
    query(shell, ctypes.cast(ctypes.byref(file_id), ctypes.c_void_p), ctypes.byref(file_ptr))
    save = vtable(file_ptr, 6, ctypes.c_long, ctypes.c_wchar_p, ctypes.c_int)
    path.parent.mkdir(parents=True, exist_ok=True)
    save(file_ptr, str(path), 1)
    vtable(file_ptr, 2, ctypes.c_ulong)(file_ptr)
    release_store(store)
    release(shell)


_icon_lock = threading.Lock()


def write_taskbar_icon(dest: Path, name: str, photo: Path | None, salt: str) -> None:
    with _icon_lock:
        _write_taskbar_icon(dest, name, photo, salt)


def _write_taskbar_icon(dest: Path, name: str, photo: Path | None, salt: str) -> None:
    library, token = _gdiplus()
    image = ctypes.c_void_p()
    try:
        if photo is not None and photo.is_file():
            image = _draw_photo(library, photo)
        else:
            colors = (0xFF8C4A32, 0xFF2F6F5E, 0xFF3D5A80, 0xFF8A5A44, 0xFF4C6B4F, 0xFF6B4C7A)
            letter = name.strip()[:1].upper() or "?"
            image = _draw_badge(library, letter, colors[sum(salt.encode("utf-8")) % len(colors)])
        encoder = _guid("557cf406-1a04-11d3-9a73-0000f81ef32e")
        handle, name = tempfile.mkstemp(suffix=".png")
        os.close(handle)
        temp = Path(name)
        try:
            if library.GdipSaveImageToFile(image, str(temp), ctypes.byref(encoder), None) != 0:
                raise DueError("Không lưu được icon")
            library.GdipDisposeImage(image)
            image = ctypes.c_void_p()
            png = temp.read_bytes()
        finally:
            temp.unlink(missing_ok=True)
    finally:
        if image:
            library.GdipDisposeImage(image)
        library.GdiplusShutdown(token)
    _wrap_png_icon(png, dest)


def pe_machine(path: Path) -> int:
    with path.open("rb") as handle:
        handle.seek(0x3C)
        offset = int.from_bytes(handle.read(4), "little")
        handle.seek(offset + 4)
        return int.from_bytes(handle.read(2), "little")


def version_parts(text: str | None) -> tuple[int, ...]:
    if not text:
        return ()
    match = re.search(r"(\d+(?:\.\d+)+)", text)
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def file_version(path: Path) -> str | None:
    size = version.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return None
    buffer = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(path), 0, size, buffer):
        return None

    class VS_FIXEDFILEINFO(ctypes.Structure):
        _fields_ = [
            ("dwSignature", wintypes.DWORD),
            ("dwStrucVersion", wintypes.DWORD),
            ("dwFileVersionMS", wintypes.DWORD),
            ("dwFileVersionLS", wintypes.DWORD),
            ("dwProductVersionMS", wintypes.DWORD),
            ("dwProductVersionLS", wintypes.DWORD),
            ("dwFileFlagsMask", wintypes.DWORD),
            ("dwFileFlags", wintypes.DWORD),
            ("dwFileOS", wintypes.DWORD),
            ("dwFileType", wintypes.DWORD),
            ("dwFileSubtype", wintypes.DWORD),
            ("dwFileDateMS", wintypes.DWORD),
            ("dwFileDateLS", wintypes.DWORD),
        ]

    pointer = ctypes.c_void_p()
    length = wintypes.UINT()
    if not version.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        return None
    info = ctypes.cast(pointer, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
    major = (info.dwFileVersionMS >> 16) & 0xFFFF
    minor = info.dwFileVersionMS & 0xFFFF
    patch = (info.dwFileVersionLS >> 16) & 0xFFFF
    build = info.dwFileVersionLS & 0xFFFF
    return f"{major}.{minor}.{patch}.{build}"


def iter_processes():
    snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)
    if snapshot is None or snapshot == ctypes.c_void_p(-1).value:
        return
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    try:
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            yield int(entry.th32ProcessID), int(entry.th32ParentProcessID), entry.szExeFile
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)


def image_path(pid: int) -> str | None:
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        return buffer.value
    finally:
        kernel32.CloseHandle(handle)


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def descendant_pids(root: int) -> set[int]:
    children: dict[int, list[int]] = {}
    for pid, parent, _name in iter_processes():
        children.setdefault(parent, []).append(pid)
    found = {root}
    stack = [root]
    while stack:
        current = stack.pop()
        for child in children.get(current, []):
            if child not in found:
                found.add(child)
                stack.append(child)
    return found


def _force_foreground(hwnd) -> None:
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)
    else:
        user32.ShowWindow(hwnd, 5)
    user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
    user32.AllowSetForegroundWindow(0xFFFFFFFF)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)


def _window_title(hwnd) -> str:
    buffer = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buffer, 512)
    return buffer.value


def _window_class(hwnd) -> str:
    buffer = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(hwnd, buffer, 128)
    return buffer.value


def _background_title(title: str) -> bool:
    text = title.casefold()
    return any(
        name in text
        for name in ("shared worker", "service worker", "dedicated worker", "sqlite")
    )


def hide_background_windows(pids: set[int]) -> None:
    """Shared Worker is a blank Chromium helper. Never leave it on screen."""

    def visit(hwnd, _lparam):
        proc = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc))
        if proc.value not in pids or not user32.IsWindowVisible(hwnd):
            return True
        if _background_title(_window_title(hwnd)):
            user32.ShowWindow(hwnd, 0)
        return True

    user32.EnumWindows(WNDENUMPROC(visit), 0)


def hide_blank_frames(pids: set[int]) -> None:
    """Hide the empty native-frame Zalo window once the real window is visible."""
    frameless = False
    shells: list[int] = []

    def visit(hwnd, _lparam):
        nonlocal frameless
        proc = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc))
        if proc.value not in pids or user32.GetWindow(hwnd, 4):
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.GetWindowLongPtrW(hwnd, -20) & 0x80:
            return True
        if "Chrome_WidgetWin" not in _window_class(hwnd):
            return True
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
        if area < 320 * 200:
            return True
        caption = bool(user32.GetWindowLongPtrW(hwnd, -16) & 0x00C00000)
        if caption and _window_title(hwnd).strip() in {"", "Zalo"}:
            shells.append(hwnd)
        elif not caption:
            frameless = True
        return True

    user32.EnumWindows(WNDENUMPROC(visit), 0)
    if not frameless:
        return
    for hwnd in shells:
        user32.ShowWindow(hwnd, 0)


def account_hwnd(name: str) -> tuple[int, int] | None:
    """The account window, including one Zalo has hidden. Title is 'Name - Zalo'."""
    want = f"{name} - Zalo"
    best: tuple[int, int] | None = None
    best_key: tuple[int, int] | None = None

    def visit(hwnd, _lparam):
        nonlocal best, best_key
        if _window_title(hwnd) != want or user32.GetWindow(hwnd, 4):
            return True
        proc = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc))
        rect = wintypes.RECT()
        area = 0
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
        visible = 1 if user32.IsWindowVisible(hwnd) else 0
        key = (visible, area)
        if best_key is None or key > best_key:
            best = (hwnd, int(proc.value))
            best_key = key
        return True

    user32.EnumWindows(WNDENUMPROC(visit), 0)
    return best


def hide_account_window(name: str) -> None:
    located = account_hwnd(name)
    if located and user32.IsWindowVisible(located[0]):
        user32.ShowWindow(located[0], 0)


def focus_pids(pids: set[int]) -> bool:
    """Bring forward the real account window, not Zalo's blank framed shell."""
    hide_background_windows(pids)
    best = None
    best_key: tuple[int, int, int, int] | None = None

    def visit(hwnd, _lparam):
        nonlocal best, best_key
        proc = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc))
        if proc.value not in pids or user32.GetWindow(hwnd, 4):
            return True
        style = user32.GetWindowLongPtrW(hwnd, -16)
        extra = user32.GetWindowLongPtrW(hwnd, -20)
        if extra & 0x80:
            return True
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
        if area < 320 * 200:
            return True
        title = _window_title(hwnd).strip()
        if _background_title(title):
            return True
        branded = " - Zalo" in title
        visible = bool(user32.IsWindowVisible(hwnd))
        caption = bool(style & 0x00C00000)
        if caption and title in {"", "Zalo"}:
            return True
        key = (1 if branded else 0, 1 if visible else 0, 0 if caption else 1, area)
        if best_key is None or key > best_key:
            best = hwnd
            best_key = key
        return True

    callback = WNDENUMPROC(visit)
    user32.EnumWindows(callback, 0)
    if not best:
        return False
    _force_foreground(best)
    return True


def focus_title(title: str) -> bool:
    found = None

    def visit(hwnd, _lparam):
        nonlocal found
        if user32.GetWindow(hwnd, 4):
            return True
        buffer = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buffer, 512)
        if buffer.value == title:
            found = hwnd
            return False
        return True

    callback = WNDENUMPROC(visit)
    user32.EnumWindows(callback, 0)
    if not found:
        return False
    user32.ShowWindow(found, 9 if user32.IsIconic(found) else 5)
    user32.SetForegroundWindow(found)
    return True


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        target = Path(sys.executable).resolve()
        return f'"{target}" --tray'
    packaged = app_dir() / "Zalo Due.exe"
    if packaged.is_file():
        return f'"{packaged.resolve()}" --tray'
    script = Path(__file__).resolve().parent / "main.py"
    return f'"{Path(sys.executable).resolve()}" "{script}" --tray'


def apply_windows_startup(enabled: bool) -> None:
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        if not enabled:
            try:
                winreg.DeleteValue(key, "Zalo Due")
            except FileNotFoundError:
                return
            return
        winreg.SetValueEx(key, "Zalo Due", 0, winreg.REG_SZ, startup_command())


def run_hidden(args: list[str], **kwargs):
    startup = kwargs.get("startupinfo") or subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_FORCEOFFFEEDBACK
    kwargs["startupinfo"] = startup
    kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
    return subprocess.run(args, **kwargs)


def terminate_pids(pids: set[int]) -> None:
    handles = []
    for pid in pids:
        if pid <= 0:
            continue
        handle = kernel32.OpenProcess(0x0001, False, pid)
        if not handle:
            continue
        kernel32.TerminateProcess(handle, 1)
        handles.append(handle)
    for handle in handles:
        kernel32.CloseHandle(handle)


def taskkill(pid: int, *, tree: bool = True) -> None:
    command = ["taskkill", "/PID", str(pid), "/F"]
    if tree:
        command.append("/T")
    run_hidden(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class _PowerThrottle(ctypes.Structure):
    _fields_ = [
        ("Version", wintypes.DWORD),
        ("ControlMask", wintypes.DWORD),
        ("StateMask", wintypes.DWORD),
    ]


def foreground_pid() -> int | None:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    proc = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc))
    return proc.value or None


def set_efficiency(pid: int, enabled: bool) -> None:
    access = PROCESS_SET_INFORMATION | PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION
    handle = kernel32.OpenProcess(access, False, pid)
    if not handle:
        return
    try:
        state = _PowerThrottle(
            1,
            PROCESS_POWER_THROTTLING_EXECUTION_SPEED,
            PROCESS_POWER_THROTTLING_EXECUTION_SPEED if enabled else 0,
        )
        kernel32.SetProcessInformation(handle, PROCESS_POWER_THROTTLING, ctypes.byref(state), ctypes.sizeof(state))
        kernel32.SetPriorityClass(handle, BELOW_NORMAL_PRIORITY_CLASS if enabled else NORMAL_PRIORITY_CLASS)
        if enabled:
            kernel32.K32EmptyWorkingSet(handle)
    finally:
        kernel32.CloseHandle(handle)


def is_foreign_updater(image: str, name: str) -> bool:
    lowered = f"{image} {name}".lower()
    if any(marker in lowered for marker in ("zalosetup", "\\update.exe", "uninstall zalo", "\\zalo-updater\\", "zalo-updater")):
        return "zalo" in lowered
    path = Path(image)
    if path.name.lower() != "zalo.exe" or path.parent.name.lower() != "zalo":
        return False
    try:
        return path.stat().st_size < 5_000_000
    except OSError:
        return False


def _same_dir(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def _junction_target(link: Path) -> Path | None:
    if not is_reparse(link):
        return None
    try:
        return Path(os.readlink(link))
    except OSError:
        return None


def _create_junction(link: Path, target: Path) -> None:
    link.mkdir(parents=True, exist_ok=False)
    absolute = os.path.normpath(os.path.abspath(target))
    substitute = ("\\??\\" + absolute + "\0").encode("utf-16le")
    printable = (absolute + "\0").encode("utf-16le")
    body = struct.pack("<HHHH", 0, len(substitute) - 2, len(substitute), len(printable) - 2)
    body += substitute + printable
    buffer = struct.pack("<IHH", 0xA0000003, len(body), 0) + body
    raw = ctypes.create_string_buffer(buffer)
    handle = kernel32.CreateFileW(str(link), 0x40000000, 0, None, 3, 0x02200000, None)
    if handle == wintypes.HANDLE(-1).value:
        os.rmdir(link)
        raise DueError("Không tạo được liên kết thư mục")
    returned = wintypes.DWORD(0)
    ok = kernel32.DeviceIoControl(handle, 0x000900A4, raw, len(buffer), None, 0, ctypes.byref(returned), None)
    error = ctypes.get_last_error()
    kernel32.CloseHandle(handle)
    if not ok:
        os.rmdir(link)
        raise DueError(f"Không tạo được liên kết thư mục ({error})")


def link_junction(link: Path, target: Path, *, create_target: bool) -> None:
    if create_target:
        target.mkdir(parents=True, exist_ok=True)
    elif not target.exists():
        return
    current = _junction_target(link)
    if current is not None and _same_dir(current, target):
        return
    if is_reparse(link):
        os.rmdir(link)
    elif link.exists():
        return
    link.parent.mkdir(parents=True, exist_ok=True)
    _create_junction(link, target)


def resolve_setup_url() -> str:
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if newurl.split("?")[0].lower().endswith(".exe"):
                raise _SetupUrl(newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(Redirect)
    request = urllib.request.Request(DOWNLOAD_PAGE, headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(request, timeout=40) as response:
            final = response.geturl()
    except _SetupUrl as found:
        return found.url
    if final.split("?")[0].lower().endswith(".exe"):
        return final
    raise DueError("Không lấy được link cài Zalo")


def copy_tree_skip_reparse(source: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for current, dirs, files in os.walk(source):
        dirs[:] = [name for name in dirs if not is_reparse(Path(current) / name)]
        target = dest / Path(current).relative_to(source)
        target.mkdir(parents=True, exist_ok=True)
        for name in files:
            copied = target / name
            if not copied.exists():
                shutil.copy2(Path(current) / name, copied)


def _file_count(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for current, dirs, files in os.walk(path):
        dirs[:] = [name for name in dirs if not is_reparse(Path(current) / name)]
        total += len(files)
    return total


def _no_login_browser_profile(path: Path) -> bool:
    config = path / "config.json"
    if not config.is_file():
        return False
    text = config.read_text(encoding="utf-8", errors="replace").lower()
    return not any(marker in text for marker in ("uid", "phone", "user_id", "userid", "login"))


def _is_png(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(8) == b"\x89PNG\r\n\x1a\n"
    except OSError:
        return False


def relocate_data_folder(home: Path) -> None:
    legacy = home.parent / "Due"
    if (home / "accounts.json").exists() or not (legacy / "accounts.json").exists():
        return
    if home.exists():
        try:
            next(home.iterdir())
        except StopIteration:
            home.rmdir()
        else:
            return
    try:
        shutil.move(str(legacy), str(home))
    except OSError:
        return


class DueCore:
    def __init__(self, home: Path | None = None) -> None:
        self.home = Path(home) if home else app_dir() / "data"
        relocate_data_folder(self.home)
        self.zalo_dir = self.home / "Zalo"
        self.updater_dir = self.home / "zalo-updater"
        self.profiles = self.home / "profiles"
        self.selftest_root = self.home / "selftest"
        self.bin = self.home / "bin"
        self.cache = self.home / "cache"
        self.logs = self.home / "logs"
        self.accounts_path = self.home / "accounts.json"
        self.settings_path = self.home / "settings.json"
        self._lock = threading.Lock()
        self.job: dict | None = None
        self.last_error: str | None = None
        self._saving: set[str] = set()
        self._idle_since: dict[str, float] = {}
        self._trimmed_at: dict[str, float] = {}
        self._usage: dict[str, tuple[float, dict]] = {}
        self._housekeeping = False
        self._check_soon = False
        self._latest: str | None = None
        self.settings = {"autoUpdate": True, "efficiency": True, "startWithWindows": False}
        for folder in (self.home, self.profiles, self.selftest_root, self.bin, self.cache, self.logs, self.updater_dir):
            folder.mkdir(parents=True, exist_ok=True)
        self.accounts = self._load_accounts()
        self.settings = self._load_settings()
        self.migrate_legacy_home()
        self.adopt_zalo()
        self.retire_external_zalo()

    def log(self, message: str) -> None:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with (self.logs / "due.log").open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {message}\n")

    def _load_accounts(self) -> list[dict]:
        if not self.accounts_path.exists():
            return []
        try:
            data = json.loads(self.accounts_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        accounts = data.get("accounts", [])
        return [item for item in accounts if isinstance(item, dict) and item.get("id") and item.get("name")]

    def _save_accounts(self) -> None:
        payload = json.dumps({"accounts": self.accounts}, ensure_ascii=False, indent=2)
        temp = self.accounts_path.with_suffix(".json.tmp")
        temp.write_text(payload, encoding="utf-8")
        temp.replace(self.accounts_path)

    def _load_settings(self) -> dict:
        settings = {"autoUpdate": True, "efficiency": True, "startWithWindows": False}
        if not self.settings_path.exists():
            return settings
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return settings
        if not isinstance(data, dict):
            return settings
        settings["autoUpdate"] = bool(data.get("autoUpdate", True))
        settings["efficiency"] = bool(data.get("efficiency", True))
        settings["startWithWindows"] = bool(data.get("startWithWindows", False))
        return settings

    def _save_settings(self) -> None:
        payload = json.dumps(self.settings, ensure_ascii=False, indent=2)
        temp = self.settings_path.with_suffix(".json.tmp")
        temp.write_text(payload, encoding="utf-8")
        temp.replace(self.settings_path)

    def set_setting(self, key: str, enabled: bool) -> None:
        if key not in ("autoUpdate", "efficiency", "startWithWindows"):
            raise DueError("Không có mục này")
        if not isinstance(enabled, bool):
            raise DueError("Giá trị bật tắt không hợp lệ")
        with self._lock:
            previous = bool(self.settings.get(key))
            self.settings[key] = enabled
            self._save_settings()
            if key == "autoUpdate" and enabled:
                self._check_soon = True
        if key == "efficiency" and not enabled:
            self._release_efficiency()
        if key == "startWithWindows":
            try:
                apply_windows_startup(enabled)
            except OSError as exc:
                with self._lock:
                    self.settings[key] = previous
                    self._save_settings()
                self.log(f"startup registry: {exc}")
                raise DueError("Không ghi được khởi động cùng Windows") from exc
            if not enabled:
                with self._lock:
                    for account in self.accounts:
                        account["openWithWindows"] = False
                    self._save_accounts()

    def set_account_startup(self, account_id: str, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise DueError("Giá trị bật tắt không hợp lệ")
        with self._lock:
            account = self._account(account_id)
            account["openWithWindows"] = enabled
            self._save_accounts()
            self.last_error = None
            arm_due = enabled and not self.settings.get("startWithWindows")
            if arm_due:
                self.settings["startWithWindows"] = True
                self._save_settings()
        if not arm_due:
            return
        try:
            apply_windows_startup(True)
        except OSError as exc:
            with self._lock:
                self.settings["startWithWindows"] = False
                self._save_settings()
                account = self._account(account_id)
                account["openWithWindows"] = False
                self._save_accounts()
            self.log(f"startup registry: {exc}")
            raise DueError("Không ghi được khởi động cùng Windows") from exc

    def launch_startup_accounts(self) -> None:
        if "--tray" not in sys.argv:
            return
        with self._lock:
            ids = [item["id"] for item in self.accounts if item.get("openWithWindows")]
        if not ids:
            return
        threading.Thread(
            target=self._open_startup_accounts,
            args=(ids,),
            name="due-boot-accounts",
            daemon=True,
        ).start()

    def _open_startup_accounts(self, ids: list[str]) -> None:
        for account_id in ids:
            try:
                self.open_account(account_id, hidden=True)
            except Exception as exc:
                self.log(f"boot account {account_id}: {exc}")

    def tray_accounts(self) -> list[dict]:
        with self._lock:
            snapshot = [dict(item) for item in self.accounts]
        rows = []
        for account in snapshot:
            icon = self.profile_path(account["id"]) / "taskbar.ico"
            if not icon.is_file():
                try:
                    icon = self.prepare_taskbar(account)
                except DueError:
                    pass
            rows.append(
                {
                    "id": account["id"],
                    "name": account["name"],
                    "icon": str(icon) if icon.is_file() else "",
                }
            )
        return rows

    def _account(self, account_id: str) -> dict:
        for account in self.accounts:
            if account["id"] == account_id:
                return account
        raise DueError("Không thấy tài khoản")

    def profile_path(self, account_id: str, *, bucket: str = "profiles") -> Path:
        try:
            uuid.UUID(account_id)
        except ValueError as exc:
            raise DueError("Mã tài khoản không hợp lệ") from exc
        root = self.profiles if bucket == "profiles" else self.selftest_root
        return root / account_id

    def stage_binaries(self) -> None:
        for arch in ("x86", "x64"):
            destination = self.bin / arch
            destination.mkdir(parents=True, exist_ok=True)
            for name in ("DueHook.dll", "DueLaunch.exe", "DueProbe.exe"):
                source = BUILD_DIR / arch / name
                if not source.exists():
                    raise DueError("Due chưa được biên dịch")
                target = destination / name
                if not target.exists() or source.stat().st_mtime > target.stat().st_mtime:
                    try:
                        shutil.copy2(source, target)
                    except OSError:
                        if not target.exists():
                            raise DueError("Due chưa được biên dịch") from None

    def tools_for(self, program: Path) -> tuple[Path, Path]:
        arch = "x86" if pe_machine(program) == 0x14C else "x64"
        folder = self.bin / arch
        launch = folder / "DueLaunch.exe"
        dll = folder / "DueHook.dll"
        if not launch.exists() or not dll.exists():
            raise DueError("Thiếu thành phần để mở Zalo")
        return launch, dll

    def _scan_zalo(self, root: Path) -> list[Path]:
        if not root.exists() or is_reparse(root):
            return []
        found: list[Path] = []
        found.extend(path for path in root.glob("Zalo-*/Zalo.exe") if path.is_file())
        found.extend(path for path in root.glob("app-*/Zalo.exe") if path.is_file())
        direct = root / "Zalo.exe"
        if direct.is_file() and direct.stat().st_size > 5_000_000:
            found.append(direct)
        return found

    def find_zalo(self) -> Path | None:
        found = self._scan_zalo(self.zalo_dir)
        if not found:
            local = Path(os.environ["LOCALAPPDATA"])
            for root in (
                local / "Programs" / "Zalo",
                local / "Zalo",
                local / "ZaloPC",
                Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Zalo",
                Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Zalo",
            ):
                found.extend(self._scan_zalo(root))
        if not found:
            return None

        def rank(path: Path) -> tuple:
            return (version_parts(path.parent.name), path.stat().st_mtime)

        return max(found, key=rank)

    def zalo_version(self) -> str | None:
        exe = self.find_zalo()
        if exe is None:
            return None
        folder = version_parts(exe.parent.name)
        if len(folder) >= 3 and folder[0] >= 20:
            return ".".join(str(part) for part in folder)
        install = self.install_root(exe)
        for marker in install.glob("pc_*"):
            parts = version_parts(marker.name)
            if len(parts) >= 3:
                return ".".join(str(part) for part in parts)
        raw = file_version(exe)
        if version_parts(raw)[:3] == (1, 0, 0):
            return None
        return raw

    def install_root(self, exe: Path) -> Path:
        parent = exe.parent
        if parent.name.lower().startswith(("app-", "zalo-")):
            return parent.parent
        return parent

    def ensure_layout(self, profile: Path, zalo_exe: Path | None) -> None:
        for name in ("Roaming", "Local", "LocalLow", "Documents", "Downloads"):
            (profile / name).mkdir(parents=True, exist_ok=True)
        (profile / "Documents" / "Zalo Received Files").mkdir(parents=True, exist_ok=True)
        link_junction(profile / "Roaming" / "zalo-updater", self.updater_dir, create_target=True)
        if zalo_exe is None:
            return
        install = self.install_root(zalo_exe)
        (profile / "Local" / "Programs").mkdir(parents=True, exist_ok=True)
        link_junction(profile / "Local" / "Programs" / "Zalo", install, create_target=False)

    def migrate_legacy_home(self) -> None:
        old = Path(os.environ["LOCALAPPDATA"]) / "Due"
        if not old.exists() or _same_dir(old, self.home):
            return
        old_accounts = old / "accounts.json"
        if old_accounts.is_file() and not self.accounts:
            self.accounts_path.write_bytes(old_accounts.read_bytes())
            self.accounts = self._load_accounts()
        old_profiles = old / "profiles"
        if old_profiles.is_dir():
            for child in old_profiles.iterdir():
                if not child.is_dir() or is_reparse(child):
                    continue
                dest = self.profiles / child.name
                if dest.exists():
                    continue
                before = _file_count(child)
                copy_tree_skip_reparse(child, dest)
                if _file_count(dest) < before:
                    raise DueError("Chưa chuyển hết dữ liệu tài khoản vào thư mục app")
        safe_rmtree(old)
        self.log("moved accounts into the app folder")

    def adopt_zalo(self) -> None:
        if self._scan_zalo(self.zalo_dir):
            return
        legacy = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Zalo"
        if not self._scan_zalo(legacy):
            return
        self.stop_zalo()
        shutil.move(str(legacy), str(self.zalo_dir))
        self.log(f"moved Zalo into {self.zalo_dir}")

    def retire_external_zalo(self) -> None:
        if not self._scan_zalo(self.zalo_dir):
            return
        shortcut = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Zalo.lnk"
        if shortcut.is_file():
            shortcut.unlink()
        self._remove_uninstall_key()
        roaming = Path(os.environ["APPDATA"])
        leftover = roaming / "ZaloData"
        if leftover.exists() and not is_reparse(leftover) and _no_login_browser_profile(leftover):
            shutil.rmtree(leftover, ignore_errors=True)
        updater = roaming / "zalo-updater"
        if not updater.exists() or is_reparse(updater) or _same_dir(updater, self.updater_dir):
            return
        if any(updater.iterdir()):
            if not any(self.updater_dir.iterdir()):
                shutil.rmtree(self.updater_dir, ignore_errors=True)
                shutil.move(str(updater), str(self.updater_dir))
        else:
            updater.rmdir()

    def _remove_uninstall_key(self) -> None:
        path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as root:
                names = []
                index = 0
                while True:
                    try:
                        names.append(winreg.EnumKey(root, index))
                    except OSError:
                        break
                    index += 1
            for name in names:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path + "\\" + name) as key:
                    try:
                        display, _ = winreg.QueryValueEx(key, "DisplayName")
                    except OSError:
                        continue
                if not str(display).lower().startswith("zalo"):
                    continue
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path + "\\" + name)
        except OSError as exc:
            self.log(f"uninstall key: {exc}")

    def _custom_photo(self, account_id: str) -> Path | None:
        profile = self.profile_path(account_id)
        matches = sorted(profile.glob("custom-icon.*"))
        return matches[0] if matches else None

    def prepare_taskbar(self, account: dict) -> Path:
        profile = self.profile_path(account["id"])
        profile.mkdir(parents=True, exist_ok=True)
        icon = profile / "taskbar.ico"
        write_taskbar_icon(icon, account["name"], self._custom_photo(account["id"]), account["id"])
        return icon

    def _shortcut_folder(self) -> Path:
        return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Due"

    def _shortcut_path(self, account: dict) -> Path:
        safe = "".join(ch for ch in account["name"] if ch not in '<>:"/\\|?*').strip() or "Zalo"
        return self._shortcut_folder() / account["id"][:8] / f"{safe}.lnk"

    def remove_toast_shortcut(self, account_id: str) -> None:
        folder = self._shortcut_folder()
        if not folder.exists():
            return
        for shortcut in folder.glob(f"*-{account_id[:8]}.lnk"):
            shortcut.unlink(missing_ok=True)
        nested = folder / account_id[:8]
        if nested.is_dir():
            shutil.rmtree(nested, ignore_errors=True)

    def publish_taskbar(self, account: dict, exe: Path, dll: Path, launch: Path, icon: Path) -> None:
        profile = self.profile_path(account["id"])

        def quote(value: str) -> str:
            return '"' + value.replace('"', "'") + '"'

        arguments = " ".join(
            [
                "--root",
                quote(str(profile)),
                "--id",
                quote(account["id"]),
                "--exe",
                quote(str(exe)),
                "--dll",
                quote(str(dll)),
                "--name",
                quote(account["name"]),
                "--icon",
                quote(str(icon)),
            ]
        )
        self.remove_toast_shortcut(account["id"])
        create_toast_shortcut(
            self._shortcut_path(account),
            launch,
            arguments,
            icon,
            f"Due.Zalo.{account['id']}",
            account["name"],
        )

    def set_account_icon(self, account_id: str, source: str) -> None:
        src = Path(source)
        if src.suffix.lower() != ".png" or not _is_png(src):
            raise DueError("Chỉ nhận file PNG")
        if not src.is_file():
            raise DueError("Không thấy file ảnh")
        with self._lock:
            account = dict(self._account(account_id))
        profile = self.profile_path(account_id)
        profile.mkdir(parents=True, exist_ok=True)
        for old in profile.glob("custom-icon.*"):
            old.unlink(missing_ok=True)
        dest = profile / f"custom-icon{src.suffix.lower()}"
        shutil.copy2(src, dest)
        self._publish_account(account)

    def read_pid(self, profile: Path) -> int | None:
        file = profile / "due.pid"
        if not file.exists():
            return None
        try:
            return int(file.read_text(encoding="utf-8").strip())
        except ValueError:
            return None

    def running_pid(self, account_id: str) -> int | None:
        profile = self.profile_path(account_id)
        with self._lock:
            try:
                name = self._account(account_id)["name"]
            except DueError:
                return None
        located = account_hwnd(name)
        window_pid = located[1] if located else None
        if window_pid and pid_alive(window_pid):
            if self.read_pid(profile) != window_pid:
                (profile / "due.pid").write_text(str(window_pid), encoding="utf-8")
            return window_pid
        pid = self.read_pid(profile)
        if pid is None or not pid_alive(pid):
            return None
        image = image_path(pid) or ""
        if "zalo" not in Path(image).name.lower():
            return None
        return pid

    def account_running(self, account_id: str) -> bool:
        return self.running_pid(account_id) is not None

    def state(self) -> dict:
        version = self.zalo_version()
        with self._lock:
            snapshot = [dict(item) for item in self.accounts]
            saving = set(self._saving)
            job = self.job
            error = self.last_error
            settings = dict(self.settings)
            idle_since = dict(self._idle_since)
            latest = self._latest
        accounts = []
        for account in snapshot:
            photo = self._custom_photo(account["id"])
            running = self.account_running(account["id"])
            since = idle_since.get(account["id"])
            idle_for = int(max(0, time.monotonic() - since)) if running and since else 0
            accounts.append(
                {
                    "id": account["id"],
                    "name": account["name"],
                    "running": running,
                    "saving": running and settings["efficiency"] and account["id"] in saving,
                    "idleFor": idle_for,
                    "icon": photo.as_uri() if photo else "",
                    "openWithWindows": bool(account.get("openWithWindows")),
                    **self.account_usage(account["id"], running),
                }
            )
        current_key = version_parts(version or "")[:3]
        latest_key = version_parts(latest or "")[:3]
        return {
            "zalo": {
                "installed": version is not None,
                "version": version,
                "latest": latest,
                "updateAvailable": bool(latest_key) and latest_key > current_key,
            },
            "settings": settings,
            "accounts": accounts,
            "job": job,
            "error": error,
        }

    def add_account(self, name: str) -> dict:
        cleaned = clean_name(name)
        account = {"id": str(uuid.uuid4()), "name": cleaned, "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with self._lock:
            self.accounts.append(account)
            self._save_accounts()
            self.last_error = None
        self.profile_path(account["id"]).mkdir(parents=True, exist_ok=True)
        return account

    def account_usage(self, account_id: str, running: bool | None = None) -> dict:
        now = time.monotonic()
        with self._lock:
            cached = self._usage.get(account_id)
        if cached is None or now - cached[0] >= USAGE_CACHE_SECONDS:
            measured = measure_profile(self.profile_path(account_id))
            with self._lock:
                self._usage[account_id] = (now, measured)
            cached = (now, measured)
        disk = cached[1]
        if running is None:
            running = self.account_running(account_id)
        ram = 0
        if running:
            for pid in self._account_pids(account_id):
                ram += working_set(pid)
        profile = self.profile_path(account_id)
        return {
            "disk": disk["total"],
            "media": disk["media"],
            "cache": disk["cache"],
            "system": disk["system"],
            "other": disk["other"],
            "ram": ram,
            "path": str(profile),
            "zaloLocation": volume_caption(str(Path.home().drive or "C:")),
        }

    def clear_cache(self, account_id: str) -> None:
        if self.account_running(account_id):
            raise DueError("Đóng tài khoản trước khi xóa bộ nhớ đệm")
        profile = self.profile_path(account_id)
        for relative in _CACHE_RELATIVE:
            target = profile.joinpath(*relative)
            if is_reparse(target) or not target.exists():
                continue
            safe_rmtree(target)
        with self._lock:
            self._usage.pop(account_id, None)
            self.last_error = None

    def open_folder(self, account_id: str) -> None:
        profile = self.profile_path(account_id)
        profile.mkdir(parents=True, exist_ok=True)
        os.startfile(profile)  # type: ignore[attr-defined]

    def rename_account(self, account_id: str, name: str) -> None:
        cleaned = clean_name(name)
        with self._lock:
            account = self._account(account_id)
            account["name"] = cleaned
            self._save_accounts()
            snapshot = dict(account)
            self.last_error = None
        if (self.profile_path(account_id) / "taskbar.ico").is_file():
            icon = self.prepare_taskbar(snapshot)
            exe = self.find_zalo()
            if exe is not None:
                self.stage_binaries()
                launch, dll = self.tools_for(exe)
                self.publish_taskbar(snapshot, exe, dll, launch, icon)

    def remove_account(self, account_id: str) -> None:
        profile = self.profile_path(account_id)
        self.remove_toast_shortcut(account_id)
        self.close_account(account_id)
        with self._lock:
            self.accounts = [item for item in self.accounts if item["id"] != account_id]
            self._save_accounts()
            self.last_error = None
        if profile.exists() or is_reparse(profile):
            safe_rmtree(profile)

    def launch_program(
        self,
        profile: Path,
        program: Path,
        extra: list[str] | None = None,
        *,
        bucket: str = "profiles",
        name: str | None = None,
        icon: Path | None = None,
        keep_pid: bool = False,
    ) -> int:
        self.stage_binaries()
        launch, dll = self.tools_for(program)
        profile.mkdir(parents=True, exist_ok=True)
        account_id = profile.name
        result = profile / "launch.result"
        if result.exists():
            result.unlink()
        command = [
            str(launch),
            "--root",
            str(profile),
            "--id",
            account_id,
            "--exe",
            str(program),
            "--dll",
            str(dll),
        ]
        if name:
            command.extend(["--name", name])
        if icon is not None and icon.is_file():
            command.extend(["--icon", str(icon)])
        if extra:
            command.append("--")
            command.extend(extra)
        run_hidden(command, cwd=str(launch.parent), timeout=60, check=False)
        if not result.exists():
            raise DueError("Trình chạy Due không trả kết quả")
        lines = result.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != "ok":
            detail = lines[1] if len(lines) > 1 else "Không mở được tiến trình"
            raise DueError(detail)
        pid = int(lines[1])
        if bucket == "profiles" and not keep_pid:
            (profile / "due.pid").write_text(str(pid), encoding="utf-8")
        return pid

    def _nudge_show(self, account_id: str, original_pid: int) -> None:
        """Start a second Zalo just long enough for it to call BrowserWindow.show()."""
        profile = self.profile_path(account_id)
        exe = self.find_zalo()
        if exe is None:
            raise DueError("Cài Zalo PC trước khi mở tài khoản")
        with self._lock:
            account = dict(self._account(account_id))
        icon = profile / "taskbar.ico"
        if not icon.is_file():
            icon = self.prepare_taskbar(account)
        new_pid = self.launch_program(profile, exe, name=account["name"], icon=icon, keep_pid=True)
        self.log(f"nudge show {account_id} via {new_pid}")

        def reap() -> None:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if not pid_alive(new_pid):
                    return
                time.sleep(0.2)
            if not pid_alive(new_pid) or new_pid == original_pid:
                return
            extras = descendant_pids(new_pid) - descendant_pids(original_pid)
            terminate_pids(extras)
            self.log(f"stopped extra zalo {new_pid}")

        threading.Thread(target=reap, name="due-nudge", daemon=True).start()

    def _reveal_account(self, account_id: str, pid: int) -> None:
        with self._lock:
            name = self._account(account_id)["name"]
        pids = descendant_pids(pid)
        hide_background_windows(pids)
        hide_blank_frames(pids)
        located = account_hwnd(name)
        hwnd = located[0] if located else None
        if hwnd and user32.IsWindowVisible(hwnd):
            _force_foreground(hwnd)
            return
        self._nudge_show(account_id, pid)
        for _ in range(25):
            time.sleep(0.2)
            located = account_hwnd(name)
            if located and user32.IsWindowVisible(located[0]):
                _force_foreground(located[0])
                self.log(f"revealed {account_id}")
                return
        located = account_hwnd(name)
        if located:
            _force_foreground(located[0])
        raise DueError("Không hiện lại được cửa sổ Zalo")

    def _stash_account(self, account_id: str, pid: int) -> None:
        with self._lock:
            name = self._account(account_id)["name"]
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and pid_alive(pid):
            descendants = descendant_pids(pid)
            hide_background_windows(descendants)
            hide_blank_frames(descendants)
            hide_account_window(name)
            time.sleep(0.25)

    def open_account(self, account_id: str, *, during_update: bool = False, hidden: bool = False) -> None:
        with self._lock:
            if self.job and not during_update:
                raise DueError("Đang cài hoặc cập nhật Zalo")
            self._account(account_id)
        profile = self.profile_path(account_id)
        running = self.running_pid(account_id)
        if running:
            if hidden:
                self._stash_account(account_id, running)
                return
            self._reveal_account(account_id, running)
            return
        exe = self.find_zalo()
        if exe is None:
            raise DueError("Cài Zalo PC trước khi mở tài khoản")
        with self._lock:
            account = dict(self._account(account_id))
        self.ensure_layout(profile, exe)
        icon = self.prepare_taskbar(account)
        self.stage_binaries()
        launch, dll = self.tools_for(exe)
        self.publish_taskbar(account, exe, dll, launch, icon)
        pid = self.launch_program(profile, exe, name=account["name"], icon=icon)
        if hidden:
            self._stash_account(account_id, pid)
        else:
            for _ in range(12):
                if not pid_alive(pid):
                    break
                time.sleep(0.25)
                descendants = descendant_pids(pid)
                hide_blank_frames(descendants)
                if focus_pids(descendants):
                    break
        if not pid_alive(pid):
            note = ""
            hook_log = profile / "hook.log"
            if hook_log.exists():
                lines = hook_log.read_text(encoding="utf-8", errors="replace").splitlines()
                note = " " + lines[-1] if lines else ""
            raise DueError("Cửa sổ Zalo đóng ngay sau khi mở." + note)
        self.log(f"opened {account_id} pid {pid}" + (" hidden" if hidden else ""))

    def close_account(self, account_id: str) -> None:
        profile = self.profile_path(account_id)
        pid = self.read_pid(profile)
        if pid and pid_alive(pid):
            taskkill(pid)
        file = profile / "due.pid"
        if file.exists():
            file.unlink()

    def zalo_pids(self) -> list[int]:
        exe = self.find_zalo()
        if exe is None:
            return []
        root = os.path.normcase(str(self.install_root(exe)))
        found = []
        for pid, _parent, name in iter_processes():
            if "zalo" not in name.lower():
                continue
            image = image_path(pid)
            if image and os.path.normcase(image).startswith(root):
                found.append(pid)
        return found

    def stop_zalo(self) -> None:
        targets: set[int] = set()
        for pid in self.zalo_pids():
            targets.update(descendant_pids(pid))
        terminate_pids(targets)
        leftovers: set[int] = set()
        for pid in self.zalo_pids():
            leftovers.update(descendant_pids(pid))
        terminate_pids(leftovers)
        for account in list(self.accounts):
            file = self.profile_path(account["id"]) / "due.pid"
            if file.exists():
                file.unlink(missing_ok=True)

    def _set_job(self, kind: str, message: str, progress: float | None) -> None:
        with self._lock:
            self.job = {"kind": kind, "message": message, "progress": progress}

    def _clear_job(self, error: str | None = None) -> None:
        with self._lock:
            self.job = None
            self.last_error = error

    def _publish_account(self, account: dict) -> None:
        exe = self.find_zalo()
        if exe is None:
            self.prepare_taskbar(account)
            return
        try:
            self.stage_binaries()
            launch, dll = self.tools_for(exe)
        except DueError:
            self.prepare_taskbar(account)
            return
        icon = self.prepare_taskbar(account)
        self.publish_taskbar(account, exe, dll, launch, icon)

    def start_housekeeping(self) -> None:
        if self._housekeeping:
            return
        self._housekeeping = True
        threading.Thread(target=self._housekeeping_loop, name="due-housekeeping", daemon=True).start()

    def _housekeeping_loop(self) -> None:
        try:
            self._refresh_shortcuts()
        except Exception as exc:  # noqa: BLE001 - keep the desk alive if a shortcut fails
            self.log(f"shortcut refresh failed: {exc}")
        next_check = time.monotonic() + 12
        while True:
            try:
                with self._lock:
                    busy_job = self.job is not None
                if not busy_job:
                    self._stop_foreign_updates()
                    self._tune_accounts()
                    hide_background_windows(set(self.zalo_pids()))
                due = time.monotonic() >= next_check or self._check_requested()
                if due and not busy_job:
                    self._consume_check_request()
                    again_soon = self._maybe_autoupdate()
                    next_check = time.monotonic() + (UPDATE_RETRY_SECONDS if again_soon else UPDATE_CHECK_SECONDS)
            except Exception as exc:  # noqa: BLE001 - a failed check must not stop the loop
                self.log(f"housekeeping failed: {exc}")
                next_check = time.monotonic() + UPDATE_RETRY_SECONDS
            time.sleep(5)

    def _refresh_shortcuts(self) -> None:
        with self._lock:
            accounts = [dict(item) for item in self.accounts]
        for account in accounts:
            self._publish_account(account)

    def _stop_foreign_updates(self) -> None:
        for pid, _parent, name in iter_processes():
            image = image_path(pid) or ""
            if is_foreign_updater(image, name):
                self.log(f"stopped Zalo updater pid {pid}")
                taskkill(pid, tree=Path(image).name.lower() != "zalo.exe")

    def _account_pids(self, account_id: str) -> set[int]:
        root = self.read_pid(self.profile_path(account_id))
        if root is None:
            return set()
        return descendant_pids(root)

    def _tree_busy(self, pids: set[int], front: int | None) -> bool:
        if front is not None and front in pids:
            return True
        for pid in pids:
            image = image_path(pid) or ""
            if Path(image).name.lower() in CALL_PROCESSES:
                return True
        return False

    def _busy_for_update(self) -> bool:
        front = foreground_pid()
        with self._lock:
            accounts = [item["id"] for item in self.accounts]
        for account_id in accounts:
            if not self.account_running(account_id):
                continue
            if self._tree_busy(self._account_pids(account_id), front):
                return True
        return False

    def _check_requested(self) -> bool:
        with self._lock:
            return self._check_soon

    def _consume_check_request(self) -> None:
        with self._lock:
            self._check_soon = False

    def _release_efficiency(self) -> None:
        with self._lock:
            account_ids = list(self._saving)
            self._idle_since.clear()
        for account_id in account_ids:
            for pid in self._account_pids(account_id):
                set_efficiency(pid, False)
            self._mark_saving(account_id, False)
            self._trimmed_at.pop(account_id, None)

    def _tune_accounts(self) -> None:
        with self._lock:
            efficiency = bool(self.settings.get("efficiency", True))
            saving = bool(self._saving)
        if not efficiency:
            if saving:
                self._release_efficiency()
            return
        now = time.monotonic()
        front = foreground_pid()
        with self._lock:
            accounts = [item["id"] for item in self.accounts]
        for account_id in accounts:
            if not self.account_running(account_id):
                self._idle_since.pop(account_id, None)
                self._trimmed_at.pop(account_id, None)
                self._mark_saving(account_id, False)
                continue
            pids = self._account_pids(account_id)
            if self._tree_busy(pids, front):
                self._idle_since[account_id] = now
                if account_id in self._saving:
                    for pid in pids:
                        set_efficiency(pid, False)
                    self._mark_saving(account_id, False)
                    self._trimmed_at.pop(account_id, None)
                continue
            self._idle_since.setdefault(account_id, now)
            if now - self._idle_since[account_id] < IDLE_AFTER_SECONDS:
                continue
            with self._lock:
                if not self.settings.get("efficiency", True):
                    return
            if account_id in self._saving and now - self._trimmed_at.get(account_id, 0) < TRIM_EVERY_SECONDS:
                continue
            for pid in pids:
                set_efficiency(pid, True)
            self._trimmed_at[account_id] = now
            if account_id not in self._saving:
                self._mark_saving(account_id, True)
                self.log(f"efficiency {account_id}")

    def _mark_saving(self, account_id: str, enabled: bool) -> None:
        with self._lock:
            if enabled:
                self._saving.add(account_id)
            else:
                self._saving.discard(account_id)

    def _remember_latest(self, current: str, available: str) -> bool:
        newer = version_parts(available)[:3] > version_parts(current)[:3]
        with self._lock:
            self._latest = available if newer else None
        return newer

    def _open_account_ids(self) -> list[str]:
        with self._lock:
            account_ids = [item["id"] for item in self.accounts]
        return [account_id for account_id in account_ids if self.account_running(account_id)]

    def _reopen_accounts(self, account_ids: list[str]) -> None:
        for account_id in account_ids:
            try:
                self.open_account(account_id, during_update=True)
            except DueError as exc:
                self.log(f"reopen {account_id} failed: {exc}")
                with self._lock:
                    self.last_error = str(exc)

    def _maybe_autoupdate(self) -> bool:
        if self.find_zalo() is None:
            with self._lock:
                self._latest = None
            return False
        try:
            url = resolve_setup_url()
        except Exception as exc:  # noqa: BLE001 - offline checks retry later
            self.log(f"update check failed: {exc}")
            return True
        available = re.search(r"ZaloSetup-(\d+(?:\.\d+)+)", url, re.I)
        if not available:
            return True
        current = self.zalo_version()
        if current is None:
            return False
        if not self._remember_latest(current, available.group(1)):
            return False
        with self._lock:
            auto = bool(self.settings.get("autoUpdate", True))
        if not auto:
            return False
        if self._busy_for_update():
            return True
        self.log(f"auto-update {current} -> {available.group(1)}")
        try:
            self.start_install(update=True)
        except DueError:
            return True
        return False

    def start_install(self, *, update: bool) -> None:
        with self._lock:
            if self.job:
                raise DueError("Đang có một lượt cài khác")
            self.job = {"kind": "update" if update else "install", "message": "Đang nối tới Zalo", "progress": None}
            self.last_error = None
        thread = threading.Thread(target=self._install_worker, args=(update,), daemon=True)
        thread.start()

    def _install_worker(self, update: bool) -> None:
        reopen: list[str] = []
        try:
            url = resolve_setup_url()
            available = re.search(r"ZaloSetup-(\d+(?:\.\d+)+)", url, re.I)
            available_text = available.group(1) if available else None
            current = self.zalo_version()
            if update and current and available_text:
                current_key = version_parts(current)[:3]
                available_key = version_parts(available_text)[:3]
                if current_key and available_key and current_key >= available_key:
                    self._remember_latest(current, available_text)
                    self._clear_job()
                    with self._lock:
                        self.last_error = None
                    self._set_job("update", f"Zalo {available_text} đang là bản mới.", 1)
                    time.sleep(4)
                    self._clear_job()
                    return
            self._set_job("update" if update else "install", "Đang tải bộ cài Zalo", 0)
            if update or self.find_zalo() is not None:
                if update:
                    reopen = self._open_account_ids()
                self._set_job("update" if update else "install", "Đang đóng Zalo để cài", None)
                self.stop_zalo()
            setup = self.cache / "ZaloSetup.exe"
            self._download(url, setup)
            self._set_job("update" if update else "install", "Đang cài Zalo", None)
            self._run_setup(setup)
            self.adopt_zalo()
            self.retire_external_zalo()
            if self.find_zalo() is None:
                raise DueError("Cài xong nhưng chưa thấy Zalo trên máy")
            self.log(f"installed {self.zalo_version()}")
            with self._lock:
                self._latest = None
            if reopen:
                self._set_job("update", "Đang mở lại Zalo", None)
                self._reopen_accounts(reopen)
            self._clear_job()
        except Exception as exc:  # noqa: BLE001 - surface any install failure in the desk
            self.log(f"install failed: {exc}")
            self._clear_job(str(exc))
            if reopen:
                self._reopen_accounts(reopen)

    def _download(self, url: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp = dest.with_suffix(".part")
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=60) as response, temp.open("wb") as handle:
                total = int(response.headers.get("Content-Length") or 0)
                read = 0
                while True:
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    read += len(chunk)
                    if total:
                        self._set_job(self.job["kind"] if self.job else "install", "Đang tải bộ cài Zalo", read / total)
        except urllib.error.URLError as exc:
            raise DueError("Không tải được bộ cài Zalo") from exc
        if temp.stat().st_size < 1_000_000:
            temp.unlink(missing_ok=True)
            raise DueError("File tải về không phải bộ cài Zalo")
        with temp.open("rb") as handle:
            if handle.read(2) != b"MZ":
                temp.unlink(missing_ok=True)
                raise DueError("File tải về không phải chương trình cài đặt")
        temp.replace(dest)

    def _run_setup(self, setup: Path) -> None:
        silent = run_hidden([str(setup), "/S"], timeout=900, check=False)
        for _ in range(30):
            if self.find_zalo() is not None:
                return
            time.sleep(1)
        if silent.returncode == 0 and self.find_zalo() is not None:
            return
        self._set_job("install", "Mở trình cài Zalo", None)
        subprocess.run([str(setup)], timeout=1800, check=False)
        for _ in range(15):
            if self.find_zalo() is not None:
                return
            time.sleep(1)
