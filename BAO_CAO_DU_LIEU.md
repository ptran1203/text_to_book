# Dữ liệu thô để viết báo cáo — Dự án chuyển đổi sách sang chuẩn DAISY 3

> File này tổng hợp toàn bộ thông tin thực tế của dự án (số liệu, quyết định, vấn đề đã gặp, cách xử lý) để dùng làm nguyên liệu viết báo cáo PDF chính thức. Không phải báo cáo hoàn chỉnh — là dữ liệu đầu vào đầy đủ, chính xác.

## 1. Thông tin chung

| Mục | Nội dung |
|---|---|
| Tên đồ án | Chuyển đổi sách in sang sách nói chuẩn DAISY 3 |
| Sách thực hiện | *Tư Duy Đặt Cược* (nguyên tác: *Thinking in Bets*) |
| Tác giả | Annie Duke |
| Người dịch | Mai Chí Trung |
| Nhà xuất bản (bản dịch) | NXB Trẻ |
| ISBN dùng trong metadata | 9780735216358 |
| Ngày xuất bản (metadata) | 2018-02-06 |
| Ngôn ngữ | Tiếng Việt (vi) |
| Thể loại | Tâm lý học & Phát triển cá nhân |
| Số trang sách gốc | 322 trang (bản scan PDF) |
| Thành viên thực hiện | MSSV 25C11016, MSSV 25C11003 |
| Deadline nộp bài | 30/09 |

**Mô tả sách (dùng cho metadata / giới thiệu):**
> Tư duy đặt cược sử dụng rất nhiều ví dụ hấp dẫn để minh họa cho những công cụ hùng mạnh (và gần như không liên quan gì đến toán học) mà bất cứ ai cũng có thể áp dụng được. Nó sẽ giúp bạn nhận diện những sai lầm may mắn và những khoảnh khắc sáng chói xui xẻo để bạn sẽ ít có nguy cơ bị chiếm lĩnh bởi những cảm xúc phản ứng, thành kiến theo phản xạ và thói quen tiêu cực. Và nó sẽ giúp bạn chiêu mộ được sự giúp đỡ của đồng nghiệp, bạn bè và gia đình trên cuộc hành trình tìm kiếm thành công đang tiếp diễn của mình. Cho dù tương lai có ra sao đi nữa thì bạn cũng sẽ trở nên tự tin hơn, điềm tĩnh hơn và bao dung với bản thân mình hơn khi đối mặt với nó. Không phải lúc nào bạn cũng đưa ra được những quyết định đúng đắn, nhưng bạn sẽ có được một lợi thế lớn hơn rất nhiều so với những người đặt cược bằng cảm giác thay vì bằng trí óc.

## 2. Mục tiêu đồ án

1. Chuyển một cuốn sách in (chỉ có bản scan ảnh, không có văn bản số hoá) thành sách nói điện tử theo chuẩn quốc tế **DAISY 3** (ANSI/NISO Z39.86-2005) — chuẩn dành cho người khiếm thị, khó đọc chữ in.
2. Đảm bảo đồng bộ chính xác giữa văn bản, âm thanh và điều hướng (theo chương, theo trang, theo câu).
3. Đáp ứng yêu cầu môn học: mỗi thành viên đóng góp tối thiểu 1 giờ audio thật; đóng gói và nộp bài đúng quy cách (thư mục theo MSSV, file zip, checksum SHA-256).

## 3. Đầu vào và bước xác minh đầu tiên

- File gốc: `data/book.pdf`, 322 trang.
- **Xác minh bằng kỹ thuật (không đoán)**: dùng PyMuPDF đọc trực tiếp content stream của PDF — phát hiện **không có bất kỳ font nào được nhúng, không có toán tử vẽ chữ nào (Tj/TJ)**; mỗi trang PDF chỉ chứa đúng một lệnh vẽ ảnh (`Do`). Mỗi trang là ảnh scan JBIG2/DCTDecode độ phân giải cao (~3626×5400 px).
- Kết luận: đây là **bản scan thuần**, không có lớp văn bản → bắt buộc phải OCR toàn bộ, không có đường tắt.
- Đã thử tìm bản PDF/ebook khác có lớp văn bản sẵn để thay thế OCR — không tìm được bản nào không phải scan.

## 4. Quy trình thực hiện — 9 bước (pipeline)

Toàn bộ quy trình được viết thành một pipeline tự động bằng Python, chia thành 9 bước kế tiếp, mỗi lần chạy đầy đủ được gọi là một "run" và lưu kết quả riêng để không ghi đè các lần chạy trước:

| # | Bước | Công cụ / Kỹ thuật | Đầu ra |
|---|---|---|---|
| 0 | Tách trang | PyMuPDF — trích ảnh gốc từng trang từ PDF | Ảnh PNG/JPEG từng trang |
| 1 | OCR | **Tesseract** (chỉ dùng để dò vị trí từng dòng chữ) + **VietOCR** (mô hình nhận dạng chữ tiếng Việt, thực hiện việc đọc chữ) | Văn bản thô theo từng dòng, kèm độ tin cậy (confidence) |
| 2 | Làm sạch văn bản | Quy tắc xử lý bằng Python: nối dòng bị ngắt, chuẩn hoá Unicode, loại bỏ đầu trang/số trang lặp lại, sửa khoảng trắng quanh dấu câu | Văn bản đã làm sạch theo từng trang |
| 3 | Xác định cấu trúc | Dò tiêu đề chương bằng chiều cao chữ bất thường + đối chiếu Mục Lục; sinh file **DTBook XML** (chuẩn DAISY) cho từng chương | `book.dtbook.xml` cho mỗi chương |
| 4 | Text-to-Speech | **piper** (TTS ngoại tuyến, giọng `vi_VN-vais1000-medium`) — mỗi câu văn sinh ra một file MP3 riêng | File audio .mp3 theo từng câu |
| 5 | Đồng bộ SMIL | Ghép ID từng câu trong DTBook với đoạn audio tương ứng + thời lượng chính xác (đo từ file WAV) | `book.smil` |
| 6 | Đóng gói DAISY 3 | Sinh **NCX** (điều hướng theo chương/trang) và **OPF** (metadata + danh mục file) | Bộ file DAISY 3 hoàn chỉnh mỗi chương |
| 7 | Kiểm tra | Kiểm tra nội bộ (liên kết SMIL–DTBook–NCX, số trang, ISBN thống nhất) + chuẩn bị cho DAISY Pipeline 2 | Báo cáo kiểm tra |
| 8 | Đóng gói nộp bài | Nén .zip + tính SHA-256, sắp xếp theo cấu trúc thư mục MSSV | `Tu_Duy_Dat_Cuoc.zip` + `_sha256sums.txt` |

Ngoài ra có 2 công cụ báo cáo bổ sung chạy sau cùng: đo tổng thời lượng audio theo từng thành viên, và gộp bản build mới nhất của từng chương (vì mỗi chương thường được build/sửa ở những lần chạy khác nhau) thành một bộ nộp bài thống nhất.

## 5. Các quyết định kỹ thuật chính và lý do

| Quyết định | Lý do lựa chọn |
|---|---|
| OCR = Tesseract (dò dòng) + VietOCR (nhận chữ), không dùng Tesseract để tự đọc chữ | Thử nghiệm thực tế trên trang thân bài thật cho thấy VietOCR đạt ~0.90+ độ tin cậy và đọc đúng gần như hoàn toàn dấu tiếng Việt, trong khi để Tesseract tự nhận chữ tiếng Việt cho kết quả kém hơn rõ rệt. |
| TTS = piper (ngoại tuyến), giọng `vais1000/medium` | Đây là mức chất lượng cao nhất hiện có cho giọng tiếng Việt trong piper (so với `vivos` và `25hours_single` đều thấp hơn); chạy hoàn toàn ngoại tuyến, không cần API/trả phí, phù hợp thời gian và ngân sách đồ án. |
| Mỗi chương = một quyển sách DAISY 3 riêng, dùng chung một mã ISBN | Đúng theo quy định môn học cho sách dài chia theo chương/hồi, vẫn giữ mã định danh chung. |
| Tự viết code sinh DTBook/SMIL/NCX/OPF bằng Python, không dùng DAISY Pipeline 2 để dựng sách | piper không phải là bộ máy TTS được DAISY Pipeline 2 hỗ trợ sẵn. DAISY Pipeline 2 được dành riêng cho vai trò **kiểm tra/thẩm định** ở bước cuối, không dùng để dựng nội dung. |
| Xác định ranh giới chương bằng cách quét toàn sách tìm dòng chữ to bất thường (tiêu đề), rồi đối chiếu thủ công với Mục Lục | Không có cách tự động đáng tin cậy 100%; heuristic chiều cao chữ cho ra nhiều nhiễu (đầu trang lặp lại cũng to), cần người kiểm tra lại trước khi build audio để tránh lãng phí thời gian tổng hợp giọng đọc cho nội dung sai. |

## 6. Các vấn đề gặp phải và cách xử lý

### 6.1. Chất lượng OCR không đồng đều — vấn đề nghiêm trọng nhất

- **Trang thân bài bình thường**: độ tin cậy ~85–92%, lỗi phổ biến là sai dấu đơn lẻ do OCR (ví dụ: "Tồi" thay vì "Tôi", "giá từ" thay vì "giã từ"). Mức lỗi này chấp nhận được, cần người nghe/đọc phát hiện dần.
- **Trang mở đầu mỗi chương** (tiêu đề in đậm cỡ lớn/drop-cap trộn lẫn với đoạn văn mở đầu): phát hiện đây là điểm yếu hệ thống của OCR — xảy ra ở **tất cả 6/6 trang mở chương đã kiểm tra**. Hai dạng lỗi điển hình:
  1. OCR **bịa ra chuỗi số vô nghĩa** không hề tồn tại trên trang gốc (ví dụ đọc thành `031001001001201` ở đầu phần Dẫn Nhập).
  2. **Chú thích cuối trang bị ghép nhầm vào giữa đoạn văn chính** (do sai thứ tự đọc dòng), làm câu văn trở nên vô nghĩa.
- **Phát hiện quan trọng**: độ tin cậy OCR đo theo dòng **không phát hiện được lỗi này** — trang lỗi nặng vẫn có điểm tin cậy ~0.87, gần như bình thường, vì OCR "tự tin" đọc sai cấu trúc chứ không phải đọc sai từng ký tự riêng lẻ.
- **Cách xử lý**: không tin số liệu tự động; chủ động xem trực tiếp ảnh scan gốc của toàn bộ 6 trang mở chương, đối chiếu bằng mắt và sửa tay lại đúng nội dung thật, giữ nguyên số lượng đoạn văn gốc để tránh ảnh hưởng dây chuyền đến việc đánh số câu ở các đoạn phía sau.

**Ví dụ cụ thể (Dẫn Nhập, trang 11):**

| Trước (OCR gốc, độ tin cậy 0.87) | Sau (đối chiếu ảnh gốc, sửa tay) |
|---|---|
| "Vì sao đây không phải là 031001001001201 một cuốn sách viết về poker Nim 26 sáu truổi, rôi nghi rằng rương hi của mình đã được hoad định rất rõ ràng." | "Năm 26 sáu tuổi, tôi nghĩ rằng tương lai của mình đã được hoạch định rất rõ ràng." |

### 6.2. Lỗi hệ thống tự phát sinh trong pipeline (không phải do OCR)

- **Số thập phân bị vỡ đôi khi đọc**: một quy tắc làm sạch văn bản (tự động thêm khoảng trắng sau dấu câu) đã vô tình biến số thập phân kiểu Việt Nam "6,4 triệu" thành "6, 4 triệu" → giọng đọc tách thành hai số riêng biệt có khoảng ngừng ở giữa, nghe rất kỳ. Sửa bằng cách loại trừ trường hợp dấu phẩy/chấm nằm giữa hai chữ số trong quy tắc regex. Rà soát và phát hiện tổng cộng 16 câu bị ảnh hưởng trên toàn sách, tái tạo lại đúng các câu đó.
- **Dữ liệu tổng hợp bị ghi đè khi build nhiều chương chung một lần chạy**: khi từng chương trong cùng một lượt xử lý được build (dựng lại) riêng lẻ, file dữ liệu tổng hợp dùng chung cho lượt đó bị ghi đè hoàn toàn mỗi lần, chỉ còn giữ lại đúng chương build sau cùng — khiến việc sửa lỗi cho chương chạy trước đó "biến mất" một cách âm thầm mà log vẫn báo "thành công". Phát hiện bằng cách đối chiếu danh sách chương thực tế có trong file dữ liệu, không tin log của công cụ.
- **Audio cũ bị giữ lại nhầm dù nội dung đã sửa**: cơ chế tái sử dụng audio đã tổng hợp trước đó (để tiết kiệm thời gian, không phải đọc lại từ đầu mỗi lần sửa) dựa trên so khớp mã định danh câu; khi cấu trúc đoạn văn thay đổi, một số câu vô tình có cùng mã định danh với câu cũ dù nội dung đã khác hoàn toàn — dẫn đến việc audio SAI vẫn được giữ nguyên mà không được tái tạo lại, trong khi văn bản hiển thị thì đã đúng. Không thể phát hiện qua số liệu tự báo cáo của công cụ; phải tự kiểm tra chéo bằng cách so sánh thời điểm sửa file văn bản với thời điểm tạo file audio tương ứng cho từng trường hợp nghi ngờ.

### 6.3. Phát âm tiếng Anh trong giọng đọc tiếng Việt

- Sách viết nhiều về văn hoá poker Mỹ nên có rất nhiều tên người, địa danh, thuật ngữ tiếng Anh (hơn 50 tên riêng khác nhau chỉ trong khoảng 2/3 đầu sách). Giọng piper tiếng Việt thuần áp quy tắc phát âm tiếng Việt lên nguyên văn tiếng Anh, nghe sai/gượng.
- Riêng từ **"poker"** — từ khoá trung tâm của cả cuốn sách — xuất hiện **243 lần**.
- **Giải pháp**: xây dựng một từ điển thay thế phát âm, áp dụng **chỉ cho phần văn bản đưa vào bộ tổng hợp giọng nói**, hoàn toàn không thay đổi chữ hiển thị trong sách (đảm bảo văn bản DTBook vẫn đúng chính tả gốc). Ví dụ: "poker" → phát âm "pô kơ"; "Pennsylvania" → phát âm "Pen sồn vây nia". Ưu tiên xử lý theo tần suất xuất hiện — xử lý "poker" trước tiên, chỉ tái tạo lại đúng 222 câu bị ảnh hưởng (không tái tạo lại toàn bộ sách).
- **Giới hạn còn tồn tại**: các cách phát âm này là suy đoán hợp lý dựa trên quy ước phiên âm tiếng Việt thông dụng, **chưa được người nghe bản ngữ xác nhận từng mục** vì không thể tự nghe lại kết quả trong quá trình xây dựng.

## 7. Phương pháp kiểm tra chất lượng (QA)

Ba lớp kiểm tra được áp dụng, vì đã xác định rõ điểm tin cậy OCR là **không đủ** để đảm bảo chất lượng:

1. **Kiểm tra cấu trúc tự động**: liên kết giữa SMIL (audio) – DTBook (văn bản) – NCX (điều hướng) phải khớp id với nhau; số trang trong NCX phải đúng; mã ISBN (`dc:Identifier`) phải thống nhất giữa tất cả các chương của cùng một sách.
2. **Đo thời lượng audio thật tự động**: quét toàn bộ audio đã tổng hợp, cộng dồn theo từng thành viên phụ trách, so sánh với yêu cầu tối thiểu 1 giờ/người.
3. **Nghe trực tiếp + đối chiếu ảnh scan gốc**: kênh hiệu quả nhất trên thực tế — nhiều lỗi nghiêm trọng nhất (mục 6.1) chỉ được phát hiện qua việc trực tiếp nghe thấy đoạn đọc kỳ lạ, sau đó truy ngược lại đúng trang scan để xác minh và sửa.

## 8. Kết quả đạt được

### 8.1. Phạm vi nội dung

- Toàn bộ 322 trang sách đã được OCR và xử lý (100%).
- Cấu trúc sách xác định được đầy đủ: Dẫn Nhập + 6 chương chính (đúng theo Mục Lục gốc) + phần phụ lục cuối sách.
- **7 phần được dựng thành sách nói hoàn chỉnh**: Dẫn Nhập, Chương 1–6.
- **Phần phụ lục cuối sách chủ động không thực hiện** (Lời Cảm Ơn trang 283–290, Chú Thích trang 291–304, Danh Mục Sách Tham Khảo trang 305–319, bìa sau trang 320–322): giá trị nghe thấp (danh sách trích dẫn/tên riêng dày đặc), trong khi yêu cầu thời lượng đã vượt xa mức tối thiểu.

### 8.2. Bảng thời lượng audio theo từng chương

| Chương | Tiêu đề | Phụ trách (MSSV) | Thời lượng audio thật |
|---|---|---|---|
| Dẫn Nhập | Vì Sao Đây Không Phải Là Một Cuốn Sách Viết Về Poker | 25C11016 | 5 phút 54 giây |
| Chương 1 | Cuộc Đời Là Một Ván Poker, Không Phải Một Ván Cờ Vua | 25C11016 | 54 phút 31 giây |
| Chương 2 | Muốn Cược Không? | 25C11003 | 1 giờ 04 phút 49 giây |
| Chương 3 | Đặt Cược Để Học Hỏi - Phân Loại Tương Lai Đã Diễn Ra | 25C11003 | 1 giờ 19 phút 27 giây |
| Chương 4 | Hệ Thống Bạn Cùng Tiến | 25C11003 | 57 phút 40 giây |
| Chương 5 | Bất Đồng Ý Kiến Để Chiến Thắng | 25C11016 | 42 phút 04 giây |
| Chương 6 | Những Cuộc Phiêu Lưu Du Hành Thời Gian Trong Tâm Trí | 25C11016 | 1 giờ 37 phút 45 giây |

### 8.3. Tổng hợp theo thành viên

| MSSV | Các phần phụ trách | Tổng thời lượng | Yêu cầu tối thiểu | Kết quả |
|---|---|---|---|---|
| 25C11016 | Dẫn Nhập, Chương 1, Chương 5, Chương 6 | 3 giờ 20 phút 15 giây | 1 giờ | Đạt (vượt 2h20m) |
| 25C11003 | Chương 2, Chương 3, Chương 4 | 3 giờ 21 phút 56 giây | 1 giờ | Đạt (vượt 2h21m) |

**Tổng cộng toàn bộ sách: 6 giờ 42 phút 10 giây** audio thật, so với yêu cầu tối thiểu 2 giờ (2 thành viên × 1 giờ) — vượt hơn 3 lần.

### 8.4. Metadata & cấu trúc nộp bài

Metadata Dublin Core đầy đủ, đúng biểu mẫu môn học, nhúng vào file `.opf` của từng chương:

| Trường | Giá trị |
|---|---|
| dc:Title | (tên chương tương ứng) |
| dc:Source / dc:Identifier | 9780735216358 (dùng chung mọi chương) |
| dc:Creator | Annie Duke |
| dc:Language | vi |
| dc:Publisher | NXB Trẻ |
| dc:Date | 2018-02-06 |
| dc:Subject | Tâm lý học & Phát triển cá nhân |
| dc:Description | (mô tả sách, xem mục 1) |

Cấu trúc thư mục nộp bài:
```
25C11016_25C11003/
├── Tu_Duy_Dat_Cuoc-intro/
│   ├── Tu_Duy_Dat_Cuoc.zip
│   └── Tu_Duy_Dat_Cuoc_sha256sums.txt
├── Tu_Duy_Dat_Cuoc-Chuong 1/
├── Tu_Duy_Dat_Cuoc-Chuong 2/
├── Tu_Duy_Dat_Cuoc-Chuong 3/
├── Tu_Duy_Dat_Cuoc-Chuong 4/
├── Tu_Duy_Dat_Cuoc-Chuong 5/
└── Tu_Duy_Dat_Cuoc-Chuong 6/
```
Mỗi thư mục chương chứa một file `.zip` (gồm `.dtbook.xml`, `.smil`, `.ncx`, `.opf`, thư mục `audio/*.mp3`, ảnh bìa) và một file `_sha256sums.txt` (mã băm SHA-256 của từng file bên trong, theo đúng quy định môn học).

## 9. Hạn chế và hướng phát triển

1. **Phần phụ lục chưa thực hiện** (xem mục 8.1) — có thể bổ sung nếu có thêm thời gian, nhưng không bắt buộc để đạt yêu cầu.
2. **Chưa chạy trình kiểm tra chính thức của DAISY Pipeline 2** — mới chỉ có bộ kiểm tra nội bộ tự viết (kiểm tra liên kết id, số trang, ISBN thống nhất). DAISY Pipeline 2 đã được tải về nhưng cần cài đặt hoàn tất qua giao diện đồ hoạ để chạy kiểm định chính thức.
3. **Từ điển phiên âm tiếng Anh cho giọng đọc chưa được xác nhận đầy đủ bởi người nghe** — là suy đoán hợp lý dựa trên quy ước phiên âm thông dụng, cần nghe và tinh chỉnh thêm nếu có thời gian.
4. **Chỉ mới đối chiếu thủ công 6/6 trang mở đầu chương với ảnh scan gốc** (nơi phát hiện lỗi nặng nhất); các trang thân bài còn lại (~250+ trang) mới được kiểm tra chọn lọc qua nghe thử, chưa đối chiếu toàn bộ từng trang — mức lỗi còn lại ước tính ở mức sai dấu/từ đơn lẻ thông thường của OCR (~85–92% độ chính xác).
5. **Vấn đề bản quyền**: đây là bản dịch tiếng Việt đang còn thời hạn bản quyền (Annie Duke, NXB Trẻ) — cần xác nhận môn học đã có cơ chế cho phép sử dụng cho mục đích học thuật/phi thương mại.

## 10. Kết luận

Đồ án đã xây dựng thành công một pipeline tự động hoàn chỉnh, chuyển đổi một cuốn sách 322 trang từ bản scan ảnh thuần (không có lớp văn bản) sang sách nói điện tử chuẩn DAISY 3, đạt vượt xa yêu cầu về thời lượng (6h42m so với 2h yêu cầu). Trong quá trình thực hiện, nhóm đã chủ động phát hiện và xử lý nhiều lớp vấn đề khác nhau — từ chất lượng OCR không đồng đều (đặc biệt là lỗi hệ thống ở các trang mở đầu chương mà chỉ số tin cậy tự động không phát hiện được), đến các lỗi kỹ thuật tự phát sinh trong chính pipeline (ghi đè dữ liệu, giữ nhầm audio cũ), và hạn chế cố hữu của công nghệ chuyển giọng nói tiếng Việt khi gặp thuật ngữ tiếng Anh. Phương pháp xuyên suốt là **không tin tuyệt đối vào bất kỳ số liệu tự động nào** (độ tin cậy OCR, log "thành công" của công cụ, số liệu tái sử dụng audio) mà luôn đối chiếu bằng một nguồn độc lập (ảnh scan gốc, danh sách thực tế, thời gian sửa file) trước khi kết luận một phần nội dung là chính xác.
