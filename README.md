nguyenphi37
# Zalo Due

Chạy nhiều tài khoản Zalo PC cùng lúc trên Windows. Mỗi tài khoản một cửa sổ, một phiên đăng nhập, gọi thoại và gọi video riêng. Zalo vẫn là bản chính thức.

Zalo Due không sửa chương trình Zalo. Nó chỉ cho mỗi tài khoản một thư mục dữ liệu riêng để các bản chạy song song.

## Tiếng Việt

### Cách dùng

1. Tải `Zalo.Due.exe` và mở. Không cần cài Python.
2. Lần đầu, nếu máy đã cài Zalo, app hiện đang chuyển Zalo và dữ liệu vào thư mục `data` cạnh file exe. Tài khoản đó nằm trong app.
3. Bấm **Thêm tài khoản**, đặt tên, quét mã QR trên điện thoại.
4. Bấm **Mở** để chạy tài khoản. Nhiều tài khoản mở cùng lúc.
5. Trong từng Zalo, gọi thoại và gọi video dùng bình thường.
6. Bấm X để ẩn Due xuống khay. Chuột phải icon khay để hiện lại.
7. Trong **Cài đặt** có **Khởi động cùng Windows**. Trên từng thẻ có **Mở cùng máy**: tài khoản đó tự chạy khi đăng nhập Windows.
8. Thoát hết đóng mọi cửa sổ Zalo rồi tắt Due.
9. Zalo cập nhật một lần, mọi tài khoản dùng chung bản đó.

### Dữ liệu

Tài khoản, tin nhắn và file nằm trong thư mục `data` cạnh `Zalo.Due.exe`. File tải về không chứa tài khoản của ai. Giữ thư mục `data` khi đổi file exe.

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

### Ghi chú

- Phần native dùng [Microsoft Detours](https://github.com/microsoft/Detours), đặt ở `third_party/Detours-4.0.1` (giấy phép MIT).
- Zalo là sản phẩm của VNG Corporation. Dự án này là trình chạy độc lập, không liên kết với VNG.

## English

See the Vietnamese guide above for full usage instructions. In short: run several Zalo PC accounts at the same time on Windows, each with its own window, login, and data folder, while Zalo stays the official build.

- Download `Zalo.Due.exe` from [Releases](../../releases), open it, no Python needed.
- Add an account, scan the QR code, then press **Open**. Accounts run side by side.
- Accounts, messages, and files live in a `data` folder next to the exe. The download contains no one's account. Keep that folder when you swap the exe.

Build from source needs Python 3.11+ and Visual Studio 2022 Build Tools with the **Desktop development with C++** workload:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\Due.cmd
```

Zalo is a product of VNG Corporation. This project is an independent launcher and is not affiliated with VNG.
