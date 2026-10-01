# Zalo Due

Run several Zalo PC accounts at the same time on Windows. Each account keeps its own window, login, and files. Zalo itself stays the official build and updates normally.

Zalo Due does not modify the Zalo program. It only gives every account a separate data folder and lets those copies run side by side.

## What you need

- Windows 10 or 11, 64-bit
- [Microsoft Edge WebView2](https://developer.microsoft.com/microsoft-edge/webview2/) (already present on current Windows)
- Python 3.11 or newer
- Visual Studio 2022 Build Tools with the **Desktop development with C++** workload, used once to build the native helper

## Run from source

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\Due.cmd
```

`Due.cmd` builds the native helper the first time, then opens Zalo Due. The window hides to the tray; right-click the tray icon and choose the window to bring it back.

## Build the app

```powershell
.\native\build.cmd
.\.venv\Scripts\pyinstaller --noconfirm "Zalo Due.spec"
```

The result is `dist\Zalo Due.exe`.

## How accounts stay separate

- One shared, official Zalo install. Updates apply once and every account gets them.
- Each account gets its own folder for app data, documents, and downloads, so logins never overwrite each other.
- The lock that normally stops a second Zalo is lifted per account, so the windows run together.
- New Zalo processes inherit the same separation, including the hidden database process.

## Notes

- Accounts, settings, and the downloaded Zalo live in a `data` folder next to the app. That folder is local and is not part of this repository.
- The native helper links against [Microsoft Detours](https://github.com/microsoft/Detours), included under `third_party/Detours-4.0.1` (MIT license).
- Zalo is a product of VNG Corporation. This project is an independent launcher and is not affiliated with VNG.
