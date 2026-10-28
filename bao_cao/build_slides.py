#!/usr/bin/env python3
"""Generate bao_cao/Slide_BTL_INT1422.pptx (15 slides, 16:9) from the project's real artifacts.

Structure follows the 15-minute talk in Bài 12: business question (2') · data (3') ·
warehouse + live OLAP (4') · mining results with evidence (4') · actions & limits (2').
Speaker notes on every slide say what to show / say.

    pip install -r bao_cao/requirements.txt
    python bao_cao/build_slides.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pptx import Presentation  # noqa: E402
from pptx.chart.data import CategoryChartData  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # noqa: E402
from pptx.util import Inches, Pt  # noqa: E402

from report_lib import ART, FIG_DIR, FROM_SCRATCH_MINUTES, ROOT, Facts, architecture_figure, pct, vn, vn_int  # noqa: E402

OUT = HERE / "Slide_BTL_INT1422.pptx"
SHOTS = ART / "dashboard_screenshots"

# Palette: smog charcoal (dominant), alert orange (accent), clean-air teal (support).
INK = RGBColor(0x1F, 0x2A, 0x37)
ORANGE = RGBColor(0xEA, 0x58, 0x0C)
TEAL = RGBColor(0x0F, 0x76, 0x6E)
MUTED = RGBColor(0x64, 0x74, 0x8B)
CARD = RGBColor(0xF1, 0xF5, 0xF9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SOFT_ORANGE = RGBColor(0xFF, 0xED, 0xD5)
SOFT_TEAL = RGBColor(0xCC, 0xFB, 0xF1)
HEAD = "Cambria"
BODY = "Calibri"

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.6)


SUPERSCRIPT = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def sci(p: float) -> str:
    """5.2e-23 → 'p = 5×10⁻²³'"""
    mant, exp = f"{p:.0e}".split("e")
    return f"p = {mant}×10{str(int(exp)).translate(SUPERSCRIPT)}"


class Deck:
    def __init__(self) -> None:
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = W, H
        self.title_only = self.prs.slide_layouts[5]
        self.blank = self.prs.slide_layouts[6]
        self.n = 0

    # --- slide frames ------------------------------------------------------
    def content(self, title: str, section: str, notes: str):
        s = self.prs.slides.add_slide(self.title_only)
        self.n += 1
        t = s.shapes.title
        t.left, t.top, t.width, t.height = MARGIN, Inches(0.35), W - 2 * MARGIN, Inches(0.95)
        t.text_frame.word_wrap = True
        t.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = t.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.runs[0] if p.runs else p.add_run()
        run.text = title
        run.font.name, run.font.size, run.font.bold, run.font.color.rgb = HEAD, Pt(34), True, INK
        self.text(s, section.upper(), MARGIN, Inches(0.12), Inches(6), Inches(0.3), 11, MUTED, bold=True)
        self.text(s, f"{self.n} / 15", W - MARGIN - Inches(1.5), H - Inches(0.45), Inches(1.5), Inches(0.3), 11,
                  MUTED, align=PP_ALIGN.RIGHT)
        s.notes_slide.notes_text_frame.text = notes
        return s

    def dark(self, notes: str):
        s = self.prs.slides.add_slide(self.blank)
        self.n += 1
        bg = s.background.fill
        bg.solid()
        bg.fore_color.rgb = INK
        s.notes_slide.notes_text_frame.text = notes
        return s

    # --- primitives --------------------------------------------------------
    def text(self, slide, text, x, y, w, h, size=16, color=INK, bold=False, italic=False, font=BODY,
             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
        box = slide.shapes.add_textbox(x, y, w, h)
        tf = box.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        tf.margin_left = tf.margin_right = Inches(0.05)
        lines = text if isinstance(text, list) else [text]
        for i, line in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            r = p.add_run()
            r.text = line
            r.font.name, r.font.size, r.font.bold, r.font.italic = font, Pt(size), bold, italic
            r.font.color.rgb = color
        return box

    def bullets(self, slide, items, x, y, w, h, size=16, color=INK, gap=8):
        box = slide.shapes.add_textbox(x, y, w, h)
        tf = box.text_frame
        tf.word_wrap = True
        for i, item in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(gap)
            parts = item if isinstance(item, list) else [("", item)]
            pre = p.add_run()
            pre.text = "▸  "
            pre.font.name, pre.font.size, pre.font.color.rgb, pre.font.bold = BODY, Pt(size), ORANGE, True
            for kind, txt in parts:
                r = p.add_run()
                r.text = txt
                r.font.name, r.font.size, r.font.color.rgb = BODY, Pt(size), color
                r.font.bold = "b" in kind
                r.font.italic = "i" in kind
        return box

    def card(self, slide, x, y, w, h, fill=CARD):
        shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
        shp.adjustments[0] = 0.06
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
        shp.line.fill.background()
        shp.shadow.inherit = False
        return shp

    def stat(self, slide, value, label, x, y, w, color=ORANGE, fill=CARD, h=Inches(1.55), value_size=40):
        self.card(slide, x, y, w, h, fill)
        self.text(slide, value, x + Inches(0.2), y + Inches(0.12), w - Inches(0.4), Inches(0.85), value_size, color,
                  bold=True, font=HEAD)
        self.text(slide, label, x + Inches(0.2), y + Inches(0.92), w - Inches(0.4), h - Inches(0.95), 13, MUTED)

    def picture(self, slide, path: Path, x, y, w=None, h=None):
        return slide.shapes.add_picture(str(path), x, y, width=w, height=h)

    def badge(self, slide, number: str, x, y, color=ORANGE):
        c = slide.shapes.add_shape(MSO_SHAPE.OVAL, x, y, Inches(0.5), Inches(0.5))
        c.fill.solid()
        c.fill.fore_color.rgb = color
        c.line.fill.background()
        tf = c.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = number
        r.font.name, r.font.size, r.font.bold, r.font.color.rgb = BODY, Pt(16), True, WHITE
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE

    def style_chart(self, chart, colors, legend=True):
        chart.font.name = BODY
        chart.font.size = Pt(13)
        chart.font.color.rgb = INK
        chart.has_legend = legend
        if legend:
            chart.legend.position = XL_LEGEND_POSITION.TOP
            chart.legend.include_in_layout = False
            chart.legend.font.size = Pt(13)
        for series, color in zip(chart.plots[0].series, colors):
            series.format.fill.solid()
            series.format.fill.fore_color.rgb = color
        va = chart.value_axis
        va.has_major_gridlines = True
        va.major_gridlines.format.line.color.rgb = RGBColor(0xE2, 0xE8, 0xF0)
        va.format.line.fill.background()
        va.tick_labels.font.size = Pt(12)
        va.tick_labels.font.color.rgb = MUTED
        ca = chart.category_axis
        ca.tick_labels.font.size = Pt(13)
        ca.tick_labels.font.color.rgb = INK
        ca.format.line.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)


def build(f: Facts) -> Presentation:
    d = Deck()
    loc = f.test(f.locked)
    per = f.test("persistence")
    h = f.horizon_h

    # 1 — title ---------------------------------------------------------------
    s = d.dark(
        "Mở đầu (15 giây). Giới thiệu nhóm và đề tài. Câu chính: nhóm xây kho dữ liệu chất lượng không khí và một mô "
        "hình cảnh báo sớm giờ tới khi PM2.5 vượt 115 µg/m³."
    )
    d.text(s, "INT1422 · KHO DỮ LIỆU VÀ KHAI PHÁ DỮ LIỆU", MARGIN, Inches(1.0), Inches(9), Inches(0.4), 14,
           RGBColor(0xFD, 0xBA, 0x74), bold=True)
    d.text(s, ["Kho dữ liệu chất lượng không khí Bắc Kinh", "& cảnh báo sớm PM2.5 vượt ngưỡng"], MARGIN,
           Inches(1.6), Inches(12.1), Inches(2.2), 38, WHITE, bold=True, font=HEAD)
    d.text(s, "420 768 giờ đo · 12 trạm · lược đồ hình sao 4 chiều · phân loại cảnh báo giờ tới", MARGIN,
           Inches(3.95), Inches(11.5), Inches(0.5), 18, RGBColor(0xCB, 0xD5, 0xE1), italic=True)
    d.text(s, ["Nhóm [số nhóm] — [Họ tên 1 · MSSV]  ·  [Họ tên 2 · MSSV]  ·  [Họ tên 3 · MSSV]",
               "Giảng viên: [Họ tên giảng viên]  ·  Học viện Công nghệ Bưu chính Viễn thông"],
           MARGIN, Inches(5.7), Inches(11.5), Inches(1.0), 15, WHITE)

    # 2 — business question ---------------------------------------------------
    s = d.content(
        "Câu hỏi: giờ tới có cần phát cảnh báo không?", "1 · Câu hỏi nghiệp vụ",
        "≈1'45\". Người dùng là trung tâm quan trắc. Quyết định: phát cảnh báo hạn chế hoạt động ngoài trời cho giờ "
        "tới tại từng trạm. Cách làm hiện tại là nhìn số đo hiện tại (persistence), nên luôn trễ 1 giờ và không bao "
        "giờ báo trước được lúc một đợt ô nhiễm bắt đầu.",
    )
    d.card(s, MARGIN, Inches(1.55), Inches(6.6), Inches(4.9), SOFT_ORANGE)
    d.text(s, "“Giờ tới, tại trạm X, PM2.5 có ≥ 115 µg/m³ không?”", MARGIN + Inches(0.35), Inches(1.85),
           Inches(6.0), Inches(1.4), 26, INK, bold=True, italic=True, font=HEAD)
    d.bullets(s, [
        [("b", "Ai dùng: "), ("", "trung tâm quan trắc, trường học, bệnh viện")],
        [("b", "Quyết định: "), ("", "cho/không cho hoạt động ngoài trời")],
        [("b", "Hiện tại: "), ("", "chờ số đo vượt ngưỡng rồi mới báo, luôn trễ 1 giờ")],
    ], MARGIN + Inches(0.35), Inches(3.45), Inches(6.0), Inches(2.8), 17)
    d.stat(s, "79,8 µg/m³", "PM2.5 trung bình 2013–2017 trên 12 trạm", Inches(7.6), Inches(1.55), Inches(5.13))
    d.stat(s, "≈ 1/4", "số giờ có PM2.5 ≥ 115 µg/m³ (ngưỡng \"ô nhiễm trung bình\" theo AQI Trung Quốc)",
           Inches(7.6), Inches(3.2), Inches(5.13))
    d.stat(s, "0%", "số lần bắt đầu đợt ô nhiễm mà cách làm hiện tại báo trước được", Inches(7.6), Inches(4.85),
           Inches(5.13), color=INK)

    # 3 — data ----------------------------------------------------------------
    s = d.content(
        "Dữ liệu: 420 768 giờ đo, nguồn mở, có giấy phép", "2 · Dữ liệu",
        "≈1'. Nguồn chính UCI #501, giấy phép CC BY 4.0, DOI 10.24432/C5RK5G. Nguồn phụ Open-Meteo dùng để lấp "
        "khoảng trống thời tiết và thêm độ che phủ mây. Không có dữ liệu cá nhân. Script tải tự kiểm tra kích "
        "thước file.",
    )
    for i, (v, lab) in enumerate((("420 768", "bản ghi giờ"), ("12", "trạm quan trắc"), ("4 năm", "03/2013 – 02/2017"),
                                  ("12", "thuộc tính đo"))):
        d.stat(s, v, lab, MARGIN + i * Inches(3.08), Inches(1.55), Inches(2.85), color=ORANGE if i == 0 else INK,
               h=Inches(1.4))
    d.card(s, MARGIN, Inches(3.25), Inches(5.9), Inches(2.75))
    d.text(s, "UCI Beijing Multi-Site Air Quality", MARGIN + Inches(0.3), Inches(3.4), Inches(5.4), Inches(0.5), 19,
           TEAL, bold=True)
    d.bullets(s, ["PM2.5, PM10, SO2, NO2, CO, O3 + 5 biến khí tượng + hướng gió",
                  "Chen, S. (2017) · DOI 10.24432/C5RK5G", [("b", "Giấy phép CC BY 4.0")]],
              MARGIN + Inches(0.3), Inches(3.95), Inches(5.4), Inches(2.5), 16)
    d.card(s, Inches(6.83), Inches(3.25), Inches(5.9), Inches(2.75))
    d.text(s, "Open-Meteo Historical Weather", Inches(7.13), Inches(3.4), Inches(5.4), Inches(0.5), 19, TEAL, bold=True)
    d.bullets(s, ["Lấp chỗ thiếu thời tiết + thêm độ che phủ mây", "Tái phân tích ERA5, theo giờ, cùng 12 toạ độ",
                  [("b", "CC BY 4.0, phi thương mại")]],
              Inches(7.13), Inches(3.95), Inches(5.4), Inches(2.5), 16)

    # 4 — cleaning (native chart) -------------------------------------------
    s = d.content(
        "Làm sạch: giữ NULL cho chất ô nhiễm, lấp thời tiết", "2 · Dữ liệu",
        "≈2'. CO thiếu nhiều nhất (4,9%), có chuỗi thiếu dài tới 1 517 giờ, nên không nội suy để tránh bịa dữ liệu. "
        "Thời tiết thiếu ít (≈0,1%) và được lấp từ Open-Meteo, ghi nguồn; sau khi lấp còn 0 ô thiếu. 60 dòng chạm "
        "trần thiết bị được gắn cờ. Khi khai phá: median lấy từ tập train, không lấy từ val/test.",
    )
    cd = CategoryChartData()
    miss = f.missing.sort_values("missing_pct")
    cd.categories = list(miss["variable"])
    cd.add_series("% giá trị thiếu", [round(v, 2) for v in miss["missing_pct"]])
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, MARGIN, Inches(1.45), Inches(6.4), Inches(5.3), cd)
    ch = gf.chart
    d.style_chart(ch, [ORANGE], legend=False)
    ch.has_title = True
    ch.chart_title.text_frame.text = "% giá trị thiếu theo cột (12 trạm)"
    ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(14)
    pl = ch.plots[0]
    pl.has_data_labels = True
    pl.data_labels.number_format = '0.0"%"'
    pl.data_labels.number_format_is_linked = False
    pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    pl.data_labels.font.size = Pt(11)
    pl.gap_width = 60
    d.bullets(s, [
        [("b", "Chất ô nhiễm: "), ("", "giữ NULL + cờ chất lượng; chuỗi thiếu dài tới 343–1 517 giờ, không nội suy")],
        [("b", "Thời tiết, hướng gió: "), ("", "lấp từ Open-Meteo, ghi nguồn; còn 0 ô thiếu")],
        [("b", "Trần thiết bị "), ("", "(999, 10 000): giữ lại, gắn cờ SUSPECT_CAP (60 dòng)")],
        [("b", "Rời rạc hoá: "), ("", "giờ → buổi · ngày → mùa · 16 hướng → 4 phần tư → bắc/nam")],
    ], Inches(7.3), Inches(1.6), Inches(5.4), Inches(5.0), 16, gap=12)

    # 5 — architecture + one command ----------------------------------------
    s = d.content(
        "Toàn bộ chuỗi chạy lại được bằng một lệnh", "2 · Dữ liệu",
        "≈1'. Đi nhanh qua kiến trúc: lake MinIO → staging PostgreSQL → kho dbt → khối và mart → khai phá → ứng dụng. "
        f"Nhấn mạnh yêu cầu bắt buộc: python scripts/run_all.py, đã kiểm chứng từ trạng thái trống ngày 12/10/2026 "
        f"(14/14 bước, {vn(FROM_SCRATCH_MINUTES, 1)} phút, {f.dbt_total} dbt test pass).",
    )
    architecture_figure(FIG_DIR / "architecture.png")
    d.picture(s, FIG_DIR / "architecture.png", MARGIN, Inches(1.45), w=Inches(12.1))
    d.card(s, MARGIN, Inches(5.75), Inches(5.4), Inches(0.95), INK)
    d.text(s, "python scripts/run_all.py", MARGIN + Inches(0.25), Inches(5.85), Inches(5.0), Inches(0.75), 20,
           WHITE, bold=True, font="Courier New", anchor=MSO_ANCHOR.MIDDLE)
    d.text(s, f"14/14 bước · {vn(FROM_SCRATCH_MINUTES, 1)} phút từ trạng thái trống · {f.dbt_pass}/{f.dbt_total} "
              "dbt test pass · idempotent", Inches(6.1), Inches(5.85), Inches(6.6), Inches(0.75), 17, INK,
           anchor=MSO_ANCHOR.MIDDLE)

    # 6 — star schema --------------------------------------------------------
    s = d.content(
        "Lược đồ hình sao: độ mịn trạm × giờ, 4 chiều", "3 · Kho dữ liệu & OLAP",
        "≈1'. Độ mịn = 1 trạm × 1 giờ vì: là độ mịn gốc; cuộn lên được mọi mức còn ngược lại thì không; bài toán "
        "giờ tới cần mức giờ. Chiều Hướng gió trả lời câu hỏi 'vì sao'. 4 phân cấp nên số khối con là 180.",
    )
    d.picture(s, ART / "dwh" / "figures" / "star_schema.png", MARGIN, Inches(1.4), h=Inches(5.3))
    d.bullets(s, [
        [("b", "Độ mịn trạm × giờ: "), ("", "độ mịn gốc, cuộn lên được mọi mức")],
        [("b", "4 phân cấp: "), ("", "ngày→tháng→quý→năm · giờ→buổi · trạm→quận · hướng→phần tư→bắc/nam")],
        [("b", "Số khối con: "), ("", "T = 5·3·3·4 = 180")],
    ], Inches(9.35), Inches(1.6), Inches(3.4), Inches(5.0), 15, gap=14)

    # 7 — cuboids + verification ---------------------------------------------
    s = d.content(
        "Ba khối tính trước, kiểm chứng 100% ô", "3 · Kho dữ liệu & OLAP",
        "≈1'. Chọn khối theo truy vấn thật của dashboard: (trạm, ngày), (trạm, tháng) và CUBE 5 thuộc tính = 32 khối "
        "con. Mỗi ô được tính lại từ fact và so khớp: 24 759/24 759 ô đúng. Trung bình là độ đo đại số nên khối lưu "
        "tổng và số đếm.",
    )
    rows = [("mart_station_daily", "(trạm, ngày)", "17 532", "dashboard xu hướng; nhỏ hơn fact 24 lần"),
            ("mart_station_monthly", "(trạm, tháng)", "576", "báo cáo tháng/mùa; nhỏ hơn fact 730 lần"),
            ("mart_olap_cube", "CUBE(năm, mùa, quận, buổi, hướng gió)", "6 075 · 32 khối", "trang OLAP đọc trong vài ms")]
    tbl = s.shapes.add_table(4, 4, MARGIN, Inches(1.55), Inches(8.2), Inches(3.2)).table
    for c, wdt in enumerate((2.3, 2.7, 1.4, 1.8)):
        tbl.columns[c].width = Inches(wdt)
    for r_i, vals in enumerate([("Khối", "Khối con", "Số ô", "Vì sao chọn"), *rows]):
        for c_i, v in enumerate(vals):
            cell = tbl.cell(r_i, c_i)
            cell.text = v
            para = cell.text_frame.paragraphs[0]
            para.runs[0].font.size = Pt(14 if r_i == 0 else 13)
            para.runs[0].font.name = BODY
            para.runs[0].font.bold = r_i == 0
            para.runs[0].font.color.rgb = WHITE if r_i == 0 else INK
            cell.fill.solid()
            cell.fill.fore_color.rgb = INK if r_i == 0 else (CARD if r_i % 2 else WHITE)
    s_ = f.olap["summary"]
    d.stat(s, vn(s_["pct_cells_correct"], 0) + "%", f"{vn_int(s_['cells_matched'])}/{vn_int(s_['cells_checked'])} ô "
           f"của {s_['cuboids_checked']} khối khớp khi tính lại từ fact", Inches(9.1), Inches(1.55), Inches(3.63),
           color=TEAL, fill=SOFT_TEAL, h=Inches(1.9), value_size=48)
    d.stat(s, f"{f.dbt_pass}/{f.dbt_total}", "dbt test pass: khoá, độ mịn, khoá ngoại, cube phân hoạch fact",
           Inches(9.1), Inches(3.65), Inches(3.63), color=INK, h=Inches(1.6))
    d.text(s, "Truy vấn được viết lại theo khối: nếu mọi thuộc tính truy vấn nằm trong cube → đọc mart_olap_cube "
              "(2–6 ms), nếu không → quét fact (130–400 ms).", MARGIN, Inches(5.1), Inches(8.2), Inches(1.2), 16,
           MUTED, italic=True)

    # 8 — OLAP demo screenshot -------------------------------------------------
    s = d.content(
        "OLAP trực tiếp: roll-up, drill-down, slice, dice, pivot", "3 · Kho dữ liệu & OLAP",
        "≈1'30\". DEMO TRỰC TIẾP trang /olap. Gợi ý kịch bản: Năm × Mùa (đọc từ cube) → bấm 2015 để drill-down sang "
        "quý → Roll-up về năm → lọc quận Dongcheng (slice) → thêm Xicheng + năm 2016 (dice) → bấm Pivot. Nếu "
        "mạng/Docker lỗi, mở notebooks/olap/olap_demo.ipynb (đã chạy sẵn output).",
    )
    d.picture(s, SHOTS / "olap_dice_tram_x_thang.png", MARGIN, Inches(2.2), w=Inches(7.6))
    ops = [("1", "Roll-up", "tháng → quý → năm, trạm → quận"), ("2", "Drill-down", "bấm tên hàng/cột để khoan xuống"),
           ("3", "Slice", "một giá trị: quận = Dongcheng"), ("4", "Dice", "nhiều chiều: quận × năm × mùa"),
           ("5", "Pivot", "đổi hàng ↔ cột")]
    for i, (num, name, desc) in enumerate(ops):
        y = Inches(1.5) + i * Inches(1.05)
        d.badge(s, num, Inches(8.45), y)
        d.text(s, name, Inches(9.1), y - Inches(0.05), Inches(3.6), Inches(0.4), 18, INK, bold=True)
        d.text(s, desc, Inches(9.1), y + Inches(0.35), Inches(3.6), Inches(0.5), 14, MUTED)

    # 9 — OLAP insight (native chart) ----------------------------------------
    s = d.content(
        "Dice cho thấy gió nam làm PM2.5 mùa đông tăng ~60%", "3 · Kho dữ liệu & OLAP",
        "≈30\". Kết quả dice thật: cùng quận lõi đô thị, cùng mùa đông, gió nam (khí từ Hà Bắc) đẩy PM2.5 từ ~85 lên "
        "~133 µg/m³. Đây là căn cứ để khuyến nghị cảnh báo kỹ hơn khi có gió nam.",
    )
    south = {(x["district"], x["season"]): x["pm25_avg"] for x in f.op("dice_winter_south_core")["preview"]}
    north = {(x["district"], x["season"]): x["pm25_avg"] for x in f.op("dice_compare_north")["preview"]}
    keys = sorted(south, key=lambda k: (k[0], k[1] != "autumn"))
    cd = CategoryChartData()
    cd.categories = [f"{k[0]} · {'Thu' if k[1] == 'autumn' else 'Đông'}" for k in keys]
    cd.add_series("Gió bắc", [round(north[k], 1) for k in keys])
    cd.add_series("Gió nam", [round(south[k], 1) for k in keys])
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, MARGIN, Inches(1.45), Inches(8.0), Inches(5.3), cd)
    ch = gf.chart
    d.style_chart(ch, [TEAL, ORANGE])
    pl = ch.plots[0]
    pl.has_data_labels = True
    pl.data_labels.number_format = "0"
    pl.data_labels.number_format_is_linked = False
    pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    pl.data_labels.font.size = Pt(12)
    pl.gap_width = 80
    ch.value_axis.has_title = True
    ch.value_axis.axis_title.text_frame.text = "PM2.5 trung bình (µg/m³)"
    ch.value_axis.axis_title.text_frame.paragraphs[0].runs[0].font.size = Pt(12)
    dc = ("Dongcheng", "winter")
    d.stat(s, f"{vn(north[dc], 0)} → {vn(south[dc], 0)}", "µg/m³ — Dongcheng mùa đông, gió bắc → gió nam",
           Inches(8.9), Inches(1.55), Inches(3.83), value_size=34)
    d.bullets(s, ["Tỷ lệ giờ vượt ngưỡng: ~28% → ~43%", "Hướng gió là chiều \"vì sao\" của kho",
                  "→ ưu tiên cảnh báo khi dự báo có gió nam"], Inches(8.9), Inches(3.4), Inches(3.83), Inches(3.0), 16)

    # 10 — mining setup ---------------------------------------------------------
    s = d.content(
        "Phân loại: nhãn, đặc trưng, chia tập theo thời gian", "4 · Khai phá",
        "≈1'. Chọn phân loại vì quyết định là có/không và hai loại sai có giá khác nhau. 49 đặc trưng, chỉ dùng thông "
        "tin biết tại t. Chia tập theo thời gian và khoá từ đầu. Chọn độ sâu cây và ngưỡng xác suất trên val; test "
        "chỉ dùng một lần.",
    )
    segs = [("train", "03/2013 – 12/2015", f.cls["rows"]["train"], f.cls["class_balance"]["train"], TEAL, 7.2),
            ("val", "01–06/2016", f.cls["rows"]["val"], f.cls["class_balance"]["val"], MUTED, 2.4),
            ("test", "07–12/2016", f.cls["rows"]["test"], f.cls["class_balance"]["test"], ORANGE, 2.5)]
    x = MARGIN
    for name, period, n, bal, color, wdt in segs:
        shp = d.card(s, x, Inches(1.55), Inches(wdt) - Inches(0.08), Inches(1.15), color)
        shp.adjustments[0] = 0.12
        d.text(s, f"{name}  ·  {period}", x + Inches(0.15), Inches(1.6), Inches(wdt) - Inches(0.3), Inches(0.45), 16,
               WHITE, bold=True)
        d.text(s, f"{vn_int(n)} mẫu · {pct(bal, 0)} nhãn 1", x + Inches(0.15), Inches(2.1), Inches(wdt) - Inches(0.3),
               Inches(0.45), 14, WHITE)
        x += Inches(wdt)
    d.card(s, MARGIN, Inches(3.0), Inches(5.9), Inches(2.9))
    d.text(s, "Nhãn & đặc trưng", MARGIN + Inches(0.3), Inches(3.15), Inches(5.3), Inches(0.5), 19, TEAL, bold=True)
    d.bullets(s, [[("b", "y = 1 "), ("", "nếu PM2.5(t+1) ≥ 115 µg/m³")],
                  "PM2.5 hiện tại, độ trễ 1–24 giờ, xu hướng",
                  "PM10, CO, NO2 · nhiệt độ, độ ẩm, gió",
                  "giờ, tháng, mùa, trạm, cụm trạm"], MARGIN + Inches(0.3), Inches(3.7), Inches(5.4), Inches(2.8), 16)
    d.card(s, Inches(6.83), Inches(3.0), Inches(5.9), Inches(2.9))
    d.text(s, "Mô hình", Inches(7.13), Inches(3.15), Inches(5.3), Inches(0.5), 19, TEAL, bold=True)
    d.bullets(s, [[("b", "Cơ sở: "), ("", "majority · persistence (cách hiện tại)")],
                  [("b", "Cây quyết định "), ("", f"entropy, độ sâu {f.tree_depth} (chọn trên val)")],
                  [("b", "HistGradientBoosting "), ("", f"ngưỡng {vn(f.cls['probability_cutoff'], 2)}")],
                  "Khoá mô hình có F1 trên val cao nhất"], Inches(7.13), Inches(3.7), Inches(5.4), Inches(2.8), 16)

    # 11 — results ------------------------------------------------------------
    s = d.content(
        "Mô hình bỏ sót ít hơn và báo nhầm ít hơn cách hiện tại", "4 · Khai phá",
        f"≈1'30\". Đọc ma trận nhầm lẫn: FN {vn_int(per['fn'])} → {vn_int(loc['fn'])}, FP {vn_int(per['fp'])} → "
        f"{vn_int(loc['fp'])}. Majority đạt accuracy {vn(f.test('majority')['accuracy'], 2)} nhưng recall = 0, nên "
        "không thể chỉ báo cáo accuracy.",
    )
    d.picture(s, ART / "classification" / "figures" / "confusion_matrices_test.png", MARGIN, Inches(1.5),
              w=Inches(12.1))
    for i, (v, lab, color) in enumerate((
            (vn(loc["f1"], 3), f"F1 của HistGB (persistence {vn(per['f1'], 3)})", ORANGE),
            (f"{vn_int(per['fn'])} → {vn_int(loc['fn'])}", "giờ ô nhiễm bị bỏ sót (FN)", INK),
            (f"{vn_int(per['fp'])} → {vn_int(loc['fp'])}", "cảnh báo nhầm (FP)", INK),
            (vn(f.test("majority")["accuracy"], 2), "accuracy của majority — dù recall = 0", MUTED))):
        d.stat(s, v, lab, MARGIN + i * Inches(3.08), Inches(4.75), Inches(2.85), color=color, h=Inches(1.75),
               value_size=24)

    # 12 — evidence (native chart) --------------------------------------------
    s = d.content(
        "Báo trước được 30% số lần ô nhiễm bắt đầu", "4 · Khai phá",
        f"≈1'. Lúc bắt đầu đợt ô nhiễm là thời điểm cần cảnh báo nhất: HistGB báo trước được "
        f"{vn_int(f.onset['locked']['detected'])}/{vn_int(f.onset['locked']['onsets'])} lần, persistence 0. "
        f"McNemar p = {f.mcnemar['p_value']:.0e}. Cảnh báo càng sớm thì lợi thế càng lớn (F1 +0,043 ở tầm 6 giờ), "
        "đổi lại precision giảm nhẹ.",
    )
    d.stat(s, f"{vn_int(f.onset['locked']['detected'])} / {vn_int(f.onset['locked']['onsets'])}",
           "lần ô nhiễm bắt đầu được báo trước (persistence: 0)", MARGIN, Inches(1.55), Inches(4.2), h=Inches(1.6))
    d.stat(s, sci(f.mcnemar["p_value"]),
           f"McNemar: {vn_int(f.mcnemar['b'])} giờ chỉ mô hình đúng, {vn_int(f.mcnemar['c'])} giờ chỉ persistence đúng",
           MARGIN, Inches(3.35), Inches(4.2), color=INK, h=Inches(1.6), value_size=32)
    better = sum(
        float(g[g.model == "locked"]["f1"].iloc[0]) > float(g[g.model == "persistence"]["f1"].iloc[0])
        for _, g in f.by_station.groupby("station_key")
    )
    d.stat(s, f"{better}/12", "trạm có F1 cao hơn persistence", MARGIN, Inches(5.15), Inches(4.2), color=TEAL,
           h=Inches(1.5))
    cd = CategoryChartData()
    cd.categories = ["1 giờ", "3 giờ", "6 giờ"]
    cd.add_series("Persistence", [round(f.horizon_f1(h, "persistence"), 3) for h in (1, 3, 6)])
    cd.add_series("HistGradientBoosting", [round(f.horizon_f1(h, "hist_gradient_boosting"), 3) for h in (1, 3, 6)])
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(5.2), Inches(1.45), Inches(7.53), Inches(5.3), cd)
    ch = gf.chart
    d.style_chart(ch, [MUTED, ORANGE])
    ch.has_title = True
    ch.chart_title.text_frame.text = "F1 trên test theo tầm cảnh báo"
    ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(14)
    ch.value_axis.minimum_scale = 0.6
    ch.value_axis.maximum_scale = 1.0
    pl = ch.plots[0]
    pl.has_data_labels = True
    pl.data_labels.number_format = "0.000"
    pl.data_labels.number_format_is_linked = False
    pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    pl.data_labels.font.size = Pt(12)
    pl.gap_width = 70

    # 13 — application ----------------------------------------------------------
    s = d.content(
        "Ứng dụng: trang Cảnh báo cho người vận hành", "4 · Khai phá",
        "≈30\". DEMO trang /canh-bao: hai ma trận nhầm lẫn cạnh nhau, dòng thời gian PM2.5 thực đo tại một trạm kèm "
        f"những giờ mô hình đã cảnh báo từ {h} giờ trước (xanh = cảnh báo đúng, vàng = báo nhầm, đỏ = bỏ sót), bảng "
        "so sánh theo trạm.",
    )
    d.picture(s, SHOTS / "canh_bao.png", MARGIN, Inches(1.4), h=Inches(5.4))
    d.bullets(s, ["Ma trận nhầm lẫn: mô hình so với cách hiện tại", "Dòng thời gian PM2.5 và cảnh báo theo trạm",
                  "Đọc từ mart_pm25_alerts (dbt)", "Cùng app: /olap, /du-bao, /ban-do"], Inches(7.25), Inches(1.6),
              Inches(5.5), Inches(5.0), 17, gap=14)

    # 14 — actions & limits -----------------------------------------------------
    s = d.content(
        "Khuyến nghị hành động và hạn chế", "5 · Kết luận",
        "≈1'30\". Ba khuyến nghị gắn trực tiếp với kết quả. Hạn chế nêu thật: test chỉ 6 tháng; tầm 1 giờ ngắn; mức "
        "cải thiện khiêm tốn (+0,013 F1) dù có ý nghĩa thống kê; ngưỡng 115 vốn là ngưỡng 24 giờ.",
    )
    d.card(s, MARGIN, Inches(1.55), Inches(6.0), Inches(3.6), SOFT_TEAL)
    d.text(s, "Nên làm", MARGIN + Inches(0.3), Inches(1.7), Inches(5.4), Inches(0.5), 20, TEAL, bold=True)
    d.bullets(s, [
        "Cảnh báo theo xác suất của mô hình, không chờ số đo vượt ngưỡng",
        "Ưu tiên mùa đông, buổi tối/đêm, khi có gió nam",
        "Cần báo sớm 3–6 giờ: chấp nhận thêm báo nhầm để đổi lấy recall cao",
    ], MARGIN + Inches(0.3), Inches(2.3), Inches(5.4), Inches(4.1), 17, gap=14)
    d.card(s, Inches(6.73), Inches(1.55), Inches(6.0), Inches(3.6))
    d.text(s, "Hạn chế", Inches(7.03), Inches(1.7), Inches(5.4), Inches(0.5), 20, ORANGE, bold=True)
    d.bullets(s, [
        "Test chỉ 6 tháng cuối 2016, dữ liệu lịch sử",
        "Tầm 1 giờ còn ngắn cho quyết định lớn",
        "Lợi thế so với persistence khiêm tốn (+0,013 F1 ở 1 giờ)",
        "Ngưỡng 115 là ngưỡng 24 giờ, áp cho từng giờ",
    ], Inches(7.03), Inches(2.3), Inches(5.4), Inches(4.1), 17, gap=14)
    for i, (v, lab, color) in enumerate((
            (f"{vn(loc['f1'], 3)} vs {vn(per['f1'], 3)}", "F1 mô hình so với cách hiện tại (test)", ORANGE),
            (pct(f.onset["locked"]["recall"], 0), "số lần ô nhiễm bắt đầu được báo trước", ORANGE),
            ("100%", "ô khối tính trước kiểm chứng đúng", TEAL))):
        d.stat(s, v, lab, MARGIN + i * Inches(4.08), Inches(5.4), Inches(3.85), color=color, h=Inches(1.35),
               value_size=30)

    # 15 — close ------------------------------------------------------------------
    s = d.dark(
        "Kết thúc (15 giây) rồi mời hỏi đáp. Mỗi thành viên sẵn sàng trả lời phần mình phụ trách (xem bảng phân công)."
    )
    d.text(s, "Cảm ơn thầy/cô và các bạn", MARGIN, Inches(1.6), Inches(11.5), Inches(1.0), 42, WHITE, bold=True,
           font=HEAD)
    d.text(s, "Hỏi đáp", MARGIN, Inches(2.6), Inches(11.5), Inches(0.8), 28, RGBColor(0xFD, 0xBA, 0x74), font=HEAD)
    d.text(s, ["Mã nguồn + hướng dẫn chạy: README.md  ·  python scripts/run_all.py",
               "Báo cáo: bao_cao/BaoCao_BTL_INT1422.docx  ·  Phân công & khai báo AI: bao_cao/"],
           MARGIN, Inches(4.6), Inches(11.5), Inches(1.0), 16, RGBColor(0xCB, 0xD5, 0xE1))
    d.text(s, "[Thành viên 1 — phần …]   [Thành viên 2 — phần …]   [Thành viên 3 — phần …]", MARGIN, Inches(6.0),
           Inches(11.5), Inches(0.5), 15, WHITE)
    return d.prs


def main() -> int:
    prs = build(Facts())
    assert len(prs.slides) <= 15, "Bài 12: tối đa 15 slide"
    prs.save(str(OUT))
    print(OUT.relative_to(ROOT), len(prs.slides), "slides")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
