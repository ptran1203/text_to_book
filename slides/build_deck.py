# -*- coding: utf-8 -*-
"""
Build the presentation deck with python-pptx (this machine has no Node/
pptxgenjs or LibreOffice, so the skill's usual toolchain isn't available -
building directly with python-pptx and being conservative on sizing/spacing
since there's no automated visual-QA render step here).
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
import copy

# ----------------------------------------------------------------- palette
NAVY = RGBColor(0x1E, 0x27, 0x61)       # primary - dark bg / titles
ICE = RGBColor(0xCA, 0xDC, 0xFC)        # secondary - light accents on dark
AMBER = RGBColor(0xF2, 0xA9, 0x3B)      # accent - stat highlights, icon fills
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
INK = RGBColor(0x1A, 0x1A, 0x2E)        # body text on light bg
MUTED = RGBColor(0x6B, 0x70, 0x8C)      # captions / secondary text
CARD_BG = RGBColor(0xF3, 0xF5, 0xFC)    # light card fill
LINE = RGBColor(0xDD, 0xE2, 0xF0)

FONT_HEAD = "Cambria"
FONT_BODY = "Calibri"

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
BLANK = prs.slide_layouts[6]


def add_slide(bg=WHITE):
    s = prs.slides.add_slide(BLANK)
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    r.fill.solid()
    r.fill.fore_color.rgb = bg
    r.line.fill.background()
    r.shadow.inherit = False
    # send to back
    sp = r._element
    sp.getparent().remove(sp)
    s.shapes._spTree.insert(2, sp)
    return s


def box(slide, x, y, w, h, fill=None, line=None, line_w=None, shadow=False, radius=None):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    sh = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    if radius:
        try:
            sh.adjustments[0] = radius
        except Exception:
            pass
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(line_w or 1)
    sh.shadow.inherit = False
    if shadow:
        el = sh._element.spPr
        effect = el.makeelement(qn('a:effectLst'), {})
        outer = effect.makeelement(qn('a:outerShdw'), {
            'blurRad': '90000', 'dist': '30000', 'dir': '5400000', 'rotWithShape': '0'
        })
        clr = outer.makeelement(qn('a:srgbClr'), {'val': '1E2761'})
        alpha = clr.makeelement(qn('a:alpha'), {'val': '20000'})
        clr.append(alpha)
        outer.append(clr)
        effect.append(outer)
        el.append(effect)
    return sh


def circle(slide, cx, cy, d, fill=AMBER):
    sh = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx - d / 2), Inches(cy - d / 2), Inches(d), Inches(d))
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def text(slide, x, y, w, h, s, size=16, color=INK, bold=False, italic=False,
         font=FONT_BODY, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, line_spacing=1.0,
         space_after=0, wrap=True):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    lines = s.split("\n")
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        p.space_after = Pt(space_after)
        r = p.add_run()
        r.text = ln
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.italic = italic
        r.font.name = font
        r.font.color.rgb = color
    return tb


def bullets(slide, x, y, w, h, items, size=14, color=INK, font=FONT_BODY,
            space_after=8, line_spacing=1.05, bullet_color=None, bold_lead=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(space_after)
        p.line_spacing = line_spacing
        # bullet char via XML
        pPr = p._pPr
        if pPr is None:
            pPr = p._p.get_or_add_pPr()
        buChar = pPr.makeelement(qn('a:buChar'), {'char': '\u2022'})
        buFont = pPr.makeelement(qn('a:buFont'), {'typeface': font})
        buClr = pPr.makeelement(qn('a:buClr'), {})
        srgb = buClr.makeelement(qn('a:srgbClr'), {'val': '%02X%02X%02X' % ((bullet_color or AMBER)[0], (bullet_color or AMBER)[1], (bullet_color or AMBER)[2]) if isinstance(bullet_color or AMBER, tuple) else str(bullet_color or AMBER)})
        pPr.append(buFont)
        pPr.append(buChar)
        pPr.set('indent', '-182880')
        pPr.set('marL', '182880')
        if isinstance(item, tuple):
            lead, rest = item
            r1 = p.add_run(); r1.text = lead; r1.font.bold = True; r1.font.size = Pt(size); r1.font.name = font; r1.font.color.rgb = color
            r2 = p.add_run(); r2.text = rest; r2.font.size = Pt(size); r2.font.name = font; r2.font.color.rgb = color
        else:
            r = p.add_run()
            r.text = item
            r.font.size = Pt(size)
            r.font.name = font
            r.font.color.rgb = color
    return tb


def icon_circle(slide, cx, cy, d, glyph, fill=AMBER, glyph_color=NAVY, glyph_size=None):
    circle(slide, cx, cy, d, fill=fill)
    text(slide, cx - d / 2, cy - d / 2, d, d, glyph, size=glyph_size or int(d * 22),
         color=glyph_color, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, wrap=False)


def kicker(slide, s, x=0.7, y=0.5, color=AMBER):
    text(slide, x, y, 8, 0.4, s.upper(), size=13, color=color, bold=True, font=FONT_BODY)


def title(slide, s, x=0.7, y=0.85, w=11.9, color=NAVY, size=32):
    text(slide, x, y, w, 0.9, s, size=size, color=color, bold=True, font=FONT_HEAD)


def page_number(slide, n):
    text(slide, 12.6, 7.08, 0.6, 0.3, str(n), size=11, color=MUTED, align=PP_ALIGN.RIGHT)


# ======================================================================
# SLIDE 1 - Title
# ======================================================================
s = add_slide(NAVY)
circle(s, 12.6, -0.6, 3.2, fill=RGBColor(0x27, 0x33, 0x7A))
circle(s, -0.6, 7.9, 2.6, fill=RGBColor(0x27, 0x33, 0x7A))
text(s, 0.9, 1.7, 11.5, 0.5, "ĐỒ ÁN MÔN HỌC  ·  CHUYỂN ĐỔI SÁCH NÓI CHUẨN DAISY", size=15, color=AMBER, bold=True)
text(s, 0.9, 2.3, 11.5, 1.9, "Tư Duy Đặt Cược", size=54, color=WHITE, bold=True, font=FONT_HEAD)
text(s, 0.9, 3.5, 11.5, 0.8, "Xây dựng sách nói chuẩn DAISY 3 từ bản scan tiếng Việt", size=20, color=ICE)
box(s, 0.9, 4.6, 5.6, 0.02, fill=None)
text(s, 0.9, 4.9, 6.0, 0.4, "NHÓM THỰC HIỆN", size=12, color=AMBER, bold=True)
text(s, 0.9, 5.25, 6.0, 0.5, "MSSV: 25C11016  ·  25C11003", size=16, color=WHITE)
text(s, 7.2, 4.9, 5.2, 0.4, "SÁCH GỐC", size=12, color=AMBER, bold=True)
text(s, 7.2, 5.25, 5.2, 0.5, "Annie Duke — NXB Trẻ, 2018/2020", size=16, color=WHITE)

# ======================================================================
# SLIDE 2 - Muc tieu & dau vao
# ======================================================================
s = add_slide()
kicker(s, "Mục tiêu & Đầu vào")
title(s, "Từ bản scan không có chữ, đến sách nói chuẩn quốc tế")
box(s, 0.7, 1.9, 7.0, 4.8, fill=CARD_BG, radius=0.04)
text(s, 1.0, 2.15, 6.4, 0.4, "MỤC TIÊU", size=13, color=AMBER, bold=True)
bullets(s, 1.0, 2.6, 6.4, 3.9, [
    "Chuyển sách in (bản scan) sang sách nói điện tử theo chuẩn DAISY 3 (ANSI/NISO Z39.86)",
    "Đồng bộ văn bản – audio – điều hướng (chương/trang/câu) cho người khiếm thị / khó đọc chữ in",
    "Mỗi thành viên đóng góp tối thiểu 1 giờ audio thật, đóng gói đúng quy cách nộp bài môn học",
], size=15, space_after=14, line_spacing=1.15)

box(s, 8.0, 1.9, 4.6, 4.8, fill=NAVY, radius=0.04)
text(s, 8.3, 2.15, 4.0, 0.4, "ĐẦU VÀO", size=13, color=AMBER, bold=True)
text(s, 8.3, 2.65, 4.0, 1.6, "data/book.pdf", size=20, color=WHITE, bold=True, font="Consolas")
text(s, 8.3, 3.25, 4.0, 1.8,
     "322 trang — ảnh scan thuần,\nKHÔNG có lớp chữ (text layer)",
     size=14, color=ICE, line_spacing=1.2)
box(s, 8.3, 4.35, 4.0, 0.02, fill=RGBColor(0x35, 0x40, 0x85))
text(s, 8.3, 4.55, 4.0, 1.9,
     "Xác nhận bằng cách đọc content stream PDF: không có font, không có lệnh vẽ chữ (Tj/TJ) — mỗi trang chỉ là một lệnh vẽ ảnh.",
     size=12.5, color=ICE, italic=True, line_spacing=1.25)
text(s, 8.3, 6.2, 4.0, 0.4, "→ Bắt buộc phải OCR toàn bộ", size=13, color=AMBER, bold=True)
page_number(s, 2)

# ======================================================================
# SLIDE 3 - Pipeline 9 buoc
# ======================================================================
s = add_slide()
kicker(s, "Phương pháp")
title(s, "Quy trình 9 bước, tự động hoá theo từng lượt chạy (run)")

steps = [
    ("1", "Tách trang", "PDF → ảnh từng trang"),
    ("2", "OCR", "Tesseract dò dòng\n+ VietOCR nhận chữ"),
    ("3", "Làm sạch", "Sửa lỗi khoảng trắng,\nchuẩn hoá Unicode"),
    ("4", "Cấu trúc", "Dò tiêu đề chương,\nsinh DTBook XML"),
    ("5", "Text-to-Speech", "piper (offline)\n1 câu = 1 file mp3"),
    ("6", "Đồng bộ SMIL", "Khớp câu văn bản\n↔ đoạn audio"),
    ("7", "Đóng gói DAISY 3", "DTBook+SMIL+NCX+OPF"),
    ("8", "Kiểm tra", "Đối chiếu nội bộ +\nDAISY Pipeline 2"),
    ("9", "Nộp bài", "Zip + SHA-256 theo\nMSSV/ISBN"),
]
cols = 3
cw, ch_ = 3.85, 1.55
gx, gy = 0.35, 0.3
x0, y0 = 0.7, 1.95
for i, (num, name, desc) in enumerate(steps):
    r, c = divmod(i, cols)
    x = x0 + c * (cw + gx)
    y = y0 + r * (ch_ + gy)
    box(s, x, y, cw, ch_, fill=CARD_BG, radius=0.08)
    icon_circle(s, x + 0.55, y + ch_ / 2, 0.62, num, fill=AMBER, glyph_color=NAVY, glyph_size=20)
    text(s, x + 1.0, y + 0.16, cw - 1.15, 0.4, name, size=15, color=NAVY, bold=True, font=FONT_HEAD)
    text(s, x + 1.0, y + 0.56, cw - 1.15, ch_ - 0.6, desc, size=11.5, color=MUTED, line_spacing=1.1)
page_number(s, 3)

# ======================================================================
# SLIDE 4 - Quyet dinh ky thuat
# ======================================================================
s = add_slide()
kicker(s, "Quyết định kỹ thuật")
title(s, "4 lựa chọn định hình cả pipeline")

decisions = [
    ("OCR", "Tesseract dò dòng + VietOCR nhận chữ",
     "VietOCR đọc dấu tiếng Việt chính xác hơn hẳn (~0.90+ độ tin cậy trên trang thân bài) so với để Tesseract tự nhận chữ."),
    ("TTS", "piper (offline), giọng vais1000/medium",
     "Chất lượng cao nhất hiện có cho tiếng Việt trong piper, chạy offline — không cần API hay trả phí."),
    ("Đóng gói", "Mỗi chương = 1 quyển DAISY 3 riêng, chung 1 ISBN",
     "Theo đúng quy định môn học cho sách dài, chia theo chương/hồi."),
    ("Công cụ chuẩn", "Tự dựng DTBook/SMIL/NCX/OPF bằng Python",
     "piper không phải bộ máy TTS mà DAISY Pipeline 2 hỗ trợ trực tiếp — DP2 chỉ dùng để kiểm tra ở bước cuối."),
]
y = 1.95
for label, head, sub in decisions:
    box(s, 0.7, y, 11.95, 1.18, fill=CARD_BG, radius=0.06)
    box(s, 0.7, y, 0.09, 1.18, fill=AMBER)
    text(s, 1.05, y + 0.13, 2.0, 0.9, label.upper(), size=13, color=AMBER, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 3.1, y + 0.12, 9.35, 0.5, head, size=16, color=NAVY, bold=True, font=FONT_HEAD)
    text(s, 3.1, y + 0.56, 9.35, 0.55, sub, size=12.5, color=MUTED, line_spacing=1.1)
    y += 1.32
page_number(s, 4)

# ======================================================================
# SLIDE 5 - Thach thuc 1: OCR chat luong khong deu
# ======================================================================
s = add_slide()
kicker(s, "Thách thức 1 / 3")
title(s, "OCR: điểm tin cậy cao vẫn có thể sai hoàn toàn")

text(s, 0.7, 1.8, 11.9, 0.85,
     "Trang thân bài bình thường: ~85–92% độ tin cậy, lỗi chủ yếu là sai dấu đơn lẻ (Tồi → Tôi). Nhưng trang MỞ ĐẦU mỗi chương (tiêu đề in đậm/chữ lớn) thường bị lỗi nặng hơn hẳn — và điểm tin cậy KHÔNG phát hiện được.",
     size=13, color=INK, line_spacing=1.2)

box(s, 0.7, 2.85, 5.85, 3.85, fill=RGBColor(0xFD, 0xEC, 0xEC), radius=0.05)
text(s, 1.0, 3.05, 5.3, 0.4, "TRƯỚC — OCR gốc (độ tin cậy 0.87)", size=12, color=RGBColor(0xB0, 0x2A, 0x2A), bold=True)
text(s, 1.0, 3.5, 5.3, 3.0,
     "“Vì sao đây không phải là\n031001001001201\nmột cuốn sách viết về poker\nNim 26 sáu truổi, rôi nghi rằng\nrương hi của mình đã được\nhoad định rất rõ ràng.”",
     size=14, color=RGBColor(0x7A, 0x1E, 0x1E), italic=True, line_spacing=1.3, font="Consolas")

box(s, 6.8, 2.85, 5.85, 3.85, fill=RGBColor(0xEA, 0xF7, 0xEE), radius=0.05)
text(s, 7.1, 3.05, 5.3, 0.4, "SAU — đối chiếu ảnh scan gốc, sửa tay", size=12, color=RGBColor(0x22, 0x7A, 0x43), bold=True)
text(s, 7.1, 3.5, 5.3, 2.0,
     "“Năm 26 sáu tuổi, tôi nghĩ rằng\ntương lai của mình đã được\nhoạch định rất rõ ràng.”",
     size=16, color=RGBColor(0x18, 0x4D, 0x2C), italic=True, line_spacing=1.35, font="Consolas")
text(s, 7.1, 5.6, 5.3, 1.0,
     "Chuỗi số bị bịa ra hoàn toàn không tồn tại trên trang — xác nhận bằng cách xem trực tiếp ảnh scan, không tin OCR.",
     size=11.5, color=MUTED, italic=True, line_spacing=1.15)
page_number(s, 5)

# ======================================================================
# SLIDE 6 - Thach thuc 2: loi pipeline
# ======================================================================
s = add_slide()
kicker(s, "Thách thức 2 / 3")
title(s, "Lỗi hệ thống tự tạo ra — không phải do OCR")

bugs = [
    ("Số thập phân vỡ đôi", "Quy tắc \u201cthêm khoảng trắng sau dấu câu\u201d biến \u201c6,4 triệu\u201d thành \u201c6, 4 triệu\u201d → giọng đọc tách thành 2 số.",
     "Sửa quy tắc để loại trừ trường hợp dấu câu nằm giữa hai chữ số."),
    ("Dữ liệu bị ghi đè", "Build từng chương riêng lẻ trong 1 lượt chạy chung vô tình chỉ giữ lại dữ liệu của chương chạy sau cùng.",
     "Phát hiện bằng cách so khớp danh sách chương thực tế, không tin log \u201cthành công\u201d."),
    ("Audio cũ bị giữ nhầm", "Cơ chế \u201cresume\u201d bỏ qua tái tạo audio khi câu mới trùng ID ngẫu nhiên với câu cũ đã xoá nội dung.",
     "Kiểm tra chéo bằng thời gian sửa file thay vì tin số liệu resume báo cáo."),
]
y = 1.95
for head, prob, fix in bugs:
    box(s, 0.7, y, 11.95, 1.55, fill=CARD_BG, radius=0.06)
    icon_circle(s, 1.35, y + 0.775, 0.7, "!", fill=RGBColor(0xE3, 0x5B, 0x5B), glyph_color=WHITE, glyph_size=26)
    text(s, 2.15, y + 0.14, 10.2, 0.4, head, size=15.5, color=NAVY, bold=True, font=FONT_HEAD)
    text(s, 2.15, y + 0.55, 10.2, 0.5, prob, size=12, color=INK, line_spacing=1.1)
    text(s, 2.15, y + 1.05, 10.2, 0.45, "→  " + fix, size=12, color=RGBColor(0x1E, 0x7A, 0x4A), bold=True, line_spacing=1.1)
    y += 1.68
page_number(s, 6)

# ======================================================================
# SLIDE 7 - Thach thuc 3: phat am tieng Anh
# ======================================================================
s = add_slide()
kicker(s, "Thách thức 3 / 3")
title(s, "Giọng đọc tiếng Việt không đọc tốt tên riêng tiếng Anh")

box(s, 0.7, 1.95, 5.6, 4.75, fill=CARD_BG, radius=0.05)
text(s, 1.0, 2.2, 5.0, 0.4, "VẤN ĐỀ", size=13, color=AMBER, bold=True)
bullets(s, 1.0, 2.65, 5.0, 3.9, [
    "Sách nói về văn hoá poker Mỹ → rất nhiều tên người, địa danh, thuật ngữ tiếng Anh",
    "Từ \u201cpoker\u201d xuất hiện 243 lần trong toàn sách",
    "piper (giọng thuần Việt) áp quy tắc phát âm tiếng Việt lên nguyên văn tiếng Anh → nghe sai/kỳ",
], size=13.5, space_after=12, line_spacing=1.15)

box(s, 6.5, 1.95, 6.15, 4.75, fill=NAVY, radius=0.05)
text(s, 6.8, 2.2, 5.5, 0.4, "GIẢI PHÁP", size=13, color=AMBER, bold=True)
text(s, 6.8, 2.65, 5.5, 0.5, "Từ điển phiên âm — chỉ áp dụng cho audio", size=14.5, color=WHITE, bold=True)
box(s, 6.8, 3.3, 5.5, 1.5, fill=RGBColor(0x28, 0x32, 0x78), radius=0.06)
text(s, 7.05, 3.45, 5.0, 0.35, "chữ hiển thị (không đổi)      →      giọng đọc", size=10.5, color=ICE)
text(s, 7.05, 3.8, 2.3, 0.4, "poker", size=17, color=WHITE, font="Consolas")
text(s, 9.5, 3.8, 2.4, 0.4, "pô kơ", size=17, color=AMBER, bold=True, font="Consolas")
text(s, 7.05, 4.25, 2.3, 0.4, "Pennsylvania", size=14, color=WHITE, font="Consolas")
text(s, 9.5, 4.25, 2.4, 0.4, "Pen sồn vây nia", size=13, color=AMBER, bold=True, font="Consolas")
text(s, 6.8, 5.0, 5.5, 1.5,
     "Ưu tiên xử lý theo tần suất xuất hiện — \u201cpoker\u201d làm trước tiên (243 lần → 222 câu tái tạo lại có chọn lọc, không làm lại cả sách).",
     size=12.5, color=ICE, line_spacing=1.25)
page_number(s, 7)

# ======================================================================
# SLIDE 8 - Phuong phap QA
# ======================================================================
s = add_slide()
kicker(s, "Chất lượng")
title(s, "3 lớp kiểm tra — vì điểm tin cậy OCR là chưa đủ")

qa = [
    ("1", "Kiểm tra tự động", "Liên kết SMIL ↔ DTBook ↔ NCX khớp nhau, số trang đúng, mã ISBN thống nhất giữa các chương."),
    ("2", "Đo thời lượng thật", "Tự động cộng audio thật theo từng thành viên, so với yêu cầu tối thiểu 1 giờ/người."),
    ("3", "Nghe & đối chiếu ảnh gốc", "Kênh hiệu quả nhất: nghe audio, nghi ngờ chỗ nào thì mở lại đúng trang scan để xác minh."),
]
x = 0.7
w = 3.85
for num, head, desc in qa:
    box(s, x, 2.1, w, 4.4, fill=CARD_BG, radius=0.06)
    icon_circle(s, x + w / 2, 2.75, 0.85, num, fill=AMBER, glyph_color=NAVY, glyph_size=30)
    text(s, x + 0.25, 3.35, w - 0.5, 0.6, head, size=16, color=NAVY, bold=True, align=PP_ALIGN.CENTER, font=FONT_HEAD)
    text(s, x + 0.3, 4.0, w - 0.6, 2.3, desc, size=12.5, color=MUTED, align=PP_ALIGN.CENTER, line_spacing=1.25)
    x += w + 0.3
page_number(s, 8)

# ======================================================================
# SLIDE 9 - Ket qua (stat slide, dark bg)
# ======================================================================
s = add_slide(NAVY)
circle(s, 12.9, 7.9, 3.0, fill=RGBColor(0x27, 0x33, 0x7A))
kicker(s, "Kết quả", color=AMBER)
title(s, "Toàn bộ 322 trang, 7 phần nội dung, vượt xa yêu cầu", color=WHITE)

stats = [
    ("322", "trang sách\nđã xử lý 100%"),
    ("7", "phần nội dung\n(Dẫn Nhập + 6 chương)"),
    ("6h42m", "audio thật\n(so với 2h yêu cầu)"),
    ("2", "thành viên,\nmỗi người > 1 giờ"),
]
x = 0.7
w = 2.95
for num, label in stats:
    text(s, x, 2.3, w, 1.3, num, size=44, color=AMBER, bold=True, font=FONT_HEAD, align=PP_ALIGN.LEFT)
    text(s, x, 3.5, w, 1.0, label, size=13, color=ICE, line_spacing=1.2)
    x += w + 0.25

box(s, 0.7, 4.9, 11.95, 0.02, fill=RGBColor(0x35, 0x40, 0x85))
text(s, 0.7, 5.15, 11.95, 1.9,
     "Mỗi chương đóng gói thành một quyển DAISY 3 độc lập (DTBook + SMIL + NCX + OPF), dùng chung một mã ISBN thật (9780735216358) và metadata đầy đủ theo đúng biểu mẫu môn học (Title, Source, Creator, Subject, Description, Publisher, Date, Language).",
     size=14, color=WHITE, line_spacing=1.3)
page_number(s, 9)

# ======================================================================
# SLIDE 10 - Cau truc nop bai
# ======================================================================
s = add_slide()
kicker(s, "Sản phẩm nộp bài")
title(s, "Cấu trúc thư mục & metadata theo đúng quy định")

box(s, 0.7, 1.95, 6.5, 4.75, fill=RGBColor(0x11, 0x14, 0x2E), radius=0.05)
mono_lines = [
    "25C11016_25C11003/",
    "├─ Tu_Duy_Dat_Cuoc-intro/",
    "│   ├─ Tu_Duy_Dat_Cuoc.zip",
    "│   └─ Tu_Duy_Dat_Cuoc_sha256sums.txt",
    "├─ Tu_Duy_Dat_Cuoc-Chuong 1/",
    "├─ Tu_Duy_Dat_Cuoc-Chuong 2/",
    "├─ ...",
    "└─ Tu_Duy_Dat_Cuoc-Chuong 6/",
]
text(s, 1.0, 2.2, 5.9, 4.3, "\n".join(mono_lines), size=14.5, color=RGBColor(0x9C, 0xE8, 0xB8), font="Consolas", line_spacing=1.5)

box(s, 7.4, 1.95, 5.25, 4.75, fill=CARD_BG, radius=0.05)
text(s, 7.7, 2.2, 4.7, 0.4, "METADATA (dc-metadata)", size=13, color=AMBER, bold=True)
meta_rows = [
    ("Source (ISBN)", "9780735216358"),
    ("Creator", "Annie Duke"),
    ("Publisher", "NXB Trẻ"),
    ("Date", "2018-02-06"),
    ("Language", "vi"),
    ("Subject", "Tâm lý học & PT cá nhân"),
]
yy = 2.7
for k, v in meta_rows:
    text(s, 7.7, yy, 2.1, 0.4, k, size=12, color=MUTED, bold=True)
    text(s, 9.9, yy, 2.6, 0.4, v, size=12, color=INK, font="Consolas")
    yy += 0.5
text(s, 7.7, yy + 0.1, 4.7, 0.9, "→ ISBN dùng chung khắc phục lỗi \u201cdc:Identifier khác nhau giữa các chương\u201d.",
     size=11.5, color=RGBColor(0x1E, 0x7A, 0x4A), italic=True, line_spacing=1.2)
page_number(s, 10)

# ======================================================================
# SLIDE 11 - Han che con ton tai
# ======================================================================
s = add_slide()
kicker(s, "Nhìn thẳng vào hạn chế")
title(s, "Những gì chưa hoàn thiện")

limits = [
    "Phần phụ lục (Lời Cảm Ơn, Chú Thích, Danh Mục Sách Tham Khảo, ~37 trang) chưa được đọc — giá trị nghe thấp, yêu cầu thời lượng đã vượt xa nên không bắt buộc.",
    "Chưa chạy trình kiểm tra chính thức của DAISY Pipeline 2 — mới chỉ có kiểm tra nội bộ tự viết.",
    "Từ điển phiên âm tiếng Anh là suy đoán hợp lý, chưa được người nghe bản ngữ xác nhận toàn bộ.",
    "Đây là bản dịch có bản quyền hiện hành — cần xác nhận môn học đã cho phép sử dụng.",
]
bullets(s, 0.7, 2.0, 11.9, 4.8, limits, size=15, space_after=20, line_spacing=1.25, bullet_color=AMBER)
page_number(s, 11)

# ======================================================================
# SLIDE 12 - Demo plan
# ======================================================================
s = add_slide(NAVY)
kicker(s, "Demo trực tiếp", color=AMBER)
title(s, "3 bước trình diễn", color=WHITE)

demo_steps = [
    ("1", "Nghe audio mẫu", "Phát trực tiếp 1 câu đã sửa lỗi (vd. câu mở đầu Dẫn Nhập) — so sánh trước/sau."),
    ("2", "Mở sách trong Thorium Reader", "Giải nén 1 chương .zip, mở book.opf — trình chiếu điều hướng đồng bộ chữ–giọng theo câu, theo trang."),
    ("3", "Chỉ ra một lỗi đã tìm & sửa", "Đối chiếu ảnh scan gốc với bản văn bản đã làm sạch, minh hoạ quy trình QA thực tế."),
]
y = 2.2
for num, head, desc in demo_steps:
    icon_circle(s, 1.35, y + 0.55, 0.85, num, fill=AMBER, glyph_color=NAVY, glyph_size=30)
    text(s, 2.2, y + 0.05, 10.2, 0.45, head, size=19, color=WHITE, bold=True, font=FONT_HEAD)
    text(s, 2.2, y + 0.55, 10.2, 0.55, desc, size=13.5, color=ICE, line_spacing=1.2)
    y += 1.5
page_number(s, 12)

# ======================================================================
# SLIDE 13 - Thank you
# ======================================================================
s = add_slide(NAVY)
circle(s, 12.6, -0.6, 3.2, fill=RGBColor(0x27, 0x33, 0x7A))
circle(s, -0.6, 7.9, 2.6, fill=RGBColor(0x27, 0x33, 0x7A))
text(s, 0.9, 2.9, 11.5, 1.2, "Cảm ơn thầy/cô đã lắng nghe", size=40, color=WHITE, bold=True, font=FONT_HEAD)
text(s, 0.9, 3.9, 11.5, 0.6, "Câu hỏi & thảo luận", size=18, color=AMBER)
text(s, 0.9, 5.6, 11.5, 0.5, "MSSV: 25C11016  ·  25C11003      |      Tư Duy Đặt Cược — DAISY 3", size=13, color=ICE)

prs.save(r"D:\Master\hk2\text_to_book\slides\DAISY3_TuDuyDatCuoc.pptx")
print("saved")
