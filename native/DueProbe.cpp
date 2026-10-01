// nguyenphi37
// Prints the folders and singleton result DueHook produced for this process.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <knownfolders.h>
#include <shlobj.h>

#include <string>

namespace {

std::wstring Known(REFKNOWNFOLDERID id) {
    PWSTR path = nullptr;
    if (FAILED(SHGetKnownFolderPath(id, 0, nullptr, &path)) || path == nullptr) {
        return L"";
    }
    std::wstring value(path);
    CoTaskMemFree(path);
    return value;
}

std::wstring FolderPath(int csidl) {
    wchar_t path[MAX_PATH];
    if (FAILED(SHGetFolderPathW(nullptr, csidl, nullptr, SHGFP_TYPE_CURRENT, path))) {
        return L"";
    }
    return path;
}

std::wstring Env(const wchar_t* name) {
    wchar_t buffer[MAX_PATH];
    DWORD n = GetEnvironmentVariableW(name, buffer, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return L"";
    }
    return buffer;
}

void WriteProbe(const std::wstring& path, const std::wstring& text) {
    HANDLE file = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    int bytes = WideCharToMultiByte(CP_UTF8, 0, text.c_str(), static_cast<int>(text.size()), nullptr, 0, nullptr, nullptr);
    std::string utf8(static_cast<size_t>(bytes > 0 ? bytes : 0), '\0');
    if (bytes > 0) {
        WideCharToMultiByte(CP_UTF8, 0, text.c_str(), static_cast<int>(text.size()), utf8.data(), bytes, nullptr, nullptr);
        DWORD written = 0;
        WriteFile(file, utf8.data(), static_cast<DWORD>(utf8.size()), &written, nullptr);
    }
    CloseHandle(file);
}

}  // namespace

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    bool checkMutex = false;
    DWORD holdMs = 1500;
    int argc = 0;
    LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argv != nullptr) {
        for (int i = 1; i < argc; ++i) {
            if (_wcsicmp(argv[i], L"--mutex") == 0) {
                checkMutex = true;
            } else if (_wcsicmp(argv[i], L"--hold") == 0 && i + 1 < argc) {
                holdMs = static_cast<DWORD>(_wtoi(argv[++i]));
            }
        }
        LocalFree(argv);
    }

    std::wstring mutex = L"SKIP";
    HANDLE handle = nullptr;
    if (checkMutex) {
        SetLastError(0);
        handle = CreateMutexW(nullptr, TRUE, L"Local\\Zalo.singleton.probe");
        if (handle == nullptr) {
            mutex = L"ERROR";
        } else if (GetLastError() == ERROR_ALREADY_EXISTS) {
            mutex = L"BLOCKED";
        } else {
            mutex = L"OK";
        }
    }

    std::wstring text;
    text += L"APPDATA=" + Env(L"APPDATA") + L"\n";
    text += L"LOCALAPPDATA=" + Env(L"LOCALAPPDATA") + L"\n";
    text += L"SH_ROAMING=" + Known(FOLDERID_RoamingAppData) + L"\n";
    text += L"SH_LOCAL=" + Known(FOLDERID_LocalAppData) + L"\n";
    text += L"SH_DOCS=" + Known(FOLDERID_Documents) + L"\n";
    text += L"SH_DOWNLOADS=" + Known(FOLDERID_Downloads) + L"\n";
    text += L"CSIDL_APPDATA=" + FolderPath(CSIDL_APPDATA) + L"\n";
    text += L"MUTEX=" + mutex + L"\n";

    std::wstring root = Env(L"DUE_PROFILE_ROOT");
    if (!root.empty()) {
        WriteProbe(root + L"\\probe.txt", text);
    }
    if (holdMs > 0) {
        Sleep(holdMs);
    }
    if (handle != nullptr) {
        CloseHandle(handle);
    }
    return mutex == L"BLOCKED" ? 2 : 0;
}
