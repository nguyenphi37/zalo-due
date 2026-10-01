// Loaded into Zalo so each Due account gets its own data folders.
// The Zalo install directory is not redirected; updates stay on one copy.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <knownfolders.h>
#include <shlobj.h>
#include <detours.h>
#include <propsys.h>
#include <propkey.h>
#include <propvarutil.h>
#include "Inject.hpp"

#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <cwctype>
#include <string>

extern "C" HRESULT WINAPI SHGetPropertyStoreForWindow(HWND hwnd, REFIID riid, void** ppv);

#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "propsys.lib")

namespace {

wchar_t g_profileId[64];
wchar_t g_profileRoot[MAX_PATH];
wchar_t g_appData[MAX_PATH];
wchar_t g_localAppData[MAX_PATH];
wchar_t g_documents[MAX_PATH];
wchar_t g_downloads[MAX_PATH];
wchar_t g_localLow[MAX_PATH];
wchar_t g_logPath[MAX_PATH];
wchar_t g_dllPath[1024];
wchar_t g_accountName[80];
wchar_t g_iconFile[1024];
wchar_t g_appId[80];
HICON g_iconBig = nullptr;
HICON g_iconSmall = nullptr;
using SetAppUserModelID_t = HRESULT(WINAPI*)(PCWSTR);
SetAppUserModelID_t TrueSetAppUserModelID = nullptr;
bool g_debug = false;
thread_local bool g_inLog = false;
CRITICAL_SECTION g_logLock;
bool g_logReady = false;

using SHGetKnownFolderPath_t = HRESULT(WINAPI*)(REFKNOWNFOLDERID, DWORD, HANDLE, PWSTR*);
using SHGetFolderPathW_t = HRESULT(WINAPI*)(HWND, int, HANDLE, DWORD, LPWSTR);
using CreateMutexW_t = HANDLE(WINAPI*)(LPSECURITY_ATTRIBUTES, BOOL, LPCWSTR);
using CreateMutexExW_t = HANDLE(WINAPI*)(LPSECURITY_ATTRIBUTES, LPCWSTR, DWORD, DWORD);
using OpenMutexW_t = HANDLE(WINAPI*)(DWORD, BOOL, LPCWSTR);
using CreateFileW_t = HANDLE(WINAPI*)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
using CreateProcessW_t = BOOL(WINAPI*)(LPCWSTR, LPWSTR, LPSECURITY_ATTRIBUTES, LPSECURITY_ATTRIBUTES,
                                       BOOL, DWORD, LPVOID, LPCWSTR, LPSTARTUPINFOW, LPPROCESS_INFORMATION);
using ShellNotify_t = BOOL(WINAPI*)(DWORD, void*);

SHGetKnownFolderPath_t TrueSHGetKnownFolderPath = nullptr;
SHGetFolderPathW_t TrueSHGetFolderPathW = nullptr;
CreateMutexW_t TrueCreateMutexW = nullptr;
CreateMutexExW_t TrueCreateMutexExW = nullptr;
OpenMutexW_t TrueOpenMutexW = nullptr;
CreateFileW_t TrueCreateFileW = nullptr;
CreateProcessW_t TrueCreateProcessW = nullptr;
ShellNotify_t TrueShell_NotifyIconW = nullptr;
ShellNotify_t TrueShell_NotifyIconA = nullptr;
bool g_loggedTray = false;

void Log(const wchar_t* message) {
    if (!g_logReady || g_logPath[0] == 0 || g_inLog) {
        return;
    }
    g_inLog = true;
    EnterCriticalSection(&g_logLock);
    HANDLE file = CreateFileW(g_logPath, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
                              nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file != INVALID_HANDLE_VALUE) {
        DWORD written = 0;
        int bytes = WideCharToMultiByte(CP_UTF8, 0, message, -1, nullptr, 0, nullptr, nullptr);
        if (bytes > 1) {
            std::string utf8(static_cast<size_t>(bytes), '\0');
            WideCharToMultiByte(CP_UTF8, 0, message, -1, utf8.data(), bytes, nullptr, nullptr);
            utf8.pop_back();
            utf8.append("\r\n");
            WriteFile(file, utf8.data(), static_cast<DWORD>(utf8.size()), &written, nullptr);
        }
        CloseHandle(file);
    }
    LeaveCriticalSection(&g_logLock);
    g_inLog = false;
}

void Logf(const wchar_t* fmt, ...) {
    wchar_t buffer[1024];
    va_list args;
    va_start(args, fmt);
    _vsnwprintf_s(buffer, _TRUNCATE, fmt, args);
    va_end(args);
    Log(buffer);
}

bool CopyEnv(const wchar_t* name, wchar_t* dest, size_t destCount, bool required) {
    DWORD n = GetEnvironmentVariableW(name, dest, static_cast<DWORD>(destCount));
    if (n == 0 || n >= destCount) {
        dest[0] = 0;
        if (required) {
            Logf(L"missing env %s", name);
        }
        return !required;
    }
    return true;
}

bool AllowedProfileRoot(const wchar_t* root) {
    std::wstring lower(root);
    for (wchar_t& ch : lower) {
        ch = static_cast<wchar_t>(towlower(ch));
    }
    return lower.find(L"\\data\\profiles\\") != std::wstring::npos ||
           lower.find(L"\\data\\selftest\\") != std::wstring::npos ||
           lower.find(L"\\due\\profiles\\") != std::wstring::npos ||
           lower.find(L"\\due\\selftest\\") != std::wstring::npos;
}

bool InDueProfile(const wchar_t* path) {
    if (path == nullptr) {
        return false;
    }
    return FindStringOrdinal(FIND_FROMSTART, path, -1, L"\\data\\profiles\\", -1, TRUE) != -1 ||
           FindStringOrdinal(FIND_FROMSTART, path, -1, L"\\data\\selftest\\", -1, TRUE) != -1 ||
           FindStringOrdinal(FIND_FROMSTART, path, -1, L"\\Due\\profiles\\", -1, TRUE) != -1 ||
           FindStringOrdinal(FIND_FROMSTART, path, -1, L"\\Due\\selftest\\", -1, TRUE) != -1;
}

bool MarkerAt(const std::wstring& hay, size_t pos, const wchar_t* marker) {
    size_t n = wcslen(marker);
    if (pos + n > hay.size()) {
        return false;
    }
    if (_wcsnicmp(hay.c_str() + pos, marker, n) != 0) {
        return false;
    }
    if (pos + n == hay.size()) {
        return true;
    }
    wchar_t next = hay[pos + n];
    return next == L'\\' || next == L'/';
}

bool RewriteDataPath(const std::wstring& in, std::wstring& out) {
    if (in.empty() || InDueProfile(in.c_str())) {
        return false;
    }
    const wchar_t* markers[] = {L"\\Zalo Received Files", L"\\ZaloData", L"\\ZaloPC"};
    const wchar_t* roots[] = {g_documents, g_appData, g_localAppData};
    for (int i = 0; i < 3; ++i) {
        if (roots[i][0] == 0) {
            continue;
        }
        size_t n = wcslen(markers[i]);
        for (size_t pos = 0; pos + n <= in.size(); ++pos) {
            if (!MarkerAt(in, pos, markers[i])) {
                continue;
            }
            out.assign(roots[i]);
            out.append(in, pos, std::wstring::npos);
            return true;
        }
    }
    return false;
}

bool ShouldSuffixMutex(LPCWSTR name) {
    if (name == nullptr || name[0] == 0 || g_profileId[0] == 0) {
        return false;
    }
    return FindStringOrdinal(FIND_FROMSTART, name, -1, L"singleton", -1, TRUE) != -1;
}

const wchar_t* Suffixed(LPCWSTR name, std::wstring& storage) {
    if (!ShouldSuffixMutex(name)) {
        return name;
    }
    storage.assign(name);
    storage.append(L".due.");
    storage.append(g_profileId);
    if (g_debug) {
        Logf(L"mutex %s", storage.c_str());
    }
    return storage.c_str();
}

bool EndsWithExe(LPCWSTR value) {
    if (value == nullptr) {
        return false;
    }
    size_t length = wcslen(value);
    return length >= 8 && _wcsicmp(value + length - 8, L"Zalo.exe") == 0;
}

bool HasText(LPCWSTR value, const wchar_t* needle) {
    if (value == nullptr || needle == nullptr || needle[0] == 0) {
        return false;
    }
    return FindStringOrdinal(FIND_FROMSTART, value, -1, needle, -1, TRUE) != -1;
}

bool IsZaloSelfUpdate(LPCWSTR application, LPCWSTR command) {
    const wchar_t* needles[] = {
        L"ZaloSetup", L"\\update.exe", L"Uninstall Zalo", L"\\zalo-updater\\", L"--relaunch-silently",
        L"\\Zalo\\Zalo.exe",
    };
    for (const wchar_t* needle : needles) {
        if (HasText(application, needle) || HasText(command, needle)) {
            return true;
        }
    }
    return false;
}

bool LooksLikeZaloImage(LPCWSTR application, LPCWSTR command) {
    if (EndsWithExe(application)) {
        return true;
    }
    if (command == nullptr) {
        return false;
    }
    for (const wchar_t* cursor = command; *cursor != 0; ++cursor) {
        if (_wcsnicmp(cursor, L"Zalo.exe", 8) != 0) {
            continue;
        }
        wchar_t before = cursor == command ? L'\\' : cursor[-1];
        wchar_t after = cursor[8];
        if ((before == L'\\' || before == L'"') && (after == 0 || after == L'"' || after == L' ')) {
            return true;
        }
    }
    return false;
}

const wchar_t* RedirectKnown(REFKNOWNFOLDERID id) {
    if (IsEqualGUID(id, FOLDERID_RoamingAppData)) {
        return g_appData;
    }
    if (IsEqualGUID(id, FOLDERID_LocalAppData)) {
        return g_localAppData;
    }
    if (IsEqualGUID(id, FOLDERID_Documents)) {
        return g_documents;
    }
    if (g_downloads[0] != 0 && IsEqualGUID(id, FOLDERID_Downloads)) {
        return g_downloads;
    }
    if (g_localLow[0] != 0 && IsEqualGUID(id, FOLDERID_LocalAppDataLow)) {
        return g_localLow;
    }
    return nullptr;
}

HRESULT ReturnAlloc(const wchar_t* path, PWSTR* out) {
    size_t chars = wcslen(path) + 1;
    PWSTR buffer = static_cast<PWSTR>(CoTaskMemAlloc(chars * sizeof(wchar_t)));
    if (buffer == nullptr) {
        return E_OUTOFMEMORY;
    }
    memcpy(buffer, path, chars * sizeof(wchar_t));
    *out = buffer;
    return S_OK;
}

HRESULT WINAPI MineSHGetKnownFolderPath(REFKNOWNFOLDERID rfid, DWORD flags, HANDLE token, PWSTR* path) {
    const wchar_t* redirected = RedirectKnown(rfid);
    if (redirected != nullptr && redirected[0] != 0) {
        (void)flags;
        (void)token;
        return ReturnAlloc(redirected, path);
    }
    return TrueSHGetKnownFolderPath(rfid, flags, token, path);
}

HRESULT WINAPI MineSHGetFolderPathW(HWND hwnd, int csidl, HANDLE token, DWORD flags, LPWSTR path) {
    int id = csidl & 0x00FF;
    const wchar_t* redirected = nullptr;
    if (id == CSIDL_APPDATA) {
        redirected = g_appData;
    } else if (id == CSIDL_LOCAL_APPDATA) {
        redirected = g_localAppData;
    } else if (id == CSIDL_MYDOCUMENTS || id == CSIDL_PERSONAL) {
        redirected = g_documents;
    }
    if (redirected == nullptr || redirected[0] == 0) {
        return TrueSHGetFolderPathW(hwnd, csidl, token, flags, path);
    }
    if (wcslen(redirected) >= MAX_PATH) {
        Log(L"redirected folder path is too long");
        TerminateProcess(GetCurrentProcess(), 3);
    }
    wcscpy_s(path, MAX_PATH, redirected);
    return S_OK;
}

HANDLE WINAPI MineCreateMutexW(LPSECURITY_ATTRIBUTES security, BOOL owner, LPCWSTR name) {
    std::wstring storage;
    return TrueCreateMutexW(security, owner, Suffixed(name, storage));
}

HANDLE WINAPI MineCreateMutexExW(LPSECURITY_ATTRIBUTES security, LPCWSTR name, DWORD flags, DWORD access) {
    std::wstring storage;
    return TrueCreateMutexExW(security, Suffixed(name, storage), flags, access);
}

HANDLE WINAPI MineOpenMutexW(DWORD access, BOOL inherit, LPCWSTR name) {
    std::wstring storage;
    return TrueOpenMutexW(access, inherit, Suffixed(name, storage));
}

HANDLE WINAPI MineCreateFileW(LPCWSTR name, DWORD access, DWORD share, LPSECURITY_ATTRIBUTES security,
                              DWORD disposition, DWORD flags, HANDLE templateFile) {
    if (g_inLog || name == nullptr) {
        return TrueCreateFileW(name, access, share, security, disposition, flags, templateFile);
    }
    std::wstring rewritten;
    if (!RewriteDataPath(name, rewritten)) {
        return TrueCreateFileW(name, access, share, security, disposition, flags, templateFile);
    }
    if (g_debug) {
        Logf(L"file %s", rewritten.c_str());
    }
    return TrueCreateFileW(rewritten.c_str(), access, share, security, disposition, flags, templateFile);
}

BOOL WINAPI MineCreateProcessW(LPCWSTR application, LPWSTR command, LPSECURITY_ATTRIBUTES processAttributes,
                               LPSECURITY_ATTRIBUTES threadAttributes, BOOL inherit, DWORD flags, LPVOID environment,
                               LPCWSTR directory, LPSTARTUPINFOW startup, LPPROCESS_INFORMATION information) {
    if (IsZaloSelfUpdate(application, command)) {
        Log(L"blocked Zalo self-update");
        SetLastError(ERROR_ACCESS_DENIED);
        return FALSE;
    }
    if (startup != nullptr) {
        startup->dwFlags |= STARTF_FORCEOFFFEEDBACK;
    }
    if (g_dllPath[0] == 0) {
        return TrueCreateProcessW(application, command, processAttributes, threadAttributes, inherit, flags,
                                   environment, directory, startup, information);
    }
    BOOL ok = TrueCreateProcessW(application, command, processAttributes, threadAttributes, inherit,
                                  flags | CREATE_SUSPENDED, environment, directory, startup, information);
    if (!ok) {
        return FALSE;
    }
    if (!InjectDll(information->hProcess, g_dllPath)) {
        DWORD error = GetLastError();
        Logf(L"child inject failed (%lu), launching with inherited Due profile environment", error);
        if ((flags & CREATE_SUSPENDED) == 0) {
            ResumeThread(information->hThread);
        }
        return TRUE;
    }
    if ((flags & CREATE_SUSPENDED) == 0) {
        ResumeThread(information->hThread);
    }
    return TRUE;
}

BOOL WINAPI MineShell_NotifyIconW(DWORD, void*) {
    if (!g_loggedTray) {
        g_loggedTray = true;
        Log(L"suppressed tray icon");
    }
    return TRUE;
}

BOOL WINAPI MineShell_NotifyIconA(DWORD, void*) {
    return MineShell_NotifyIconW(0, nullptr);
}

void FailClosed(const wchar_t* reason) {
    Log(reason);
    TerminateProcess(GetCurrentProcess(), 4);
}

HRESULT WINAPI MineSetAppUserModelID(PCWSTR) {
    if (TrueSetAppUserModelID == nullptr || g_appId[0] == 0) {
        return S_OK;
    }
    return TrueSetAppUserModelID(g_appId);
}

void StampWindow(HWND hwnd) {
    IPropertyStore* store = nullptr;
    if (SUCCEEDED(SHGetPropertyStoreForWindow(hwnd, IID_PPV_ARGS(&store))) && store != nullptr) {
        PROPVARIANT value{};
        value.vt = VT_LPWSTR;
        value.pwszVal = g_appId;
        store->SetValue(PKEY_AppUserModel_ID, value);
        store->Commit();
        store->Release();
    }
    if (g_iconBig != nullptr) {
        SendMessageW(hwnd, WM_SETICON, ICON_BIG, reinterpret_cast<LPARAM>(g_iconBig));
    }
    if (g_iconSmall != nullptr) {
        SendMessageW(hwnd, WM_SETICON, ICON_SMALL, reinterpret_cast<LPARAM>(g_iconSmall));
    }
    if (g_accountName[0] == 0) {
        return;
    }
    wchar_t title[512];
    if (GetWindowTextW(hwnd, title, 512) <= 0 || title[0] == 0) {
        return;
    }
    const wchar_t* body = title;
    size_t nameLength = wcslen(g_accountName);
    if (nameLength > 0 && wcsncmp(title, g_accountName, nameLength) == 0) {
        body = title + nameLength;
        while (*body == L' ' || *body == L'-' || *body == L'\u00b7' || *body == L'\u00c2' || *body == L'\u2022') {
            ++body;
        }
    }
    if (*body == 0) {
        body = L"Zalo";
    }
    wchar_t next[600];
    _snwprintf_s(next, _TRUNCATE, L"%s - %s", g_accountName, body);
    if (wcscmp(title, next) == 0) {
        return;
    }
    SetWindowTextW(hwnd, next);
}

constexpr wchar_t kCloseProp[] = L"Due.OrigProc";
thread_local bool g_inClose = false;
HHOOK g_callHook = nullptr;
DWORD g_hookedThreads[8]{};
int g_hookedCount = 0;

bool IsBlankHelperTitle(const wchar_t* title) {
    if (title == nullptr || title[0] == 0) {
        return false;
    }
    return wcsstr(title, L"SQLite") != nullptr || wcsstr(title, L"sqlite") != nullptr ||
           wcsstr(title, L"Shared Worker") != nullptr || wcsstr(title, L"Service Worker") != nullptr ||
           wcsstr(title, L"Dedicated Worker") != nullptr;
}

bool IsBlankHelperWindow(HWND hwnd) {
    wchar_t title[512];
    if (GetWindowTextW(hwnd, title, 512) <= 0) {
        return false;
    }
    return IsBlankHelperTitle(title);
}

using ShowWindow_t = BOOL(WINAPI*)(HWND, int);
ShowWindow_t TrueShowWindow = nullptr;

BOOL WINAPI MineShowWindow(HWND hwnd, int cmd) {
    if (cmd != SW_HIDE && IsBlankHelperWindow(hwnd)) {
        return TrueShowWindow(hwnd, SW_HIDE);
    }
    return TrueShowWindow(hwnd, cmd);
}

bool IsAccountWindow(HWND hwnd) {
    wchar_t title[512];
    if (GetWindowTextW(hwnd, title, 512) <= 0) {
        return false;
    }
    if (IsBlankHelperTitle(title)) {
        return false;
    }
    return wcsstr(title, L" - Zalo") != nullptr;
}

bool InCloseButton(HWND root, POINT pt) {
    RECT rect{};
    if (!GetWindowRect(root, &rect)) {
        return false;
    }
    UINT dpi = 96;
    auto getDpi = reinterpret_cast<UINT(WINAPI*)(HWND)>(GetProcAddress(GetModuleHandleW(L"user32.dll"), "GetDpiForWindow"));
    if (getDpi != nullptr) {
        dpi = getDpi(root);
    }
    if (dpi < 96) {
        dpi = 96;
    }
    const int width = MulDiv(56, static_cast<int>(dpi), 96);
    const int height = MulDiv(48, static_cast<int>(dpi), 96);
    return pt.x >= rect.right - width && pt.x < rect.right && pt.y >= rect.top && pt.y < rect.top + height;
}

LRESULT CALLBACK MouseHook(int code, WPARAM wp, LPARAM lp) {
    if (code == HC_ACTION && (wp == WM_LBUTTONUP || wp == WM_NCLBUTTONUP)) {
        auto* info = reinterpret_cast<MOUSEHOOKSTRUCT*>(lp);
        HWND root = GetAncestor(info->hwnd, GA_ROOT);
        if (root != nullptr && IsAccountWindow(root) && InCloseButton(root, info->pt)) {
            PostMessageW(root, WM_CLOSE, 0, 0);
        }
    }
    return CallNextHookEx(nullptr, code, wp, lp);
}

UINT DueCloseMessage() {
    static UINT message = RegisterWindowMessageW(L"Due.HookClose");
    return message;
}

LRESULT CALLBACK MineCloseProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    auto original = reinterpret_cast<WNDPROC>(GetPropW(hwnd, kCloseProp));
    if (original == nullptr) {
        return DefWindowProcW(hwnd, msg, wp, lp);
    }
    const bool closing = msg == WM_CLOSE || (msg == WM_SYSCOMMAND && (wp & 0xFFF0) == SC_CLOSE);
    if (!closing) {
        return CallWindowProcW(original, hwnd, msg, wp, lp);
    }
    if (g_inClose) {
        return CallWindowProcW(original, hwnd, msg, wp, lp);
    }
    g_inClose = true;
    LRESULT result = CallWindowProcW(original, hwnd, msg, wp, lp);
    if (IsWindow(hwnd) && IsWindowVisible(hwnd)) {
        ShowWindow(hwnd, SW_HIDE);
    }
    g_inClose = false;
    return result;
}

LRESULT CALLBACK CallHook(int code, WPARAM wp, LPARAM lp) {
    if (code == HC_ACTION) {
        auto* msg = reinterpret_cast<CWPSTRUCT*>(lp);
        if (msg->message == DueCloseMessage()) {
            auto current = reinterpret_cast<WNDPROC>(GetWindowLongPtrW(msg->hwnd, GWLP_WNDPROC));
            if (current != nullptr && current != MineCloseProc) {
                SetPropW(msg->hwnd, kCloseProp, current);
                SetWindowLongPtrW(msg->hwnd, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(MineCloseProc));
            }
        }
    }
    return CallNextHookEx(g_callHook, code, wp, lp);
}

void WatchClose(HWND hwnd) {
    auto current = reinterpret_cast<WNDPROC>(GetWindowLongPtrW(hwnd, GWLP_WNDPROC));
    if (current == MineCloseProc) {
        return;
    }
    DWORD threadId = GetWindowThreadProcessId(hwnd, nullptr);
    bool known = false;
    for (int i = 0; i < g_hookedCount; ++i) {
        if (g_hookedThreads[i] == threadId) {
            known = true;
            break;
        }
    }
    if (!known && g_hookedCount < 8) {
        HMODULE module = nullptr;
        GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           reinterpret_cast<LPCWSTR>(&CallHook), &module);
        if (SetWindowsHookExW(WH_CALLWNDPROC, CallHook, module, threadId) != nullptr) {
            SetWindowsHookExW(WH_MOUSE, MouseHook, module, threadId);
            g_hookedThreads[g_hookedCount++] = threadId;
        }
    }
    SendMessageW(hwnd, DueCloseMessage(), 0, 0);
}

BOOL CALLBACK BrandWindow(HWND hwnd, LPARAM) {
    DWORD pid = 0;
    GetWindowThreadProcessId(hwnd, &pid);
    if (pid != GetCurrentProcessId() || !IsWindowVisible(hwnd) || GetWindow(hwnd, GW_OWNER) != nullptr) {
        return TRUE;
    }
    wchar_t cls[64];
    if (GetClassNameW(hwnd, cls, 64) == 0 || wcsstr(cls, L"Chrome_WidgetWin") == nullptr) {
        return TRUE;
    }
    wchar_t title[512];
    if (GetWindowTextW(hwnd, title, 512) > 0 && IsBlankHelperTitle(title)) {
        ShowWindow(hwnd, SW_HIDE);
        return TRUE;
    }
    StampWindow(hwnd);
    RECT rect{};
    if (GetWindowRect(hwnd, &rect)) {
        const int area = (rect.right - rect.left) * (rect.bottom - rect.top);
        if (area >= 320 * 200) {
            WatchClose(hwnd);
        }
    }
    return TRUE;
}

DWORD WINAPI TaskbarThread(LPVOID) {
    Sleep(700);
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    for (;;) {
        EnumWindows(BrandWindow, 0);
        Sleep(1000);
    }
}

void StartTaskbarIdentity() {
    if (!CopyEnv(L"DUE_ACCOUNT_NAME", g_accountName, _countof(g_accountName), false) || g_accountName[0] == 0) {
        return;
    }
    CopyEnv(L"DUE_ACCOUNT_ICON", g_iconFile, _countof(g_iconFile), false);
    _snwprintf_s(g_appId, _TRUNCATE, L"Due.Zalo.%s", g_profileId);
    HMODULE shell = LoadLibraryW(L"shell32.dll");
    if (shell != nullptr) {
        TrueSetAppUserModelID = reinterpret_cast<SetAppUserModelID_t>(GetProcAddress(shell, "SetCurrentProcessExplicitAppUserModelID"));
    }
    if (TrueSetAppUserModelID != nullptr) {
        DetourTransactionBegin();
        DetourUpdateThread(GetCurrentThread());
        DetourAttach(&(PVOID&)TrueSetAppUserModelID, MineSetAppUserModelID);
        if (DetourTransactionCommit() == NO_ERROR) {
            TrueSetAppUserModelID(g_appId);
        }
    }
    if (g_iconFile[0] != 0) {
        g_iconBig = static_cast<HICON>(LoadImageW(nullptr, g_iconFile, IMAGE_ICON, 32, 32, LR_LOADFROMFILE));
        g_iconSmall = static_cast<HICON>(LoadImageW(nullptr, g_iconFile, IMAGE_ICON, 16, 16, LR_LOADFROMFILE));
    }
    HANDLE thread = CreateThread(nullptr, 0, TaskbarThread, nullptr, 0, nullptr);
    if (thread != nullptr) {
        CloseHandle(thread);
    }
}

void InstallHooks() {
    wchar_t debug[8];
    if (CopyEnv(L"DUE_DEBUG", debug, 8, false) && debug[0] == L'1') {
        g_debug = true;
    }
    if (!CopyEnv(L"DUE_PROFILE_ID", g_profileId, _countof(g_profileId), true) ||
        !CopyEnv(L"DUE_PROFILE_ROOT", g_profileRoot, _countof(g_profileRoot), true) ||
        !CopyEnv(L"DUE_APP_DATA", g_appData, _countof(g_appData), true) ||
        !CopyEnv(L"DUE_LOCAL_APP_DATA", g_localAppData, _countof(g_localAppData), true) ||
        !CopyEnv(L"DUE_DOCUMENTS", g_documents, _countof(g_documents), true)) {
        FailClosed(L"Due profile environment is incomplete");
        return;
    }
    CopyEnv(L"DUE_DOWNLOADS", g_downloads, _countof(g_downloads), false);
    CopyEnv(L"DUE_LOCAL_LOW", g_localLow, _countof(g_localLow), false);
    if (!AllowedProfileRoot(g_profileRoot) || !AllowedProfileRoot(g_appData)) {
        FailClosed(L"refusing profile outside Due");
        return;
    }
    _snwprintf_s(g_logPath, _TRUNCATE, L"%s\\hook.log", g_profileRoot);

    HMODULE self = nullptr;
    g_dllPath[0] = 0;
    if (GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           reinterpret_cast<LPCWSTR>(&InstallHooks), &self)) {
        if (GetModuleFileNameW(self, g_dllPath, static_cast<DWORD>(_countof(g_dllPath))) == 0) {
            g_dllPath[0] = 0;
        }
    }

    TrueSHGetKnownFolderPath = SHGetKnownFolderPath;
    TrueSHGetFolderPathW = SHGetFolderPathW;
    HMODULE kernelbase = GetModuleHandleW(L"kernelbase.dll");
    if (kernelbase != nullptr) {
        TrueCreateMutexW = reinterpret_cast<CreateMutexW_t>(GetProcAddress(kernelbase, "CreateMutexW"));
        TrueCreateMutexExW = reinterpret_cast<CreateMutexExW_t>(GetProcAddress(kernelbase, "CreateMutexExW"));
        TrueOpenMutexW = reinterpret_cast<OpenMutexW_t>(GetProcAddress(kernelbase, "OpenMutexW"));
        TrueCreateFileW = reinterpret_cast<CreateFileW_t>(GetProcAddress(kernelbase, "CreateFileW"));
        TrueCreateProcessW = reinterpret_cast<CreateProcessW_t>(GetProcAddress(kernelbase, "CreateProcessW"));
    }
    if (TrueCreateMutexW == nullptr) {
        TrueCreateMutexW = CreateMutexW;
    }
    if (TrueCreateMutexExW == nullptr) {
        TrueCreateMutexExW = CreateMutexExW;
    }
    if (TrueOpenMutexW == nullptr) {
        TrueOpenMutexW = OpenMutexW;
    }
    if (TrueCreateFileW == nullptr) {
        TrueCreateFileW = CreateFileW;
    }
    if (TrueCreateProcessW == nullptr) {
        TrueCreateProcessW = CreateProcessW;
    }
    TrueShowWindow = reinterpret_cast<ShowWindow_t>(GetProcAddress(GetModuleHandleW(L"user32.dll"), "ShowWindow"));
    if (TrueShowWindow == nullptr) {
        TrueShowWindow = ShowWindow;
    }
    HMODULE shell32 = GetModuleHandleW(L"shell32.dll");
    if (shell32 == nullptr) {
        shell32 = LoadLibraryW(L"shell32.dll");
    }
    if (shell32 != nullptr) {
        TrueShell_NotifyIconW = reinterpret_cast<ShellNotify_t>(GetProcAddress(shell32, "Shell_NotifyIconW"));
        TrueShell_NotifyIconA = reinterpret_cast<ShellNotify_t>(GetProcAddress(shell32, "Shell_NotifyIconA"));
    }

    DetourTransactionBegin();
    DetourUpdateThread(GetCurrentThread());
    DetourAttach(&(PVOID&)TrueSHGetKnownFolderPath, MineSHGetKnownFolderPath);
    DetourAttach(&(PVOID&)TrueSHGetFolderPathW, MineSHGetFolderPathW);
    DetourAttach(&(PVOID&)TrueCreateMutexW, MineCreateMutexW);
    DetourAttach(&(PVOID&)TrueCreateMutexExW, MineCreateMutexExW);
    DetourAttach(&(PVOID&)TrueOpenMutexW, MineOpenMutexW);
    DetourAttach(&(PVOID&)TrueCreateFileW, MineCreateFileW);
    if (g_dllPath[0] != 0) {
        DetourAttach(&(PVOID&)TrueCreateProcessW, MineCreateProcessW);
    }
    if (TrueShell_NotifyIconW != nullptr) {
        DetourAttach(&(PVOID&)TrueShell_NotifyIconW, MineShell_NotifyIconW);
    }
    if (TrueShell_NotifyIconA != nullptr) {
        DetourAttach(&(PVOID&)TrueShell_NotifyIconA, MineShell_NotifyIconA);
    }
    DetourAttach(&(PVOID&)TrueShowWindow, MineShowWindow);
    LONG error = DetourTransactionCommit();
    if (error != NO_ERROR) {
        Logf(L"DetourTransactionCommit failed: %ld", error);
        TerminateProcess(GetCurrentProcess(), 5);
    }
    Log(L"hooks ready");
    StartTaskbarIdentity();
}

}  // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (DetourIsHelperProcess()) {
        return TRUE;
    }
    if (reason == DLL_PROCESS_ATTACH) {
        InitializeCriticalSection(&g_logLock);
        g_logReady = true;
        DisableThreadLibraryCalls(instance);
        DetourRestoreAfterWith();
        InstallHooks();
    }
    return TRUE;
}
