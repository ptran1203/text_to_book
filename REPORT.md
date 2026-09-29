# Ghi chú phương pháp — Chuyển sách "Tư Duy Đặt Cược" sang chuẩn DAISY 3

_Tài liệu nháp để dùng làm báo cáo sau này. Tập trung vào phương pháp/quyết định, không đi sâu chi tiết code._

## 1. Đầu vào

- `data/book.pdf`: bản scan (ảnh, không có lớp text) cuốn *"Tư Duy Đặt Cược"* (Thinking in Bets — Annie Duke, dịch: Mai Chí Trung, NXB Trẻ 2020), 322 trang.
- Xác nhận là scan thật (không phải PDF có sẵn text) bằng cách kiểm tra content stream của PDF: không có font, không có toán tử vẽ chữ (Tj/TJ), mỗi trang chỉ là một lệnh vẽ ảnh. → Bắt buộc phải OCR.

## 2. Quy trình tổng quan (9 bước)

```
PDF → tách trang ảnh → OCR → làm sạch text → xác định cấu trúc chương
    → sinh audio (TTS) → đồng bộ audio-text (SMIL) → đóng gói DAISY 3
    → kiểm tra → nộp bài
```

Mỗi lần chạy được đánh dấu bằng một `run_id` (thường là mốc thời gian) để không ghi đè lẫn nhau; các bước sau tự nối tiếp bước trước trong cùng run.

## 3. Các quyết định kỹ thuật chính

| Quyết định | Lý do |
|---|---|
| **OCR = Tesseract (tách dòng) + VietOCR (nhận dạng chữ)** | Test thực tế cho thấy VietOCR đọc tiếng Việt có dấu chính xác hơn hẳn bộ nhận dạng có sẵn của Tesseract (~0.90+ độ tin cậy trên trang thân bài thật, so với Tesseract tự đọc kém hơn nhiều). Tesseract chỉ dùng để xác định vị trí từng dòng chữ trên trang. |
| **TTS = piper (offline), giọng vais1000/medium** | Giọng tiếng Việt chất lượng cao nhất hiện có cho piper; chạy offline, không cần API/trả phí. Nhược điểm đã biết: không đọc tốt tên riêng/thuật ngữ tiếng Anh (mô hình chỉ train tiếng Việt thuần). |
| **Mỗi chương = 1 quyển sách DAISY 3 riêng, chung 1 mã ISBN** | Theo đúng yêu cầu môn học cho sách dài, chia theo chương. |
| **Tự dựng DTBook/SMIL/NCX/OPF bằng Python** (không dùng DAISY Pipeline 2 để build) | piper không phải bộ máy TTS mà DAISY Pipeline 2 hỗ trợ trực tiếp. DAISY Pipeline 2 dự kiến chỉ dùng để **kiểm tra/validate** ở bước cuối. |
| **Xác định chương thật bằng cách quét toàn sách tìm tiêu đề in đậm/to** (không dựa vào mục lục để tự động) | Mục lục (trang 8–10) tuy có tên chương thật (dùng làm tiêu đề chính thức), nhưng không có số trang đáng tin cậy; phải quét từng cụm ~100–160 trang, tìm dòng chữ to bất thường, rồi người kiểm tra lại thủ công loại bỏ nhiễu (đầu trang lặp lại, bìa, mục lục...). |

## 4. Các vấn đề đã gặp và cách xử lý

### 4.1. Chất lượng OCR không đồng đều
- Trang thân bài bình thường: ~85–92% độ tin cậy, lỗi chủ yếu là sai dấu/từ đơn lẻ (vd: "Tồi"→"Tôi", "giá từ"→"giã từ") — mức chấp nhận được, cần người nghe/đọc bắt lỗi.
- **Trang mở đầu mỗi chương** (tiêu đề in đậm/chữ lớn trộn với đoạn văn mở đầu) là điểm yếu rõ rệt: OCR từng **bịa ra chuỗi số vô nghĩa** (vd: đọc thành "031001001001201") và **ghép nhầm chú thích cuối trang vào giữa đoạn văn chính**, làm sai lệch hẳn nội dung. Phát hiện qua nghe thử audio ("đọc số không không một chấm..." không có trong sách thật).
- Quan trọng: **độ tin cậy OCR (confidence score) đo theo dòng KHÔNG phát hiện được lỗi này** — trang lỗi nặng vẫn có điểm tin cậy bình thường (~0.87), vì OCR "tự tin" đọc sai cấu trúc chứ không phải đọc sai từng chữ. → Phải dùng hiểu biết cấu trúc (trang mở chương = rủi ro cao) để chủ động kiểm tra bằng mắt, thay vì chỉ dựa vào số liệu.
- Cách sửa: đối chiếu trực tiếp với ảnh scan gốc, viết lại tay đoạn bị lỗi ở lớp "văn bản đã làm sạch" (không sửa log OCR gốc, không sửa file audio/sách trực tiếp), rồi build lại từ đó.

### 4.2. Lỗi hệ thống trong pipeline tự viết (không phải lỗi OCR)
- Một quy tắc làm sạch văn bản (thêm khoảng trắng sau dấu câu) vô tình phá vỡ số thập phân kiểu Việt Nam (vd: "6,4 triệu" → "6, 4 triệu"), khiến giọng đọc tách thành hai số. Sửa bằng cách loại trừ trường hợp dấu câu nằm giữa hai chữ số.
- Khi xây lại một chương đã có sẵn audio, có lúc **ghi đè nhầm dữ liệu tổng hợp** khiến một phần audio không được cập nhật dù văn bản đã sửa đúng (một số câu "trùng ID ngẫu nhiên" với bản cũ nên bị bỏ qua không tổng hợp lại). Phát hiện bằng cách đối chiếu thời gian chỉnh sửa file. Đã bổ sung cơ chế kiểm tra để tránh lặp lại.
- Một số lần build nhiều chương trong cùng một lượt chạy vô tình chỉ giữ lại dữ liệu của chương chạy sau cùng, làm "biến mất" chương chạy trước — phải bổ sung khả năng chỉ định nhiều chương cùng lúc để tránh ghi đè.

### 4.3. Phát âm tiếng Anh
- Sách nói về văn hóa poker Mỹ nên có rất nhiều tên riêng/thuật ngữ tiếng Anh (tên người, địa danh, đội thể thao, thương hiệu...). Giọng đọc tiếng Việt thuần đọc sai các từ này theo quy tắc tiếng Việt.
- Giải pháp: lập một danh sách thay thế — CHỈ áp dụng cho phần đưa vào máy đọc (không đổi chữ hiển thị trong sách) — chuyển các tên/thuật ngữ hay lặp lại sang cách viết gần với cách đọc tiếng Việt hơn. Ưu tiên xử lý từ xuất hiện nhiều lần trước (từ "poker" xuất hiện hơn 240 lần trong sách, xử lý trước tiên).
- Giới hạn: các phiên âm này là suy đoán hợp lý, **chưa được người nghe xác nhận** (không thể tự kiểm chứng bằng tai), cần người dùng nghe và phản hồi để tinh chỉnh dần.

## 5. Phương pháp kiểm tra chất lượng (QA)

1. Kiểm tra tự động: cấu trúc DAISY hợp lệ (liên kết audio-text-điều hướng khớp nhau), số trang khớp, mã định danh sách thống nhất giữa các chương.
2. Đo tổng thời lượng audio thật, gán theo từng thành viên, so với yêu cầu tối thiểu 1 giờ/người.
3. Nghe thử thực tế + đối chiếu ảnh scan khi phát hiện bất thường — đây là kênh phát hiện lỗi hiệu quả nhất hiện tại, vì độ tin cậy OCR không phản ánh hết các lỗi cấu trúc.
4. Rủi ro đã biết nhưng CHƯA kiểm tra hết: mới xem 2/6 "trang mở đầu chương" (11 và 17, cả hai đều lỗi và đã sửa); còn 4 trang cùng loại (55, 99, 151, 191, 219) khả năng cao cũng lỗi tương tự nhưng chưa xác minh.

## 6. Kết quả hiện tại

- Đã build xong: Dẫn Nhập + Chương 1–6 (7 phần), tổng cộng hơn 6 giờ audio thật.
- Phân chia cho 3 thành viên, mỗi người đều vượt yêu cầu tối thiểu 1 giờ.
- Đóng gói đúng cấu trúc nộp bài (mã số sinh viên, tên sách, sha256).

## 7. Việc còn lại / hạn chế

- Mã ISBN thật cho ấn bản này chưa được xác nhận (đã tìm được ứng viên từ trang web NXB nhưng chưa kiểm chứng chéo).
- Chương 6 chưa xác định điểm kết thúc thật (còn tiếp tục); phần phụ lục cuối sách (Lời Cảm Ơn, Chú Thích, Danh Mục Tham Khảo) chưa xác định vị trí.
- Chưa chạy trình kiểm tra chính thức của DAISY Pipeline 2 (chỉ mới kiểm tra nội bộ tự viết).
- Còn 4 "trang mở đầu chương" chưa được đối chiếu tay với ảnh scan gốc.
- Phiên âm tiếng Anh cho giọng đọc là suy đoán, chưa có người bản ngữ/người nghe xác nhận toàn bộ.
- Đây là bản dịch có bản quyền hiện hành — cần xác nhận môn học đã cho phép sử dụng.
