// nguyenphi37
// Starts one Zalo (or a test program) with DueHook loaded and a private profile.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include "Inject.hpp"

#include <cwctype>
#include <string>
#include <vector>

namespace {

std::wstring g_root;
std::wstring g_resultPath;

std::wstring ToLower(std::wstring value);
bool TrustedProfile(const std::wstring& lower);

// nguyenphi37
void WriteResult(bool ok, const std::wstring& detail) {
    std::wstring lower = ToLower(g_root);
    if (g_resultPath.empty() || !TrustedProfile(lower)) {
        return;
    }
    std::wstring temp = g_resultPath + L".tmp";
    HANDLE file = CreateFileW(temp.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    std::wstring text = ok ? L"ok\n" : L"err\n";
    text += detail;
    text += L"\n";
    int bytes = WideCharToMultiByte(CP_UTF8, 0, text.c_str(), static_cast<int>(text.size()), nullptr, 0, nullptr, nullptr);
    std::string utf8(static_cast<size_t>(bytes), '\0');
    WideCharToMultiByte(CP_UTF8, 0, text.c_str(), static_cast<int>(text.size()), utf8.data(), bytes, nullptr, nullptr);
    DWORD written = 0;
    WriteFile(file, utf8.data(), static_cast<DWORD>(utf8.size()), &written, nullptr);
    CloseHandle(file);
    MoveFileExW(temp.c_str(), g_resultPath.c_str(), MOVEFILE_REPLACE_EXISTING);
}

// nguyenphi37
std::wstring ToLower(std::wstring value) {
    for (wchar_t& ch : value) {
        ch = static_cast<wchar_t>(towlower(ch));
    }
    return value;
}

// nguyenphi37
bool ValidId(const std::wstring& id) {
    const int groups[] = {8, 4, 4, 4, 12};
    int group = 0;
    int count = 0;
    if (id.size() != 36) {
        return false;
    }
    for (wchar_t ch : id) {
        if (ch == L'-') {
            if (group >= 4 || count != groups[group]) {
                return false;
            }
            ++group;
            count = 0;
            continue;
        }
        if (!iswxdigit(ch)) {
            return false;
        }
        ++count;
    }
    return group == 4 && count == 12;
}

// nguyenphi37
bool EndsWith(const std::wstring& value, const std::wstring& suffix) {
    return value.size() >= suffix.size() &&
           value.compare(value.size() - suffix.size(), suffix.size(), suffix) == 0;
}

// nguyenphi37
bool TrustedProfile(const std::wstring& lower) {
    return lower.find(L"\\data\\profiles\\") != std::wstring::npos ||
           lower.find(L"\\data\\selftest\\") != std::wstring::npos ||
           lower.find(L"\\due\\profiles\\") != std::wstring::npos ||
           lower.find(L"\\due\\selftest\\") != std::wstring::npos;
}

// nguyenphi37
bool RootMatches(const std::wstring& root, const std::wstring& id) {
    std::wstring lower = ToLower(root);
    std::wstring lid = ToLower(id);
    return EndsWith(lower, L"\\data\\profiles\\" + lid) || EndsWith(lower, L"\\data\\selftest\\" + lid) ||
           EndsWith(lower, L"\\due\\profiles\\" + lid) || EndsWith(lower, L"\\due\\selftest\\" + lid);
}

// nguyenphi37
std::wstring Quote(const std::wstring& value) {
    std::wstring out = L"\"";
    for (wchar_t ch : value) {
        if (ch == L'"') {
            out += L'\\';
        }
        out += ch;
    }
    out += L'"';
    return out;
}

// nguyenphi37
void EnsureDir(const std::wstring& path) {
    CreateDirectoryW(path.c_str(), nullptr);
}

// nguyenphi37
std::wstring EnvBlock(const std::vector<std::pair<std::wstring, std::wstring>>& overrides) {
    std::vector<std::pair<std::wstring, std::wstring>> entries;
    std::vector<std::wstring> hidden;
    LPWCH source = GetEnvironmentStringsW();
    if (source != nullptr) {
        for (LPWCH cursor = source; *cursor != 0;) {
            std::wstring line = cursor;
            cursor += line.size() + 1;
            if (!line.empty() && line[0] == L'=') {
                hidden.push_back(line);
                continue;
            }
            size_t eq = line.find(L'=');
            if (eq == std::wstring::npos) {
                continue;
            }
            entries.emplace_back(line.substr(0, eq), line.substr(eq + 1));
        }
        FreeEnvironmentStringsW(source);
    }
    for (const auto& item : overrides) {
        bool replaced = false;
        for (auto& entry : entries) {
            if (_wcsicmp(entry.first.c_str(), item.first.c_str()) == 0) {
                entry.second = item.second;
                replaced = true;
                break;
            }
        }
        if (!replaced) {
            entries.push_back(item);
        }
    }
    std::wstring block;
    for (const auto& line : hidden) {
        block += line;
        block.push_back(L'\0');
    }
    for (const auto& entry : entries) {
        block += entry.first;
        block += L'=';
        block += entry.second;
        block.push_back(L'\0');
    }
    block.push_back(L'\0');
    return block;
}

// nguyenphi37
const wchar_t* ArgValue(int argc, wchar_t** argv, const wchar_t* name, int& index) {
    if (index + 1 >= argc || _wcsicmp(argv[index], name) != 0) {
        return nullptr;
    }
    index += 1;
    return argv[index];
}

}  // namespace

// nguyenphi37
int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    int argc = 0;
    LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argv == nullptr) {
        return 1;
    }

    std::wstring id;
    std::wstring exe;
    std::wstring dll;
    std::wstring accountName;
    std::wstring iconPath;
    std::vector<std::wstring> extra;
    bool extras = false;
    for (int i = 1; i < argc; ++i) {
        if (!extras && wcscmp(argv[i], L"--") == 0) {
            extras = true;
            continue;
        }
        if (extras) {
            extra.emplace_back(argv[i]);
            continue;
        }
        const wchar_t* value = nullptr;
        if ((value = ArgValue(argc, argv, L"--root", i)) != nullptr) {
            g_root = value;
        } else if ((value = ArgValue(argc, argv, L"--id", i)) != nullptr) {
            id = value;
        } else if ((value = ArgValue(argc, argv, L"--exe", i)) != nullptr) {
            exe = value;
        } else if ((value = ArgValue(argc, argv, L"--dll", i)) != nullptr) {
            dll = value;
        } else if ((value = ArgValue(argc, argv, L"--name", i)) != nullptr) {
            accountName = value;
        } else if ((value = ArgValue(argc, argv, L"--icon", i)) != nullptr) {
            iconPath = value;
        }
    }
    LocalFree(argv);

    while (!g_root.empty() && (g_root.back() == L'\\' || g_root.back() == L'/')) {
        g_root.pop_back();
    }
    g_resultPath = g_root + L"\\launch.result";

    if (!ValidId(id) || !RootMatches(g_root, id)) {
        WriteResult(false, L"Hồ sơ không hợp lệ");
        return 1;
    }
    if (exe.empty() || GetFileAttributesW(exe.c_str()) == INVALID_FILE_ATTRIBUTES) {
        WriteResult(false, L"Không thấy chương trình cần mở");
        return 1;
    }
    if (dll.empty() || GetFileAttributesW(dll.c_str()) == INVALID_FILE_ATTRIBUTES) {
        WriteResult(false, L"Thiếu thư viện Due");
        return 1;
    }

    std::wstring roaming = g_root + L"\\Roaming";
    std::wstring local = g_root + L"\\Local";
    std::wstring localLow = g_root + L"\\LocalLow";
    std::wstring documents = g_root + L"\\Documents";
    std::wstring downloads = g_root + L"\\Downloads";
    EnsureDir(g_root);
    EnsureDir(roaming);
    EnsureDir(local);
    EnsureDir(localLow);
    EnsureDir(documents);
    EnsureDir(downloads);
    EnsureDir(documents + L"\\Zalo Received Files");

    std::wstring command = Quote(exe);
    for (const auto& arg : extra) {
        command += L' ';
        command += Quote(arg);
    }
    std::vector<wchar_t> commandBuffer(command.begin(), command.end());
    commandBuffer.push_back(L'\0');

    std::wstring directory = exe;
    size_t slash = directory.find_last_of(L"\\/");
    if (slash != std::wstring::npos) {
        directory.resize(slash);
    }

    std::vector<std::pair<std::wstring, std::wstring>> envValues = {
        {L"APPDATA", roaming},
        {L"LOCALAPPDATA", local},
        {L"DUE_PROFILE_ROOT", g_root},
        {L"DUE_PROFILE_ID", id},
        {L"DUE_APP_DATA", roaming},
        {L"DUE_LOCAL_APP_DATA", local},
        {L"DUE_DOCUMENTS", documents},
        {L"DUE_DOWNLOADS", downloads},
        {L"DUE_LOCAL_LOW", localLow},
    };
    if (!accountName.empty()) {
        envValues.push_back({L"DUE_ACCOUNT_NAME", accountName});
    }
    if (!iconPath.empty()) {
        envValues.push_back({L"DUE_ACCOUNT_ICON", iconPath});
    }
    std::wstring environment = EnvBlock(envValues);

    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESHOWWINDOW | STARTF_FORCEOFFFEEDBACK;
    startup.wShowWindow = SW_SHOWNORMAL;
    PROCESS_INFORMATION info{};

    auto launch = [&](DWORD flags) -> BOOL {
        ZeroMemory(&info, sizeof(info));
        DWORD used = flags | CREATE_SUSPENDED;
        if (!CreateProcessW(exe.c_str(), commandBuffer.data(), nullptr, nullptr, FALSE, used, environment.data(),
                            directory.c_str(), &startup, &info)) {
            return FALSE;
        }
        if (!InjectDll(info.hProcess, dll.c_str())) {
            DWORD error = GetLastError();
            TerminateProcess(info.hProcess, 1);
            CloseHandle(info.hThread);
            CloseHandle(info.hProcess);
            ZeroMemory(&info, sizeof(info));
            SetLastError(error);
            return FALSE;
        }
        ResumeThread(info.hThread);
        return TRUE;
    };

    DWORD flags = CREATE_UNICODE_ENVIRONMENT | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB;
    BOOL ok = launch(flags);
    if (!ok) {
        flags = CREATE_UNICODE_ENVIRONMENT | CREATE_NEW_PROCESS_GROUP;
        ok = launch(flags);
    }
    if (!ok) {
        WriteResult(false, L"Không mở được tiến trình, mã " + std::to_wstring(GetLastError()));
        return 1;
    }

    WriteResult(true, std::to_wstring(info.dwProcessId));
    CloseHandle(info.hThread);
    CloseHandle(info.hProcess);
    return 0;
}
