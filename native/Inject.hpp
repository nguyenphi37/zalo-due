// nguyenphi37
#pragma once

// Loads a DLL into a suspended process. The DLL path may contain non-ASCII characters.

#include <windows.h>

// nguyenphi37
inline bool InjectDll(HANDLE process, const wchar_t* dllPath) {
    if (process == nullptr || dllPath == nullptr || dllPath[0] == 0) {
        return false;
    }
    size_t bytes = (wcslen(dllPath) + 1) * sizeof(wchar_t);
    LPVOID remote = VirtualAllocEx(process, nullptr, bytes, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (remote == nullptr) {
        return false;
    }
    if (!WriteProcessMemory(process, remote, dllPath, bytes, nullptr)) {
        VirtualFreeEx(process, remote, 0, MEM_RELEASE);
        return false;
    }
    FARPROC load = GetProcAddress(GetModuleHandleW(L"kernel32.dll"), "LoadLibraryW");
    if (load == nullptr) {
        VirtualFreeEx(process, remote, 0, MEM_RELEASE);
        return false;
    }
    HANDLE thread = CreateRemoteThread(process, nullptr, 0, reinterpret_cast<LPTHREAD_START_ROUTINE>(load), remote, 0, nullptr);
    if (thread == nullptr) {
        VirtualFreeEx(process, remote, 0, MEM_RELEASE);
        return false;
    }
    DWORD wait = WaitForSingleObject(thread, 20000);
    DWORD code = 0;
    if (wait == WAIT_OBJECT_0) {
        GetExitCodeThread(thread, &code);
    }
    CloseHandle(thread);
    VirtualFreeEx(process, remote, 0, MEM_RELEASE);
    return wait == WAIT_OBJECT_0 && code != 0;
}
