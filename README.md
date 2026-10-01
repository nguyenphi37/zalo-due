# Zalo Due

[Tiếng Việt](#tiếng-việt) · [English](#english)

## Tiếng Việt

Chạy nhiều tài khoản Zalo PC cùng lúc trên Windows. Mỗi tài khoản có cửa sổ, đăng nhập và file riêng. Zalo vẫn là bản chính thức và vẫn tự cập nhật.

Zalo Due không sửa chương trình Zalo. Nó chỉ cho mỗi tài khoản một thư mục dữ liệu riêng để các bản chạy song song.

### Tải về và dùng

Vào [Releases](../../releases), tải `Zalo.Due.exe`, rồi mở file đó. Không cần cài Python hay Visual Studio.

- Lần đầu mở, app tự tải Zalo bản chính thức. Cần có mạng.
- Bấm thêm tài khoản, quét mã QR bằng điện thoại.
- Mỗi tài khoản là một cửa sổ Zalo riêng, mở cùng lúc không đè nhau.
- Tài khoản, tin nhắn và file nằm trong thư mục `data` cạnh file exe. File exe tải về không chứa tài khoản của ai.

Muốn app chạy nền: bấm X để ẩn xuống khay. Bấm chuột phải vào icon khay để hiện lại. Trong Cài đặt có **Khởi động cùng Windows**, và mỗi tài khoản có công tắc **Mở cùng máy**.

Cần có [Microsoft Edge WebView2](https://developer.microsoft.com/microsoft-edge/webview2/). Windows hiện tại thường đã có sẵn.

### Chạy từ mã nguồn

Cần Python 3.11 trở lên và Visual Studio 2022 Build Tools, workload **Desktop development with C++**.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\Due.cmd
```

`Due.cmd` tự biên dịch phần native lần đầu, rồi mở Zalo Due.

Đóng gói ra file exe:

```powershell
.\native\build.cmd
.\.venv\Scripts\pyinstaller --noconfirm "Zalo Due.spec"
```

File thành phẩm là `dist\Zalo Due.exe`.

### Cách các tài khoản tách nhau

- Một bản Zalo chính thức dùng chung. Cập nhật một lần, mọi tài khoản đều được.
- Mỗi tài khoản một thư mục riêng cho dữ liệu app, tài liệu và file tải về, nên đăng nhập không bao giờ đè lên nhau.
- Khóa "chỉ mở một cửa sổ" được tách theo từng tài khoản, nên các cửa sổ chạy cùng lúc.
- Tiến trình Zalo mới, kể cả tiến trình cơ sở dữ liệu chạy nền, đều được tách theo.

### Lưu ý

- Cuộc gọi thoại/video khi chạy nhiều tài khoản hiện chưa được xác minh hoạt động ổn định; có báo cáo không nhận được cuộc gọi. Bản phát hành này chưa sửa lỗi cuộc gọi.
- Tài khoản, cài đặt và bản Zalo đã tải nằm trong thư mục `data` cạnh app. Thư mục này chỉ ở máy bạn, không nằm trong repo.
- Phần native dùng [Microsoft Detours](https://github.com/microsoft/Detours), đặt ở `third_party/Detours-4.0.1` (giấy phép MIT).
- Zalo là sản phẩm của VNG Corporation. Dự án này là trình chạy độc lập, không liên kết với VNG.

## English

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

- Voice/video calls with multiple accounts are not verified as reliable; incoming-call failures have been reported. This release does not fix calling.
- Accounts, settings, and the downloaded Zalo live in a `data` folder next to the app. That folder is local and is not part of this repository.
- The native helper links against [Microsoft Detours](https://github.com/microsoft/Detours), included under `third_party/Detours-4.0.1` (MIT license).
- Zalo is a product of VNG Corporation. This project is an independent launcher and is not affiliated with VNG.
