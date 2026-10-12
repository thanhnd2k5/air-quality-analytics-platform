# DATA_PREPROCESSING.md — Nguồn dữ liệu, giấy phép và tiền xử lý

> Phần 1 của bài tập lớn: mô tả nguồn, số bản ghi/thuộc tính, khoảng thời gian, tỷ lệ thiếu và cách xử lý **từng cột**.
> Chi tiết hơn về từng biến: `docs/DATA_GUIDE.md`. Báo cáo profiling gốc: `artifacts/data_profile/profiling_report.md`.

## 1. Nguồn dữ liệu và giấy phép

| | Nguồn chính | Nguồn bổ sung |
|---|---|---|
| Tên | Beijing Multi-Site Air Quality (PRSA) | Open-Meteo Historical Weather API |
| Đường dẫn | https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality | https://open-meteo.com/en/docs/historical-weather-api |
| Trích dẫn | Chen, S. (2017). *Beijing Multi-Site Air Quality* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5RK5G | Open-Meteo.com (dữ liệu tái phân tích ERA5 / Copernicus) |
| Giấy phép | **CC BY 4.0** (Creative Commons Attribution 4.0 International) | Dữ liệu theo **CC BY 4.0**; API miễn phí cho mục đích **phi thương mại** (bài tập lớn thuộc phạm vi này) |
| Cách lấy | `python scripts/download_uci_dataset.py` (tự kiểm tra kích thước từng file theo `data/raw/reference/file_inventory.csv`) | `python scripts/ingest_openmeteo_station.py --all` |
| Dữ liệu cá nhân | Không có. Chỉ là số đo môi trường theo trạm. | Không có |

Toạ độ 12 trạm (`data/raw/reference/stations.csv`) lấy từ tài liệu công khai, xem nguồn trích trong `docs/PROJECT_CONTEXT.md` (mục toạ độ trạm, quanh dòng 543).

## 2. Quy mô

- **420 768 bản ghi** = 12 trạm × 35 064 giờ, từ 2013-03-01 00:00 đến 2017-02-28 23:00 (giờ địa phương Bắc Kinh).
- **18 cột gốc / 12 thuộc tính đo có ý nghĩa:**
  - 6 chất ô nhiễm: PM2.5, PM10, SO2, NO2, CO, O3;
  - 5 biến khí tượng số: TEMP, PRES, DEWP, RAIN, WSPM;
  - 1 biến phân loại: hướng gió `wd`.
- Có thuộc tính thời gian (year, month, day, hour), từ đó dựng chiều Thời gian và chiều Giờ.
- Bổ sung từ Open-Meteo: `cloud_cover_pct` và các biến thời tiết dùng để lấp chỗ trống. Thêm thuộc tính suy diễn: độ ẩm tương đối (từ TEMP + DEWP, công thức Magnus).

## 3. Tỷ lệ giá trị thiếu và cách xử lý từng cột

Sinh bằng `python scripts/build_missing_table.py`, ghi ra `artifacts/data_profile/missing_by_column.csv` và `missing_by_column.md`. Cột "Còn thiếu trong fact" đếm trực tiếp trên `dwh.fact_air_quality_hourly`.

| Cột (UCI) | Cột trong kho | Thiếu | Tỷ lệ | Trạm tệ nhất | Chuỗi thiếu dài nhất | Còn thiếu trong fact | Cách xử lý |
|---|---|---:|---:|---:|---:|---:|---|
| PM2.5 | `pm25_ug_m3` | 8,739 | 2.08% | 2.72% | 343 giờ | 8,739 | Giữ NULL, không nội suy; gắn cờ has_missing_pollutant / MISSING_MEASUREMENT. Khai phá: dòng thiếu PM2.5 tại t hoặc t+1 bị loại khỏi ma trận đặc trưng. Giá trị trần 999 gắn cờ SUSPECT_CAP. |
| PM10 | `pm10_ug_m3` | 6,449 | 1.53% | 2.22% | 343 giờ | 6,449 | Giữ NULL trong kho. Khai phá: điền median của tập TRAIN + cờ *_missing (không dùng thông tin val/test). Giá trị trần 999 gắn cờ SUSPECT_CAP. |
| SO2 | `so2_ug_m3` | 9,021 | 2.14% | 3.70% | 457 giờ | 9,021 | Giữ NULL + cờ; không dùng làm đặc trưng khai phá. |
| NO2 | `no2_ug_m3` | 12,116 | 2.88% | 4.67% | 900 giờ | 12,116 | Giữ NULL trong kho. Khai phá: điền median của tập TRAIN + cờ *_missing (không dùng thông tin val/test). |
| CO | `co_ug_m3` | 20,701 | 4.92% | 9.12% | 1517 giờ | 20,701 | Giữ NULL trong kho. Khai phá: điền median của tập TRAIN + cờ *_missing (không dùng thông tin val/test). Giá trị trần 10000 gắn cờ SUSPECT_CAP. |
| O3 | `o3_ug_m3` | 13,277 | 3.15% | 6.01% | 497 giờ | 13,277 | Giữ NULL + cờ; không dùng làm đặc trưng khai phá. |
| TEMP | `temperature_c` | 398 | 0.10% | 0.15% | 7 giờ | 0 | Lấp từ Open-Meteo (ERA5) khi UCI thiếu; cột *_source ghi nguồn. Khai phá: median TRAIN + cờ *_missing nếu vẫn thiếu. |
| PRES | `pressure_hpa` | 393 | 0.09% | 0.15% | 7 giờ | 0 | Lấp từ Open-Meteo (ERA5) khi UCI thiếu; cột *_source ghi nguồn. |
| DEWP | `dew_point_c` | 403 | 0.10% | 0.15% | 7 giờ | 0 | Lấp từ Open-Meteo (ERA5) khi UCI thiếu. Dùng cùng TEMP để suy ra độ ẩm tương đối (công thức Magnus). |
| RAIN | `rain_mm` | 390 | 0.09% | 0.16% | 6 giờ | 0 | Lấp từ Open-Meteo (ERA5) khi UCI thiếu; cột *_source ghi nguồn. |
| WSPM | `wind_speed_m_s` | 318 | 0.08% | 0.14% | 5 giờ | 0 | Lấp từ Open-Meteo (ERA5) khi UCI thiếu. Khai phá: median TRAIN + cờ *_missing nếu vẫn thiếu. |
| wd | `wind_direction` | 1,822 | 0.43% | 1.38% | 13 giờ | 0 | Lấp từ hướng gió Open-Meteo (độ → 16 hướng, macro `compass_16`); nếu vẫn thiếu → khoá UNKNOWN (0) của `dim_wind_direction`. |

**Vì sao không nội suy chất ô nhiễm trong kho?**
- PM2.5 có những chuỗi thiếu dài tới 343 giờ (hơn 14 ngày). Nội suy qua các khoảng như vậy là bịa dữ liệu, và sẽ làm sai cả trung bình OLAP lẫn nhãn khai phá.
- Kho giữ NULL kèm cờ `data_quality_status` để người phân tích tự quyết định. Mọi trung bình trong mart đều đi kèm `*_hour_count`: số giờ có dữ liệu thật đã tham gia tính.

**Vì sao chỉ lấp thời tiết?**
- Thời tiết có nguồn độc lập đáng tin (tái phân tích ERA5), nên lấp được mà không phải đoán.
- Mỗi giá trị được lấp đều ghi nguồn vào cột `*_source`, truy vết được.

## 4. Các bước làm sạch khác

| Bước | Quy tắc | Kết quả trên dữ liệu thật |
|---|---|---|
| Khoá tự nhiên | (trạm, event_time_local) phải duy nhất. Trùng thì dừng pipeline. | 0 bản trùng |
| Giá trị âm không hợp lệ | 6 chất ô nhiễm, lượng mưa, tốc độ gió < 0 → đưa vào quarantine trên MinIO, không nạp vào kho. TEMP/DEWP âm là hợp lệ. | 0 dòng quarantine (staging = fact = 420 768) |
| Giá trị trần thiết bị | PM2.5 = 999, PM10 = 999, CO = 10000 → giữ lại, gắn cờ `SUSPECT_CAP` | 60 dòng |
| Chuẩn hoá thời gian | year/month/day/hour → `event_time_local` (giờ Bắc Kinh), khoá ngày `YYYYMMDD`, khoá giờ 0–23 | — |
| Chuẩn hoá đơn vị / tên cột | `PM2.5` → `pm25_ug_m3`, `WSPM` → `wind_speed_m_s`, … (`src/processing/schema.py`) | — |
| Trạng thái chất lượng | `OK` / `MISSING_MEASUREMENT` / `SUSPECT_CAP` cho từng dòng fact | 383 924 / 36 784 / 60 |

## 5. Rời rạc hoá phục vụ phân tích

| Thuộc tính liên tục | Rời rạc thành | Ở đâu |
|---|---|---|
| giờ (0–23) | buổi: đêm / sáng / chiều / tối | `dim_time.day_part` |
| ngày | mùa khí tượng (DJF/MAM/JJA/SON) | `dim_date.season` |
| hướng gió 16 điểm | phần tư (4) → chế độ gió bắc/nam (2) | `dim_wind_direction` |
| PM2.5 | nhãn cảnh báo: ≥ 115 µg/m³ (1) / < 115 (0) | `src/classification/target.py` |
