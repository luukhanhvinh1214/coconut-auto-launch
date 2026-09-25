# Coconut Auto Launch

Ứng dụng nhỏ cho Windows: tự mở các ứng dụng bạn chọn (trình duyệt, IDE, ứng dụng chat...) ngay sau khi đăng nhập laptop. Lõi viết bằng Python, giao diện viết bằng React và hiển thị trong cửa sổ riêng qua [pywebview](https://pywebview.flowrl.com/) (WebView2).

## Yêu cầu

- Windows 10 hoặc 11, có Microsoft Edge WebView2 Runtime (Windows 11 có sẵn)
- Python 3.11 trở lên
- Node.js 20.19+ (để build giao diện)
- Git

## Cài đặt

```powershell
git clone <dia-chi-repo> coconut-auto-launch
cd coconut-auto-launch
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
```

## Chạy

```powershell
.venv\Scripts\pythonw.exe app.py
```

Trong cửa sổ:

- **Thêm ứng dụng**: chọn file `.exe` hoặc shortcut `.lnk`.
- **Độ trễ (giây)**: thời gian chờ kể từ lúc đăng nhập rồi mới mở app đó. App mở theo độ trễ tăng dần, cùng độ trễ thì theo thứ tự trong danh sách.
- **Khởi động cùng Windows**: ghi hoặc gỡ entry `CoconutAutoLaunch` trong `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. Không cần quyền admin.

Mọi thay đổi được lưu ngay vào `config.json` cạnh `app.py`. File này là dữ liệu cá nhân nên đã nằm trong `.gitignore`. Lúc đăng nhập, Windows chạy `pythonw.exe app.py --startup`: chỉ phần lõi chạy, không mở cửa sổ. Kết quả mở từng app được ghi vào `coconut-auto-launch.log`.

Đổi chỗ thư mục dự án hoặc tạo lại `.venv` thì entry khởi động cũ sẽ trỏ sai. Mở app lên, công tắc sẽ hiện Tắt, bật lại là xong.

## Cấu trúc

| Đường dẫn | Vai trò |
|---|---|
| `app.py` | Điểm vào: không tham số thì mở cửa sổ, `--startup` thì mở danh sách app |
| `core.py` | Lõi: đọc/ghi `config.json`, mở app, đăng ký khởi động (mọi thao tác registry nằm ở đây) |
| `ui.py` | Cửa sổ pywebview và các hàm giao diện React gọi sang |
| `frontend/` | Giao diện React + Vite, build ra `frontend/dist/` |
| `test_core.py` | Test cho lõi: `.venv\Scripts\python -m unittest test_core` |

## Làm việc với Claude Code

`CLAUDE.md` và thư mục `.claude/` chỉ giữ ở máy local, không đưa lên git. Bản clone không có sẵn: tự tạo theo mô tả dưới đây, hoặc xin người trong nhóm.

Có hai thứ đó rồi thì mở thư mục dự án bằng Claude Code là cấu hình tự được nạp. Quy tắc bắt buộc trong `CLAUDE.md`, tóm tắt:

- Không emoji, không icon trong code và giao diện.
- Comment chỉ khi thật cần, một dòng, đơn giản.
- Claude chỉ commit khi được yêu cầu rõ ràng. Thông điệp commit tiếng Anh, dưới 50 ký tự, dạng `feat: ...` / `fix: ...`.
- Nghiên cứu kỹ trước khi làm, không rõ thì hỏi lại.

### Thư mục `.claude/`

| Đường dẫn | Vai trò |
|---|---|
| `rules/` | Quy tắc chi tiết, tự nạp mỗi phiên: `rules.md` (chung), `git.md`, `verification.md`, `memories.md` |
| `agents/` | Subagent: `python-dev` (viết code), `researcher` (tra cứu, không sửa code), `verifier` (kiểm chứng, không sửa code) |
| `commands/` | Lệnh gõ tắt: `/verify`, `/new-rule`, `/save-step`, `/wrap-up` |
| `output-styles/` | Giọng trả lời "Clean Tech": tiếng Việt, ngắn, trình bày trước/sau |
| `settings.json` | Quyền dùng tool, hook chạy đầu phiên |
| `settings.local.json` | Cấu hình riêng từng máy |
| `memories/` | Nhật ký phiên làm việc, tự xoá sau 30 ngày |

### Chỉnh sửa cho phù hợp

**Rule** — sửa thẳng file `.md`. Cần rule riêng cho một module thì gõ `/new-rule <ten-module>`: Claude khảo sát code, tạo file từ `rules/_module.template.md` và thêm vào mục lục cuối `rules.md`. Chỉ ghi điều đọc code không tự thấy (quyết định có chủ ý, ràng buộc đồng bộ, hướng đã thử và thất bại). Muốn rule chỉ nạp khi đụng tới một vùng code, thêm frontmatter:

```markdown
---
paths:
  - "src/startup/**"
---
```

**Agent** — mỗi file là một agent, thêm file là thêm agent:

```markdown
---
name: python-dev
description: Việc gì thì Claude nên giao cho agent này
tools: Read, Write, Edit, Glob, Grep, Bash
model: sonnet
---
Hướng dẫn cho agent.
```

`description` quyết định lúc nào Claude tự giao việc, nên viết cụ thể. `model` là tuỳ chọn. Gọi tay bằng câu như "dùng agent verifier kiểm phần vừa sửa".

**Command** — tên file là tên lệnh (`verify.md` thành `/verify`). Frontmatter có `description` và `argument-hint`; `$ARGUMENTS` trong nội dung nhận phần gõ sau lệnh. Việc nhiều bước hoặc cần file kèm theo thì nên viết thành skill: `.claude/skills/<ten>/SKILL.md`.

**Output style** — bật qua `/config`, hoặc thêm `"outputStyle": "Clean Tech"` vào `settings.json`.

**Quyền** — sửa `permissions.allow` / `permissions.deny` trong `settings.json` (deny thắng allow). Thiết lập chỉ dành cho máy mình thì để ở `settings.local.json`.

**Bộ nhớ phiên** — hook đầu phiên tự chạy `node .claude/memories/memory.mjs brief`. Sau mỗi yêu cầu gõ `/save-step`, cuối phiên gõ `/wrap-up`. Không sửa tay file JSON trong `memories/`; lỡ sửa thì chạy `node .claude/memories/memory.mjs check`.
