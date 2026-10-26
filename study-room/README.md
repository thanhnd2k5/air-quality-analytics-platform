# Góc bảo vệ — INT1422

Trang học tương tác theo dự án Air Quality Analytics Platform, gồm 13 bài kiến
thức nền có câu kiểm tra, 70 câu vấn đáp, sơ đồ luồng dữ liệu, bốn bài thực hành
và thi thử vấn đáp tự đánh giá.

## Mở trang

Trên Windows, bấm đúp `Mo_goc_bao_ve.cmd` để mở bằng Edge/Chrome đã cài.
Hoặc mở `dist/index.html` bằng Edge hoặc Chrome. Trang không cần cài thư viện,
không gọi API và dùng được offline. Nội dung, CSS và JavaScript đã được gói
trong một file HTML.

Tiến độ, câu đã lưu và ghi chú được giữ trong localStorage của trình duyệt.
Dùng **Sổ tay → Xuất tiến độ & ghi chú** để sao lưu hoặc chuyển máy; dùng
**Nhập bản lưu** để phục hồi. Chính sách của trình duyệt có thể hạn chế lưu
khi mở file trực tiếp; trang sẽ thông báo nếu không ghi được.

## Nội dung và phạm vi

- Ngân hàng câu hỏi lấy từ `bao_cao/ON_TAP_BAO_VE_HOI_DAP.md`.
- Bài kiến thức nền nằm trong `src/lessons.js`: khái niệm → ví dụ → áp dụng
  trong dự án → kiểm tra hiểu bài → câu hỏi nối tiếp.
- Ma trận nhầm lẫn dùng số đếm test trong
  `artifacts/classification/model_lock.json`; số chỉnh tay chỉ là minh họa.
- Bài OLAP dùng dữ liệu tự tạo, được ghi rõ ngay trong giao diện.
- Các mức “đã nắm / cần luyện / chưa nắm” là tự đánh giá, không phải chấm bằng AI.
- Đây là tài liệu ôn bảo vệ theo dự án, không phải giáo trình đầy đủ của học phần
  và không khẳng định giảng viên sẽ hỏi các câu trong ngân hàng.

## Sinh lại sau khi sửa tài liệu

Từ thư mục gốc dự án, chạy với Python 3:

```powershell
python study-room/build.py
```

Script chỉ dùng thư viện chuẩn. Mã giao diện nằm trong `src/`; kết quả sinh
ra nằm trong `dist/index.html`. Không sửa trực tiếp bản HTML đã sinh.

## Kiểm tra hành vi

Nếu có Node.js, chạy:

```powershell
node study-room/check.cjs
```

Bộ kiểm tra chạy bản HTML đã đóng gói trong DOM giả lập, không cần cài thêm
thư viện. Nó kiểm tra dữ liệu, tìm kiếm, lưu tiến độ, phép tổng hợp, chỉ số
và một phiên thi thử. Đây không phải kiểm tra hiển thị bằng trình duyệt.
