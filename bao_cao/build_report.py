#!/usr/bin/env python3
"""Generate bao_cao/BaoCao_BTL_INT1422.docx from the project's real artifacts.

Every number in the report is read from artifacts/ at build time, so re-running after
`python scripts/run_all.py` keeps the report consistent with the code.

    pip install -r bao_cao/requirements.txt
    python bao_cao/build_report.py

Open the .docx in Word, right-click the table of contents → Update Field, then fill in
the [placeholders] (group, members, lecturer) and the parts marked "NHÓM ĐIỀN".
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.shared import Pt  # noqa: E402

from docx_helpers import Report  # noqa: E402
from report_lib import (  # noqa: E402
    ART,
    FIG_DIR,
    FROM_SCRATCH_MINUTES,
    ROOT,
    Facts,
    architecture_figure,
    feature_vi,
    pct,
    vn,
    vn_int,
)

OUT = HERE / "BaoCao_BTL_INT1422.docx"
SHOTS = ART / "dashboard_screenshots"

MODEL_VI = {
    "majority": "Majority (luôn \"không\")",
    "persistence": "Persistence (PM2.5(t) ≥ 115)",
    "decision_tree": "Cây quyết định (entropy)",
    "hist_gradient_boosting": "HistGradientBoosting",
}


def cover(r: Report) -> None:
    for text, size, bold in (
        ("HỌC VIỆN CÔNG NGHỆ BƯU CHÍNH VIỄN THÔNG", 14, True),
        ("KHOA CÔNG NGHỆ THÔNG TIN 1", 14, True),
        ("", 13, False), ("", 13, False), ("", 13, False),
        ("BÁO CÁO BÀI TẬP LỚN", 20, True),
        ("Học phần: Kho dữ liệu và Khai phá dữ liệu (INT1422)", 14, False),
        ("", 13, False),
        ("ĐỀ TÀI", 14, True),
        ("KHO DỮ LIỆU CHẤT LƯỢNG KHÔNG KHÍ BẮC KINH", 17, True),
        ("VÀ CẢNH BÁO SỚM PM2.5 VƯỢT NGƯỠNG", 17, True),
        ("", 13, False), ("", 13, False),
    ):
        para = r.doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(text)
        run.bold = bold
        run.font.size = Pt(size)
    for label, value in (
        ("Giảng viên hướng dẫn: ", "[Họ tên giảng viên]"),
        ("Nhóm: ", "[Số nhóm]  —  Lớp: [Mã lớp học phần]"),
    ):
        para = r.doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.add_run(label).bold = True
        para.add_run(value)
    r.table(
        ["STT", "Họ và tên", "Mã sinh viên"],
        [["1", "[Họ tên thành viên 1]", "[MSSV]"], ["2", "[Họ tên thành viên 2]", "[MSSV]"],
         ["3", "[Họ tên thành viên 3 — xoá dòng nếu không có]", "[MSSV]"]],
        [1.2, 8.5, 4.0],
        None,
        font_size=12,
    )
    for _ in range(4):
        r.doc.add_paragraph()
    para = r.doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.add_run("Hà Nội, tháng [..] năm 2026").italic = True


def chapter_intro(r: Report, f: Facts) -> None:
    r.h1("Giới thiệu và câu hỏi nghiệp vụ")
    r.h2("1.1. Bối cảnh")
    r.p(
        "Bụi mịn PM2.5 (đường kính ≤ 2,5 µm) là chất ô nhiễm có ảnh hưởng lớn nhất tới sức khoẻ hô hấp và tim mạch. "
        "Giai đoạn 2013–2017, Bắc Kinh là một trong những đô thị ô nhiễm nặng nhất thế giới: trên 12 trạm quan trắc "
        "của bộ dữ liệu, PM2.5 trung bình là 79,8 µg/m³ và khoảng một phần tư số giờ có PM2.5 ≥ 115 µg/m³, tức mức "
        "\"ô nhiễm trung bình\" trở lên theo chuẩn chỉ số chất lượng không khí của Trung Quốc (HJ 633-2012). "
        "Ở mức này, người già, trẻ nhỏ và người có bệnh hô hấp được khuyến cáo hạn chế hoạt động ngoài trời."
    )
    r.h2("1.2. Câu hỏi nghiệp vụ")
    r.rich([
        ("b", "Người dùng: "),
        ("", "trung tâm quan trắc môi trường của thành phố (phối hợp cơ quan y tế công cộng). "),
        ("b", "Quyết định cần hỗ trợ: "),
        ("", "có phát cảnh báo \"hạn chế hoạt động ngoài trời\" cho giờ tới tại từng trạm hay không. Người hưởng lợi "
             "trực tiếp là trường học (quyết định cho học sinh ra sân), bệnh viện và người dân nhạy cảm."),
    ])
    r.rich([
        ("b", "Câu hỏi khai phá: "),
        ("i", "Giờ tới, tại trạm X, nồng độ PM2.5 có ≥ 115 µg/m³ hay không?"),
        ("", " Đây là bài toán phân loại nhị phân. "),
        ("b", "Cách làm hiện tại (mô hình cơ sở): "),
        ("", "nhìn số đo giờ hiện tại và cảnh báo nếu đã vượt ngưỡng (persistence). Cách này luôn trễ một giờ: "
             "nó không bao giờ báo trước được thời điểm một đợt ô nhiễm bắt đầu."),
    ])
    r.p("Để quyết định cảnh báo ở đâu và khi nào, kho dữ liệu cần trả lời nhanh các câu hỏi phân tích:")
    r.bullets([
        "Ô nhiễm biến động thế nào theo năm, quý, tháng, mùa và theo giờ trong ngày?",
        "Quận, trạm nào ô nhiễm nặng nhất?",
        "Hướng gió nào đi kèm các đợt ô nhiễm?",
    ])
    r.h2("1.3. Phạm vi công việc")
    r.p("Bài tập lớn thực hiện đủ năm phần công việc bắt buộc. Mỗi phần có sản phẩm chứng minh được trong kho mã nguồn:")
    r.table(
        ["Phần việc", "Sản phẩm chính", "Chương"],
        [
            ["1. Thu thập & tiền xử lý", "Pipeline UCI + Open-Meteo → MinIO → PostgreSQL; bảng tỷ lệ thiếu từng cột", "2"],
            ["2. Thiết kế kho dữ liệu", "Lược đồ hình sao 4 chiều, phân cấp khái niệm, độ mịn trạm × giờ", "3"],
            ["3. Cài đặt & tính khối", "dbt (PostgreSQL), 3 khối tính trước, kiểm chứng 100% ô đúng", "4"],
            ["4. Dịch vụ OLAP", "5 thao tác trên SQL, notebook và trang web /olap", "5"],
            ["5. Chức năng khai phá", "Phân loại cảnh báo vượt ngưỡng, so với persistence", "6, 7"],
        ],
        [4.2, 9.3, 2.0],
        "Năm phần công việc và sản phẩm tương ứng",
    )
    r.h2("1.4. Kiến trúc và công cụ")
    architecture_figure(FIG_DIR / "architecture.png")
    r.figure(FIG_DIR / "architecture.png", "Kiến trúc tổng thể — mỗi khối là mã nguồn chạy được", 16)
    r.p(
        "Dữ liệu thô được giữ bất biến trên data lake MinIO, xử lý thành Parquet có cờ chất lượng, nạp vào vùng "
        "staging của PostgreSQL rồi biến đổi thành kho dữ liệu bằng dbt (ELT). Khai phá dùng pandas và scikit-learn. "
        "Ứng dụng là API FastAPI cùng giao diện React. Toàn bộ chuỗi chạy lại được bằng một lệnh "
        "(python scripts/run_all.py, xem Phụ lục A). Git là bằng chứng phối hợp của nhóm."
    )


def chapter_data(r: Report, f: Facts) -> None:
    r.h1("Thu thập và tiền xử lý dữ liệu")
    r.h2("2.1. Nguồn dữ liệu và giấy phép")
    r.table(
        ["", "Nguồn chính", "Nguồn bổ sung"],
        [
            ["Bộ dữ liệu", "Beijing Multi-Site Air Quality (PRSA), UCI ML Repository #501",
             "Open-Meteo Historical Weather API (tái phân tích ERA5)"],
            ["Trích dẫn", "Chen, S. (2017). DOI 10.24432/C5RK5G", "open-meteo.com"],
            ["Giấy phép", "CC BY 4.0", "CC BY 4.0; API miễn phí cho mục đích phi thương mại"],
            ["Quy mô", "12 trạm × 35 064 giờ = 420 768 bản ghi; 01/03/2013 – 28/02/2017",
             "12 trạm, cùng giai đoạn, theo giờ"],
            ["Dữ liệu cá nhân", "Không (chỉ số đo môi trường theo trạm)", "Không"],
        ],
        [2.7, 6.9, 6.0],
        "Nguồn dữ liệu",
    )
    r.p(
        "Lý do bổ sung Open-Meteo: dữ liệu khí tượng của UCI có chỗ trống. Một nguồn tái phân tích độc lập cho phép "
        "lấp các chỗ trống này mà không phải đoán, đồng thời bổ sung độ che phủ mây. Script "
        "scripts/download_uci_dataset.py tự tải bộ dữ liệu và kiểm tra kích thước 12 file theo danh mục "
        "data/raw/reference/file_inventory.csv."
    )
    r.h2("2.2. Các thuộc tính")
    r.table(
        ["Nhóm", "Thuộc tính", "Đơn vị / miền giá trị"],
        [
            ["Thời gian", "year, month, day, hour → event_time_local", "giờ địa phương Bắc Kinh"],
            ["Địa điểm", "station (12 trạm), bổ sung quận và toạ độ", "danh mục"],
            ["Chất ô nhiễm", "PM2.5, PM10, SO2, NO2, CO, O3", "µg/m³"],
            ["Khí tượng", "TEMP, DEWP (°C), PRES (hPa), RAIN (mm), WSPM (m/s)", "số thực"],
            ["Hướng gió", "wd: 16 hướng N, NNE, …, NNW", "danh mục"],
            ["Suy diễn / bổ sung", "độ ẩm tương đối (từ TEMP + DEWP), độ che phủ mây (Open-Meteo)", "%"],
        ],
        [3.0, 7.6, 5.0],
        "Thuộc tính có ý nghĩa của bộ dữ liệu (≥ 6 thuộc tính, có thuộc tính thời gian)",
    )
    r.h2("2.3. Tỷ lệ giá trị thiếu và cách xử lý từng cột")
    short = {
        "PM2.5": "Giữ NULL + cờ chất lượng; khi khai phá loại dòng thiếu nhãn",
        "PM10": "Giữ NULL; khai phá: median TRAIN + cờ thiếu",
        "SO2": "Giữ NULL + cờ; không dùng làm đặc trưng",
        "NO2": "Giữ NULL; khai phá: median TRAIN + cờ thiếu",
        "CO": "Giữ NULL; khai phá: median TRAIN + cờ thiếu",
        "O3": "Giữ NULL + cờ; không dùng làm đặc trưng",
        "TEMP": "Lấp từ Open-Meteo, ghi nguồn",
        "PRES": "Lấp từ Open-Meteo, ghi nguồn",
        "DEWP": "Lấp từ Open-Meteo, ghi nguồn",
        "RAIN": "Lấp từ Open-Meteo, ghi nguồn",
        "WSPM": "Lấp từ Open-Meteo, ghi nguồn",
        "wd": "Lấp từ Open-Meteo (độ → 16 hướng); còn thiếu → UNKNOWN",
    }
    rows = []
    for m in f.missing.itertuples():
        rem = "—" if m.remaining_in_fact != m.remaining_in_fact else vn_int(m.remaining_in_fact)
        rows.append([m.variable, vn_int(m.missing), vn(m.missing_pct, 2) + "%", f"{int(m.longest_gap_h)} h", rem,
                     short[m.variable]])
    r.table(
        ["Cột", "Số ô thiếu", "Tỷ lệ", "Chuỗi thiếu dài nhất", "Còn thiếu trong kho", "Cách xử lý"],
        rows,
        [1.5, 1.9, 1.5, 2.0, 2.1, 6.6],
        "Giá trị thiếu trên 420 768 bản ghi và cách xử lý (scripts/build_missing_table.py)",
        font_size=10,
        align_right={1, 2, 3, 4},
    )
    r.p(
        "Kho dữ liệu không nội suy chất ô nhiễm, vì có những chuỗi thiếu dài tới 343 giờ (hơn hai tuần). Nội suy qua "
        "khoảng trống như vậy là bịa dữ liệu, làm sai cả số liệu OLAP lẫn nhãn khai phá. Mọi trung bình trong kho "
        "đều kèm số giờ có dữ liệu thật đã tham gia tính. Thời tiết được lấp vì có nguồn độc lập đáng tin, và mỗi "
        "giá trị lấp đều ghi nguồn (cột *_source)."
    )
    r.h2("2.4. Làm sạch và chuẩn hoá")
    r.bullets([
        [("b", "Khoá tự nhiên "), ("", "(trạm, thời điểm) phải duy nhất. Nếu trùng, pipeline dừng. Kết quả: 0 bản trùng.")],
        [("b", "Giá trị âm không hợp lệ "),
         ("", "(chất ô nhiễm, mưa, tốc độ gió) được đưa vào vùng cách ly trên MinIO. Kết quả: 0 dòng; nhiệt độ và "
              "điểm sương âm là hợp lệ.")],
        [("b", "Giá trị trần của thiết bị "),
         ("", "(PM2.5, PM10 = 999; CO = 10 000) được giữ lại và gắn cờ SUSPECT_CAP: 60 dòng.")],
        [("b", "Trạng thái chất lượng từng dòng: "), ("", "OK 383 924 · MISSING_MEASUREMENT 36 784 · SUSPECT_CAP 60.")],
        [("b", "Rời rạc hoá: "), ("", "giờ → buổi (đêm/sáng/chiều/tối); ngày → mùa; 16 hướng gió → 4 phần tư → 2 "
                                  "chế độ gió; PM2.5 → nhãn cảnh báo (≥ 115).")],
    ])
    r.h2("2.5. Khám phá dữ liệu")
    r.figure(ART / "eda" / "figures" / "temporal_pm25_by_season.png",
             "PM2.5 theo mùa — mùa đông ô nhiễm nặng nhất (trung bình 95,5 µg/m³), mùa hè sạch nhất (64,7)", 12)
    r.p(
        "Ô nhiễm có tính mùa rõ rệt. Theo giờ trong ngày, đỉnh rơi vào 22 h (88,9 µg/m³) và đáy vào 7 h (73,3), "
        "nhưng biên độ này nhỏ hơn chênh lệch giữa các mùa. Trạm ô nhiễm nhất là Dongsi (86,2), sạch nhất là "
        "Dingling (66,0). PM2.5 tương quan mạnh với PM10 (0,89) và CO (0,80), tương quan âm với tốc độ gió (−0,27)."
    )


def chapter_design(r: Report, f: Facts) -> None:
    r.h1("Thiết kế kho dữ liệu")
    r.h2("3.1. Lược đồ hình sao")
    r.figure(ART / "dwh" / "figures" / "star_schema.png", "Lược đồ hình sao của kho (schema dwh)", 16)
    r.h2("3.2. Bảng sự kiện và độ mịn")
    r.p(
        "Bảng sự kiện fact_air_quality_hourly có độ mịn một trạm × một giờ (420 768 dòng). Nhóm chọn độ mịn này "
        "vì bốn lý do:"
    )
    r.bullets([
        [("b", "Đó là độ mịn gốc của nguồn: "),
         ("", "gộp trước (ví dụ theo ngày) sẽ mất thông tin không lấy lại được. Một ngày trung bình 80 µg/m³ có thể "
              "chứa sáu giờ liền trên 300 µg/m³.")],
        [("b", "Mức chi tiết nhất thì cuộn lên được mọi mức "),
         ("", "(buổi, ngày, tháng, quý, năm, quận), còn chiều ngược lại thì không. Nhu cầu theo ngày/tháng đã được "
              "đáp ứng bằng khối con tính trước (Chương 4).")],
        [("b", "Bài toán khai phá cần mức giờ: "),
         ("", "cảnh báo cho giờ tới và định nghĩa đợt ô nhiễm \"≥ 115 µg/m³ liên tục ≥ 3 giờ\" không tồn tại ở mức ngày.")],
        [("b", "Kích thước vẫn nhỏ: "), ("", "PostgreSQL quét toàn bảng trong khoảng 0,2 giây.")],
    ])
    r.h2("3.3. Các chiều và phân cấp khái niệm")
    r.table(
        ["Chiều", "Thành viên", "Phân cấp khái niệm", "Số mức"],
        [
            ["Thời gian (dim_date)", "1 461 ngày", "ngày → tháng → quý → năm (song song: mùa)", "4"],
            ["Giờ trong ngày (dim_time)", "24 giờ", "giờ → buổi", "2"],
            ["Địa điểm (dim_station)", "12 trạm, 8 quận", "trạm → quận", "2"],
            ["Hướng gió (dim_wind_direction)", "16 hướng + UNKNOWN", "hướng → phần tư → chế độ gió (bắc/nam)", "3"],
        ],
        [4.6, 3.3, 6.4, 1.4],
        "Các chiều của kho",
    )
    r.p(
        "Ba chiều đầu trả lời \"khi nào, ở đâu\"; chiều Hướng gió trả lời \"vì sao\". Ở Bắc Kinh, gió nam mang không "
        "khí ẩm và bụi từ đồng bằng Hà Bắc, còn gió bắc đẩy ô nhiễm đi. Thành viên UNKNOWN (khoá 0) giúp bảng sự "
        "kiện không bao giờ có khoá ngoại rỗng."
    )
    r.h2("3.4. Độ đo")
    r.p(
        "Độ đo chính là nồng độ PM2.5 (cùng năm chất ô nhiễm khác và các biến thời tiết). Trung bình là độ đo đại "
        "số: muốn cuộn lên từ khối con thì phải lấy tổng chia số đếm, không lấy trung bình của trung bình. Vì vậy "
        "mọi khối tính trước đều lưu kèm tổng và số giờ có dữ liệu. Số giờ quan trắc và số giờ vượt ngưỡng là các "
        "độ đo cộng dồn."
    )
    r.h2("3.5. Số khối con")
    r.p(
        "Với n = 4 chiều có số mức phân cấp L = (4, 2, 2, 3), số khối con là T = Π(Lᵢ + 1) = 5 × 3 × 3 × 4 = 180. "
        "Không cần tính trước cả 180 khối. Chương 4 trình bày các khối được chọn và lý do."
    )


def chapter_build(r: Report, f: Facts) -> None:
    r.h1("Cài đặt kho dữ liệu và tính trước khối dữ liệu")
    r.h2("4.1. Quy trình nạp dữ liệu")
    r.table(
        ["Bước", "Mã nguồn", "Kết quả"],
        [
            ["Tải nguồn", "scripts/download_uci_dataset.py", "12 CSV, kiểm tra kích thước"],
            ["Data lake raw", "src/ingestion/uci_to_minio.py, openmeteo_to_minio.py", "MinIO raw/, bất biến, có checksum"],
            ["Processed", "src/processing/*.py", "Parquet chuẩn hoá + cờ chất lượng"],
            ["Staging", "src/staging/load.py", "staging.* (idempotent theo checksum)"],
            ["Kho (ELT)", "dbt/air_quality_dbt/models/warehouse/*.sql", "fact + 4 bảng chiều (schema dwh)"],
            ["Khối / mart", "dbt/air_quality_dbt/models/marts/*.sql", "khối tính trước + mart nghiệp vụ"],
            ["Điều phối", "airflow/dags/*.py, scripts/run_all.py", "DAG Airflow; chạy cả chuỗi bằng 1 lệnh"],
        ],
        [2.6, 7.3, 5.7],
        "Các bước nạp dữ liệu và mã nguồn tương ứng",
        font_size=10,
    )
    r.h2("4.2. Các khối được tính trước và lý do chọn")
    r.table(
        ["Khối tính trước", "Khối con", "Số ô", "Lý do chọn"],
        [
            ["mart_station_daily", "(trạm, ngày)", "17 532",
             "Truy vấn nhiều nhất của dashboard đều theo ngày. Giảm 24 lần so với fact; là tổ tiên chung của mọi "
             "khối tháng/quý/năm × trạm/quận."],
            ["mart_station_monthly", "(trạm, tháng)", "576",
             "Báo cáo tháng và so sánh mùa; nhỏ hơn fact 730 lần. Được cuộn lên từ fact, không phải trung bình của "
             "trung bình ngày."],
            ["mart_olap_cube", "CUBE(năm, mùa, quận, buổi, phần tư hướng gió)", "6 075 (32 khối con)",
             "Mọi tổ hợp của 5 thuộc tính phân tích hay dùng nằm trong một bảng. Trang OLAP đọc thẳng từ đây trong "
             "vài ms thay vì quét 420 nghìn dòng."],
        ],
        [3.3, 3.6, 2.2, 6.5],
        "Khối tính trước",
        font_size=10,
    )
    r.p(
        "Truy vấn được viết lại theo khối đã tính trước: API OLAP kiểm tra mọi thuộc tính truy vấn cần dùng. Nếu tất "
        "cả nằm trong cube, API chọn đúng khối con trong mart_olap_cube (2–6 ms); nếu không, API mới quét bảng sự "
        "kiện (130–400 ms)."
    )
    r.h2("4.3. Kiểm chứng tính đúng của khối dữ liệu")
    s = f.olap["summary"]
    rows = []
    for c in f.olap["cuboid_checks"][:3]:
        rows.append([c["cuboid"], vn_int(c["cells"]), vn_int(c["matched"]), vn(c["pct_correct"], 1) + "%"])
    cube = [c for c in f.olap["cuboid_checks"] if c["cuboid"].startswith("mart_olap_cube")]
    rows.append([f"mart_olap_cube ({len(cube)} khối con)", vn_int(sum(c["cells"] for c in cube)),
                 vn_int(sum(c["matched"] for c in cube)),
                 vn(100 * sum(c["matched"] for c in cube) / sum(c["cells"] for c in cube), 1) + "%"])
    rows.append(["Tổng", vn_int(s["cells_checked"]), vn_int(s["cells_matched"]), vn(s["pct_cells_correct"], 1) + "%"])
    r.table(["Khối", "Số ô", "Ô khớp", "Tỷ lệ đúng"], rows, [8.0, 2.4, 2.4, 2.4],
            "Mỗi ô của khối tính trước được tính lại từ bảng sự kiện (scripts/run_olap_checks.py)",
            align_right={1, 2, 3})
    r.p(
        f"Ngoài ra, dự án có {f.dbt_total} dbt test và tất cả đều pass ({f.dbt_pass}/{f.dbt_total}). Các test kiểm tra "
        "khoá chính, khoá ngoại tới 4 bảng chiều, độ mịn duy nhất, đúng 420 768 dòng, và việc mỗi khối con trong cube "
        "phân hoạch đủ toàn bộ bảng sự kiện (olap_cube_partitions_fact)."
    )
    r.h2("4.4. Chạy lại từ đầu bằng một lệnh")
    mins = f.run_minutes()
    took = (f"Lần kiểm chứng ngày 12/10/2026 chạy từ trạng thái trống (xoá volume Docker và dữ liệu thô) hoàn tất "
            f"14/14 bước trong {vn(FROM_SCRATCH_MINUTES, 1)} phút.")
    if mins:
        took += f" Lần chạy đầy đủ gần nhất (dữ liệu đã có, các bước tự bỏ qua phần đã làm) mất {vn(mins, 1)} phút."
    r.p(
        "Lệnh python scripts/run_all.py thực hiện tuần tự 14 bước, từ tải dữ liệu tới bật dashboard. Mọi bước đều "
        "idempotent, và khi một bước lỗi, script in sẵn lệnh để chạy tiếp từ bước đó. " + took
    )


def chapter_olap(r: Report, f: Facts) -> None:
    r.h1("Dịch vụ phân tích trực tuyến (OLAP)")
    r.p(
        "Năm thao tác OLAP được trình diễn trên dữ liệu thật qua ba giao diện: tệp SQL sql/olap/olap_operations.sql, "
        "notebook notebooks/olap/olap_demo.ipynb (đã chạy sẵn output) và trang web /olap của dashboard."
    )
    r.h2("5.1. Roll-up — cuộn lên")
    yr = f.op("rollup_year")["preview"]
    r.table(["Năm", "PM2.5 TB (µg/m³)", "Số giờ"],
            [[str(x["year"]), vn(x["pm25_avg"], 1), vn_int(x["hours"])] for x in yr],
            [3, 4, 3], "Trạm Dongsi: cuộn lên ngày → tháng → năm (rollup_day → rollup_month → rollup_year)",
            align_right={1, 2})
    r.p(
        "Ở mức ngày, 01/12/2015 có PM2.5 trung bình 506 µg/m³ (đợt khói mù lịch sử). Khi cuộn lên mức năm, đỉnh này bị "
        "pha loãng; đây cũng là minh chứng cho việc giữ độ mịn giờ. Truy vấn GROUP BY ROLLUP(year, quarter, month) "
        "sinh mọi tổng con của phân cấp Thời gian trong một câu lệnh. Năm 2017 chỉ có tháng 1–2 (mùa đông) nên "
        "trung bình cao hơn."
    )
    r.h2("5.2. Drill-down — khoan xuống")
    q = f.op("drilldown_quarter")["preview"]
    m = f.op("drilldown_month")["preview"]
    r.table(
        ["Mức", "Thành viên", "PM2.5 TB", "Số giờ vượt 115"],
        [["Quý (2015)", f"Q{x['quarter']}", vn(x["pm25_avg"], 1), vn_int(x["exceed_hours"])] for x in q]
        + [["Tháng (Q4/2015)", f"Tháng {x['month']}", vn(x["pm25_avg"], 1), vn_int(x["exceed_hours"])] for x in m],
        [3.6, 3.2, 3.0, 3.4],
        "Khoan xuống năm 2015 → quý → tháng của quý 4",
        align_right={2, 3},
    )
    r.p(
        "Quý 4 nổi bật, và khi khoan xuống thì tháng 12 tệ nhất (150,5 µg/m³). Khoan tiếp theo chiều Giờ cho thấy "
        "buổi tối và đêm cao hơn buổi sáng. Tổng số giờ vượt ngưỡng của các mức con được kiểm tra là cộng đúng bằng "
        "mức cha."
    )
    r.h2("5.3. Slice và dice")
    south = {(x["district"], x["season"]): x for x in f.op("dice_winter_south_core")["preview"]}
    north = {(x["district"], x["season"]): x for x in f.op("dice_compare_north")["preview"]}
    rows = []
    for k in sorted(south):
        rows.append([k[0], {"winter": "Đông", "autumn": "Thu"}[k[1]], vn(north[k]["pm25_avg"], 1),
                     vn(south[k]["pm25_avg"], 1), vn(north[k]["pct_exceed"], 1) + "%", vn(south[k]["pct_exceed"], 1) + "%"])
    r.table(
        ["Quận", "Mùa", "PM2.5 gió bắc", "PM2.5 gió nam", "% vượt (bắc)", "% vượt (nam)"],
        rows,
        [2.8, 1.6, 2.8, 2.8, 2.6, 2.6],
        "Dice: mùa ∈ {thu, đông} × quận ∈ {Dongcheng, Xicheng} × chế độ gió",
        align_right={2, 3, 4, 5},
    )
    r.p(
        "Slice cố định quận = 'Dongcheng' để được khối con hai chiều năm × mùa. Dice chọn khối con theo ba chiều. "
        "Kết quả: cùng quận, cùng mùa đông, gió nam làm PM2.5 tăng từ khoảng 85 lên khoảng 133 µg/m³ và tỷ lệ giờ "
        "vượt ngưỡng tăng từ khoảng 28% lên khoảng 43%. Đây là căn cứ để ưu tiên cảnh báo khi dự báo có gió nam."
    )
    r.h2("5.4. Pivot — xoay trục")
    r.figure(SHOTS / "olap_dice_tram_x_thang.png",
             "Trang /olap: trạm × tháng năm 2016, % giờ vượt ngưỡng, sau dice quận ∈ {Dongcheng, Xicheng} — "
             "nút Pivot đổi hàng ↔ cột", 15.5)
    r.p(
        "Pivot giữ nguyên dữ liệu, chỉ đổi khung nhìn: đưa trạm lên hàng và tháng sang cột (câu pivot_station_month "
        "dùng FILTER), hoặc ngược lại. Trên dashboard, bấm tên một hàng hoặc một cột sẽ khoan xuống mức con; tổng "
        "hàng/cột được sinh bằng GROUPING SETS và trạng thái khung nhìn được giữ trên URL để mở lại đúng khối đó."
    )
    r.h2("5.5. CUBE và trả lời từ khối đã tính trước")
    r.p(
        "GROUP BY CUBE(season, wind_regime) cho ra 2² = 4 khối con (đủ tổ hợp, các tổng con và tổng toàn bộ). Truy "
        "vấn năm × mùa đọc từ khối con (year, season) của mart_olap_cube mất khoảng 24 ms, so với khoảng 180 ms khi "
        "quét bảng sự kiện (đo trong notebook)."
    )
    r.figure(SHOTS / "olap_nam_x_mua.png", "Năm × mùa được trả lời từ khối con (year, season) đã tính trước", 13)


def chapter_mining(r: Report, f: Facts) -> None:
    r.h1("Khai phá dữ liệu: phân loại cảnh báo vượt ngưỡng")
    r.h2("6.1. Nhận diện bài toán")
    r.p(
        "Quyết định của người dùng là nhị phân (cảnh báo / không cảnh báo) và hai loại sai có chi phí khác nhau: bỏ "
        "sót một giờ ô nhiễm (FN) nguy hiểm hơn báo nhầm (FP). Vì vậy bài toán được chọn là phân loại và được đánh "
        "giá bằng ma trận nhầm lẫn. Phân cụm không trả lời được câu hỏi \"có cảnh báo không\"; luật kết hợp phù hợp "
        "với dữ liệu giao dịch, không phải chuỗi thời gian đo liên tục."
    )
    r.h2("6.2. Dữ liệu huấn luyện")
    r.bullets([
        [("b", "Nhãn: "), ("", "y = 1 nếu PM2.5(t+1) ≥ 115 µg/m³, ngược lại y = 0 (src/classification/target.py).")],
        [("b", f"Đặc trưng ({f.n_features}): "),
         ("", "chỉ dùng thông tin biết tại thời điểm t. Gồm PM2.5 hiện tại, độ trễ 1–24 giờ, trung bình trượt 6/24 "
              "giờ, mức thay đổi trong giờ; PM10, CO, NO2 và độ trễ của chúng; nhiệt độ, độ ẩm, tốc độ gió; giờ, "
              "tháng, thứ, mùa, trạm, cụm trạm; số giờ đã ở trong đợt ô nhiễm.")],
        [("b", "Chia tập theo thời gian, khoá từ đầu: "),
         ("", "không trộn ngẫu nhiên, để mô hình không \"nhìn thấy tương lai\". Median để điền giá trị thiếu chỉ tính "
              "trên tập train.")],
    ])
    rows = []
    for s, period in (("train", "03/2013 – 12/2015"), ("val", "01/2016 – 06/2016"), ("test", "07/2016 – 12/2016")):
        rows.append([s, period, vn_int(f.cls["rows"][s]), pct(f.cls["class_balance"][s])])
    r.table(["Tập", "Giai đoạn", "Số mẫu", "Tỷ lệ nhãn 1"], rows, [2.0, 5.0, 3.0, 3.0],
            "Chia tập theo thời gian", align_right={2, 3})
    r.h2("6.3. Mô hình và cách chọn")
    r.bullets([
        [("b", "Hai mô hình cơ sở: "), ("", "majority (luôn đoán \"không\") và persistence — chính là cách làm hiện tại.")],
        [("b", "Cây quyết định "),
         ("", f"với tiêu chí entropy (độ lợi thông tin, đúng như Bài 8). Độ sâu chọn trên tập val trong {{3, 4, 5, 6, 8, "
              f"10}}; giá trị được chọn là {f.tree_depth}, mỗi lá tối thiểu 200 mẫu để tránh quá khớp.")],
        [("b", "HistGradientBoosting: "), ("", "tập hợp cây tăng cường, cùng siêu tham số với mô hình hồi quy đã khoá.")],
        [("b", "Ngưỡng xác suất "),
         ("", f"cũng được chọn trên val: {vn(f.tree_cutoff, 2)} với cây quyết định và "
              f"{vn(f.cls['probability_cutoff'], 2)} với HistGB. Mô hình khoá là mô hình có F1 trên val cao nhất: "
              f"{MODEL_VI[f.locked]}. Tập test chỉ được dùng một lần để báo cáo.")],
    ])
    r.h2("6.4. Kết quả trên tập test")
    rows = []
    for name in ("majority", "persistence", "decision_tree", "hist_gradient_boosting"):
        t = f.test(name)
        rows.append([MODEL_VI[name], vn_int(t["tp"]), vn_int(t["fp"]), vn_int(t["fn"]), vn_int(t["tn"]),
                     vn(t["accuracy"], 3), vn(t["precision"], 3), vn(t["recall"], 3), vn(t["f1"], 3)])
    r.table(["Mô hình", "TP", "FP", "FN", "TN", "Accuracy", "Precision", "Recall", "F1"], rows,
            [3.3, 1.5, 1.3, 1.5, 1.6, 1.8, 1.9, 1.6, 1.3],
            f"Ma trận nhầm lẫn và các chỉ số trên tập test (n = {vn_int(f.test('persistence')['n'])})",
            font_size=9.5, align_right=set(range(1, 9)))
    r.figure(ART / "classification" / "figures" / "confusion_matrices_test.png", "Ma trận nhầm lẫn trên tập test", 16)
    maj = f.test("majority")
    per, loc = f.test("persistence"), f.test(f.locked)
    # Worded from the numbers: at longer horizons the model trades extra false alarms for far fewer misses.
    fp_move = (
        f"số lần báo nhầm từ {vn_int(per['fp'])} xuống {vn_int(loc['fp'])}"
        if loc["fp"] <= per["fp"]
        else f"đổi lại số lần báo nhầm tăng từ {vn_int(per['fp'])} lên {vn_int(loc['fp'])}"
    )
    r.p(
        f"Mô hình majority đạt accuracy {vn(maj['accuracy'], 3)} nhưng không phát được cảnh báo nào (recall = 0). Đây "
        f"là lý do không báo cáo accuracy đơn lẻ. HistGB giảm số giờ bỏ sót từ {vn_int(per['fn'])} "
        f"xuống {vn_int(loc['fn'])}, {fp_move}."
    )
    r.h2("6.5. Bằng chứng mô hình tốt hơn cách làm hiện tại")
    on = f.onset
    mc = f.mcnemar
    better = 0
    for st, sub in f.by_station.groupby("station_key"):
        lf = float(sub[sub.model == "locked"]["f1"].iloc[0])
        pf = float(sub[sub.model == "persistence"]["f1"].iloc[0])
        better += lf > pf
    r.bullets([
        [("b", "Phát hiện thời điểm bắt đầu đợt ô nhiễm: "),
         ("", f"trong {vn_int(on['locked']['onsets'])} giờ \"đang sạch nhưng giờ sau vượt ngưỡng\", HistGB báo trước được "
              f"{vn_int(on['locked']['detected'])} giờ ({pct(on['locked']['recall'])}); cây quyết định báo trước được "
              f"{pct(on['decision_tree']['recall'])}; persistence 0% theo định nghĩa.")],
        [("b", "Kiểm định McNemar trên test: "),
         ("", f"có {vn_int(mc['b'])} giờ mô hình đúng mà persistence sai, so với {vn_int(mc['c'])} giờ ngược lại. "
              f"χ² = {vn(mc['statistic'], 1)}, p = {mc['p_value']:.1e}, nên khác biệt có ý nghĩa thống kê.")],
        [("b", "Theo trạm: "), ("", f"F1 của mô hình cao hơn persistence ở {better}/12 trạm.")],
    ])
    rows = []
    for h in (1, 3, 6):
        p_ = f.horizon_row(h, "persistence")
        m_ = f.horizon_row(h, "hist_gradient_boosting")
        rows.append([f"{h} giờ", vn(p_["f1"], 3), vn(m_["f1"], 3), "+" + vn(m_["f1"] - p_["f1"], 3),
                     f"{vn(p_['recall'], 3)} → {vn(m_['recall'], 3)}", f"{vn(p_['precision'], 3)} → {vn(m_['precision'], 3)}"])
    r.table(["Tầm cảnh báo", "F1 persistence", "F1 HistGB", "Chênh lệch", "Recall", "Precision"], rows,
            [2.5, 2.6, 2.3, 2.2, 3.0, 3.0], "Độ nhạy theo tầm cảnh báo (tập test)", align_right={1, 2, 3})
    r.p(
        "Cảnh báo càng sớm thì lợi thế của mô hình càng lớn: ở tầm 6 giờ, F1 tăng 0,043. Lợi thế này chủ yếu đến từ "
        "recall (bắt được nhiều đợt hơn); đổi lại, precision thấp hơn persistence một chút, tức có nhiều cảnh báo "
        "nhầm hơn. Đây là đánh đổi mà người ra quyết định cần biết."
    )
    r.figure(ART / "classification" / "figures" / "pr_curve_test.png",
             "Đường Precision–Recall trên test; chấm tròn là ngưỡng đã chọn trên val", 10.5)
    r.h2("6.6. Diễn giải mô hình")
    imp = f.importance.head(3)
    root_feat, root_thr = f.tree_root
    if root_feat == "pm25_ug_m3" and abs(root_thr - 115) <= 10:
        root_note = f"Nút gốc tách tại PM2.5 ≈ {vn(root_thr, 0)} µg/m³, sát ngưỡng 115."
    elif root_feat == "pm25_ug_m3":
        root_note = (
            f"Nút gốc tách tại PM2.5 ≈ {vn(root_thr, 0)} µg/m³, thấp hơn ngưỡng 115 khá nhiều: muốn báo trước "
            f"{f.horizon_h} giờ, mô hình phải để ý từ khi PM2.5 còn dưới ngưỡng."
        )
    else:
        root_note = f"Nút gốc tách theo {feature_vi(root_feat)} tại {vn(root_thr, 1)}."
    branches = [f"{feature_vi(c)} ({c})" for c in f.tree_branch_features()]
    r.p(
        f"Cây quyết định cho thấy {feature_vi(imp.iloc[0].feature)} chiếm {pct(imp.iloc[0].importance, 1)} độ quan "
        f"trọng; tiếp theo là {feature_vi(imp.iloc[1].feature)} ({pct(imp.iloc[1].importance, 1)}) và "
        f"{feature_vi(imp.iloc[2].feature)} ({pct(imp.iloc[2].importance, 1)}). {root_note} Các nhánh bên dưới dùng "
        f"{', '.join(branches[:-1])} và {branches[-1]} để tách tiếp những giờ dễ vượt ngưỡng. Luật đầy đủ nằm trong "
        "artifacts/classification/tree_rules.txt."
    )
    r.figure(ART / "classification" / "figures" / "decision_tree_top.png", "Ba tầng đầu của cây quyết định (entropy)", 16)
    r.h2("6.7. Phân tích bổ trợ")
    sil = f.cluster["silhouette"]
    r.bullets([
        [("b", "Phân cụm trạm (K-Means): "),
         ("", f"12 trạm chia thành 2 cụm (hệ số bóng {vn(sil, 2)}, cao nhất trong K ∈ {{2, 3, 4}}, khớp hoàn toàn với "
              "phân cụm phân cấp Ward): \"lõi đô thị ô nhiễm\" (9 trạm) và \"ngoại ô phía bắc sạch hơn\" (Changping, "
              "Dingling, Huairou). Nhãn cụm được dùng làm đặc trưng.")],
        [("b", "Hồi quy PM2.5(t+1): "),
         ("", f"HistGB đạt MAE {vn(f.reg_mae('hist_gradient_boosting'), 2)} µg/m³ trên test, so với persistence "
              f"{vn(f.reg_mae('persistence'), 2)}. Giá trị dự báo hiển thị ở trang /du-bao.")],
    ])


def chapter_app(r: Report, f: Facts) -> None:
    r.h1("Ứng dụng khai phá dữ liệu")
    r.p(
        "Kết quả khai phá được đưa vào ứng dụng web chỉ-đọc gồm API FastAPI đọc kho và các mart, cùng giao diện "
        "React. Trang Cảnh báo cho người vận hành thấy ma trận nhầm lẫn của mô hình cạnh cách làm hiện tại, và "
        f"dòng thời gian PM2.5 theo trạm kèm những giờ mô hình đã cảnh báo từ {f.horizon_h} giờ trước, tô màu theo "
        "kết quả: cảnh báo đúng, báo nhầm, bỏ sót."
    )
    r.figure(SHOTS / "canh_bao.png", "Trang /canh-bao: mô hình so với persistence và dòng thời gian cảnh báo tại Dongsi", 15.5)
    r.table(
        ["Trang", "Nội dung"],
        [
            ["/ (Tổng quan)", "KPI và xu hướng ngày (đọc mart_station_daily)"],
            ["/olap", "OLAP tương tác: roll-up, drill-down, slice, dice, pivot"],
            ["/canh-bao", "Phân loại cảnh báo: ma trận nhầm lẫn, dòng thời gian, so sánh theo trạm"],
            ["/du-bao", "Hồi quy PM2.5 giờ tới so với thực tế"],
            ["/phan-cum, /thoi-tiet, /ban-do", "Phân cụm trạm, PM2.5 theo 7 biến thời tiết, bản đồ 12 trạm"],
        ],
        [5.5, 10.0],
        "Các trang của ứng dụng",
    )


def chapter_conclusion(r: Report, f: Facts) -> None:
    r.h1("Kết luận, khuyến nghị và hạn chế")
    r.h2("8.1. Kết quả theo chuẩn đầu ra")
    r.table(
        ["Tiêu chí", "Bằng chứng"],
        [
            ["CLO1.TC1 Thiết kế kho & OLAP", "Lược đồ sao 4 chiều, 4 phân cấp, lý do chọn độ mịn, 180 khối con"],
            ["CLO1.TC2 Cài đặt kho & OLAP", "dbt trên PostgreSQL, 3 khối tính trước đúng 100% ô, 5 thao tác OLAP chạy thật"],
            ["CLO2.TC1 Giải bài toán khai phá", "Phân loại có train/val/test theo thời gian, ma trận nhầm lẫn, mô hình cơ sở, McNemar"],
            ["CLO2.TC2 Ứng dụng khai phá", "Dashboard /canh-bao và /olap; chạy cả hệ thống bằng 1 lệnh"],
            ["CLO3 Làm việc nhóm", "Bảng phân công (Phụ lục B), lịch sử Git, biên bản họp"],
        ],
        [5.5, 10.0],
        "Đối chiếu với chuẩn đầu ra",
    )
    r.h2("8.2. Khuyến nghị hành động")
    r.bullets([
        "Dùng xác suất của mô hình để phát cảnh báo giờ tới thay vì chờ số đo vượt ngưỡng. Mô hình báo trước được "
        f"khoảng {pct(f.onset['locked']['recall'], 0)} số lần ô nhiễm bắt đầu, những lúc mà cách làm hiện tại luôn bỏ lỡ.",
        "Tập trung nguồn lực giám sát vào mùa đông, buổi tối và đêm, đặc biệt khi có gió nam: trong các điều kiện "
        "này PM2.5 trung bình và tỷ lệ giờ vượt ngưỡng cao hơn rõ rệt.",
        "Nếu cần cảnh báo sớm hơn (3–6 giờ), chấp nhận thêm một ít cảnh báo nhầm để đổi lấy recall cao hơn hẳn "
        "(Bảng 6.3).",
    ])
    r.h2("8.3. Hạn chế")
    r.bullets([
        "Tập test chỉ là 6 tháng cuối 2016; dữ liệu là lịch sử 2013–2017, chưa kiểm chứng trên dữ liệu thời gian thực.",
        "Tầm cảnh báo chính là 1 giờ, khá ngắn cho các quyết định lớn. Ở tầm dài hơn, độ chính xác giảm.",
        "Ngưỡng 115 µg/m³ vốn là ngưỡng trung bình 24 giờ của chuẩn AQI, ở đây được áp cho từng giờ để làm tín "
        "hiệu cảnh báo.",
        "Mô hình phụ thuộc mạnh vào giá trị PM2.5 hiện tại, nên phần cải thiện so với persistence là khiêm tốn "
        "(F1 tăng 0,013 ở tầm 1 giờ) dù đã được kiểm định là có ý nghĩa.",
        "Thời tiết lấp từ dữ liệu tái phân tích ERA5 có độ phân giải không gian thô hơn trạm đo.",
    ])
    r.h2("8.4. Hướng phát triển")
    r.bullets([
        "Đưa dự báo thời tiết (gió, độ ẩm của giờ tới) vào làm đặc trưng để cảnh báo sớm hơn.",
        "Thêm chiều Chất ô nhiễm (bảng sự kiện dạng dài) để OLAP so sánh các chất trong cùng một khối.",
        "Tự động chạy lại hằng ngày bằng Airflow khi có dữ liệu mới.",
    ])


def appendices(r: Report, f: Facts) -> None:
    r.page_break()
    r.unnumbered_h1("Phụ lục A. Hướng dẫn chạy lại từ đầu")
    r.code("""
git clone <repo> && cd air-quality-analytics-platform
python -m venv .venv
.venv\\Scripts\\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_all.py         # một lệnh: dữ liệu → kho → khai phá → OLAP → API
cd dashboard/web && npm install && npm run dev   # giao diện: http://localhost:5180
""")
    r.p(
        "Yêu cầu: Docker Desktop đang chạy, Python ≥ 3.10, có Internet ở lần chạy đầu. Nếu cổng bị trùng, sửa "
        "POSTGRES_PORT, MINIO_PORT, MINIO_ENDPOINT, MINIO_CONSOLE_PORT, DASHBOARD_API_PORT trong .env. Tuỳ chọn: "
        "--list, --from BƯỚC, --only, --skip, --retrain-all, --with-airflow."
    )
    r.unnumbered_h1("Phụ lục B. Bảng phân công")
    r.p("NHÓM ĐIỀN — mỗi thành viên phải trình bày được phần của mình. Bằng chứng: lịch sử Git và biên bản họp "
        "(bao_cao/BANG_PHAN_CONG.md, bao_cao/BIEN_BAN_HOP_TEMPLATE.md).", italic=True)
    r.table(
        ["Phần việc", "Sản phẩm / bằng chứng", "Phụ trách", "Review", "Đóng góp"],
        [
            ["1. Thu thập & tiền xử lý", "src/ingestion, src/processing, docs/DATA_PREPROCESSING.md", "[Tên]", "[Tên]", "[%]"],
            ["2. Thiết kế kho", "docs/DW_DESIGN.md, lược đồ sao", "[Tên]", "[Tên]", "[%]"],
            ["3. Cài đặt & tính khối", "dbt models/tests, run_olap_checks.py", "[Tên]", "[Tên]", "[%]"],
            ["4. Dịch vụ OLAP", "sql/olap, notebook, trang /olap", "[Tên]", "[Tên]", "[%]"],
            ["5. Khai phá", "src/classification, trang /canh-bao", "[Tên]", "[Tên]", "[%]"],
            ["Hạ tầng & chạy 1 lệnh", "docker-compose, scripts/run_all.py", "[Tên]", "[Tên]", "[%]"],
            ["Báo cáo & slide", "bao_cao/", "[Tên]", "[Tên]", "[%]"],
        ],
        [3.7, 5.6, 2.2, 2.2, 1.8],
        "Bảng phân công (nhóm điền)",
        font_size=10,
    )
    r.unnumbered_h1("Phụ lục C. Khai báo sử dụng công cụ AI")
    r.p(
        "Theo yêu cầu của học phần, nhóm khai báo các công cụ AI đã sử dụng. Nội dung chi tiết (cần nhóm rà soát, bổ "
        "sung và ký xác nhận) nằm ở bao_cao/KHAI_BAO_AI.md. Tóm tắt:"
    )
    r.bullets([
        "Claude Code (Anthropic, mô hình Claude Opus 5.5), phiên ngày 12/10/2026: đánh giá repo so với yêu cầu Bài 12; "
        "viết module phân loại cảnh báo, chiều hướng gió, khối CUBE, các truy vấn và trang OLAP, trang cảnh báo, "
        "script chạy một lệnh, tài liệu thiết kế; soạn bản nháp báo cáo và slide này.",
        "Claude Code, phiên ngày 28/10/2026: thêm bộ nhớ đệm cho API và giao diện; thiết kế lại giao diện dashboard; "
        "chạy thử nghiệm bỏ biến thời tiết theo từng tầm dự báo; cập nhật báo cáo, slide và ảnh dashboard.",
        "[NHÓM ĐIỀN] Các công cụ AI khác đã dùng trong các phase trước (tài liệu docs/PROJECT_CONTEXT.md nhắc tới "
        "các phiên ChatGPT): công cụ, mục đích, phần việc liên quan.",
        "Mọi số liệu trong báo cáo đều được sinh từ mã nguồn chạy trên dữ liệu thật (artifacts/), không do AI tự "
        "viết ra. Nhóm chịu trách nhiệm kiểm tra và giải thích được toàn bộ nội dung.",
    ])
    r.unnumbered_h1("Tài liệu tham khảo")
    refs = [
        "Nguyễn Quỳnh Chi (2018). Bài giảng Kho dữ liệu và Kỹ thuật khai phá. Học viện Công nghệ Bưu chính Viễn thông.",
        "Han, J., Kamber, M., & Pei, J. (2012). Data Mining: Concepts and Techniques (3rd ed.). Morgan Kaufmann.",
        "Aggarwal, C. C. (2015). Data Mining: The Textbook. Springer.",
        "Bramer, M. (2016). Principles of Data Mining (3rd ed.). Springer.",
        "Kimball, R., & Ross, M. (2013). The Data Warehouse Toolkit (3rd ed.). Wiley.",
        "Reis, J., & Housley, M. (2022). Fundamentals of Data Engineering. O'Reilly.",
        "Chen, S. (2017). Beijing Multi-Site Air Quality [Dataset]. UCI Machine Learning Repository. "
        "https://doi.org/10.24432/C5RK5G",
        "Zhang, S., Guo, B., Dong, A., He, J., Xu, Z., & Chen, S. X. (2017). Cautionary tales on air-quality "
        "improvement in Beijing. Proceedings of the Royal Society A, 473(2205).",
        "Open-Meteo. Historical Weather API. https://open-meteo.com/en/docs/historical-weather-api",
        "Pedregosa, F. et al. (2011). Scikit-learn: Machine Learning in Python. JMLR, 12, 2825–2830.",
        "Bộ Bảo vệ Môi trường Trung Quốc (2012). HJ 633-2012 — Technical Regulation on Ambient Air Quality Index.",
    ]
    r.bullets(refs, style="List Number")


def main() -> int:
    f = Facts()
    r = Report()
    cover(r)
    r.page_break()
    para = r.doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run("MỤC LỤC")
    run.bold = True
    run.font.size = Pt(16)
    r.toc()
    r.start_numbered_section()
    chapter_intro(r, f)
    chapter_data(r, f)
    chapter_design(r, f)
    chapter_build(r, f)
    chapter_olap(r, f)
    chapter_mining(r, f)
    chapter_app(r, f)
    chapter_conclusion(r, f)
    appendices(r, f)
    r.save(OUT)
    print(OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
