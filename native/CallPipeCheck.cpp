// nguyenphi37
// Standalone regression probe; no production hooks.
// Build to owned temp only: cl /nologo /std:c++17 /EHsc /W4 /MT /DUNICODE /D_UNICODE CallPipeCheck.cpp /link /out:<owned-temp>\CallPipeCheck.exe
// Run --server|--server-a recv|send TOKEN and matching --client|--client-a in separate synthetic DueLaunch profiles.
// Both modes require DUE_PROFILE_ID. Launch both servers before clients. A failed second creation is a safe RED;
// never connect clients on baseline. On fixed builds each client must receive its own synthetic TOKEN.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <string>
#include <cstdio>

namespace {
constexpr wchar_t kRecv[] = L"\\\\.\\pipe\\PipeZCallRecv";
constexpr wchar_t kSend[] = L"\\\\.\\pipe\\PipeZCallSend";

void Report(const wchar_t* label, DWORD error = 0) {
    std::fwprintf(stderr, L"%ls%s%lu\n", label, error ? L" error=" : L"", error);
}

bool CallName(const wchar_t* arg, const wchar_t** name) {
    if (_wcsicmp(arg, L"recv") == 0) *name = kRecv;
    else if (_wcsicmp(arg, L"send") == 0) *name = kSend;
    else return false;
    return true;
}

int Server(const wchar_t* arg, const wchar_t* token, bool ansi) {
    const wchar_t* name = nullptr;
    if (!CallName(arg, &name) || !*token || !GetEnvironmentVariableW(L"DUE_PROFILE_ID", nullptr, 0)) return 2;
    HANDLE pipe = ansi
        ? CreateNamedPipeA(_wcsicmp(arg, L"recv") == 0 ? "\\\\.\\pipe\\PipeZCallRecv" : "\\\\.\\pipe\\PipeZCallSend",
            PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE, PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT, 1, 64, 64, 5000, nullptr)
        : CreateNamedPipeW(name, PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE,
            PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT, 1, 64, 64, 5000, nullptr);
    if (pipe == INVALID_HANDLE_VALUE) {
        Report(L"SERVER_CREATE_FAILED", GetLastError());
        return 10;
    }
    BOOL connected = ConnectNamedPipe(pipe, nullptr) ? TRUE : GetLastError() == ERROR_PIPE_CONNECTED;
    char request[128]{};
    DWORD got = 0, sent = 0;
    bool ok = connected && ReadFile(pipe, request, sizeof(request) - 1, &got, nullptr) &&
        std::string(request, got) == "request" &&
        WriteFile(pipe, token, static_cast<DWORD>(wcslen(token) * sizeof(wchar_t)), &sent, nullptr) &&
        sent == wcslen(token) * sizeof(wchar_t);
    if (!ok) Report(L"SERVER_EXCHANGE_FAILED", GetLastError());
    else Report(L"SERVER_OK");
    FlushFileBuffers(pipe);
    DisconnectNamedPipe(pipe);
    CloseHandle(pipe);
    return ok ? 0 : 11;
}

int Client(const wchar_t* arg, const wchar_t* expected, bool ansi) {
    const wchar_t* name = nullptr;
    wchar_t id[64]{};
    DWORD idLength = GetEnvironmentVariableW(L"DUE_PROFILE_ID", id, _countof(id));
    if (!CallName(arg, &name) || !*expected || idLength != 36 || id[8] != L'-' || id[13] != L'-' || id[18] != L'-' || id[23] != L'-') return 2;
    std::wstring isolated(name);
    isolated += L".due.";
    isolated += id;
    if (!WaitNamedPipeW(isolated.c_str(), 50)) { Report(L"PROFILE_ENDPOINT_MISSING", GetLastError()); return 19; }
    DWORD waitResult = WaitNamedPipeW(name, 5000);
    if (!waitResult) { Report(L"CLIENT_WAIT_FAILED", GetLastError()); return 20; }
    HANDLE pipe = ansi
        ? CreateFileA(_wcsicmp(arg, L"recv") == 0 ? "\\\\.\\pipe\\PipeZCallRecv" : "\\\\.\\pipe\\PipeZCallSend",
            GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, 0, nullptr)
        : CreateFileW(name, GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, 0, nullptr);
    if (pipe == INVALID_HANDLE_VALUE) { Report(L"CLIENT_OPEN_FAILED", GetLastError()); return 20; }
    DWORD mode = PIPE_READMODE_BYTE;
    SetNamedPipeHandleState(pipe, &mode, nullptr, nullptr);
    DWORD sent = 0, got = 0;
    const char request[] = "request";
    wchar_t response[128]{};
    bool ok = WriteFile(pipe, request, sizeof(request) - 1, &sent, nullptr) && sent == sizeof(request) - 1 &&
        ReadFile(pipe, response, sizeof(response) - sizeof(wchar_t), &got, nullptr) &&
        got % sizeof(wchar_t) == 0 && std::wstring(response, got / sizeof(wchar_t)) == expected;
    if (!ok) Report(L"CLIENT_RESPONSE_MISMATCH", GetLastError());
    else Report(L"CLIENT_OK");
    CloseHandle(pipe);
    return ok ? 0 : 21;
}

bool LocalRoundTrip(const std::wstring& name) {
    HANDLE pipe = CreateNamedPipeW(name.c_str(), PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT, 1, 16, 16, 0, nullptr);
    if (pipe == INVALID_HANDLE_VALUE) return false;
    HANDLE client = CreateFileW(name.c_str(), GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, 0, nullptr);
    DWORD wrote = 0, read = 0;
    char out = 'x', in = 0;
    bool ok = client != INVALID_HANDLE_VALUE &&
        (ConnectNamedPipe(pipe, nullptr) || GetLastError() == ERROR_PIPE_CONNECTED) &&
        WriteFile(client, &out, 1, &wrote, nullptr) && ReadFile(pipe, &in, 1, &read, nullptr) &&
        wrote == 1 && read == 1 && in == out;
    if (client != INVALID_HANDLE_VALUE) CloseHandle(client);
    DisconnectNamedPipe(pipe);
    CloseHandle(pipe);
    return ok;
}
}

int wmain(int argc, wchar_t** argv) {
    if (argc == 4 && (_wcsicmp(argv[1], L"--server") == 0 || _wcsicmp(argv[1], L"--server-a") == 0))
        return Server(argv[2], argv[3], _wcsicmp(argv[1], L"--server-a") == 0);
    if (argc == 4 && (_wcsicmp(argv[1], L"--client") == 0 || _wcsicmp(argv[1], L"--client-a") == 0))
        return Client(argv[2], argv[3], _wcsicmp(argv[1], L"--client-a") == 0);
    if (argc == 2 && _wcsicmp(argv[1], L"--probe") == 0) {
        const std::wstring suffix = std::to_wstring(GetCurrentProcessId());
        const bool unrelated = LocalRoundTrip(L"\\\\.\\pipe\\DueCallCheckUnrelated_" + suffix);
        const bool nearMatch = LocalRoundTrip(L"\\\\.\\pipe\\PipeZCallRecvExtra_" + suffix);
        Report(unrelated ? L"UNRELATED_ORIGINAL_NAME_OK" : L"UNRELATED_PIPE_FAILED");
        Report(nearMatch ? L"NONMATCHING_CALL_NAME_OK" : L"NONMATCHING_CALL_NAME_FAILED");
        return unrelated && nearMatch ? 0 : 30;
    }
    std::fwprintf(stderr, L"usage: --server recv|send TOKEN | --client recv|send TOKEN | --probe\n");
    return 2;
}
