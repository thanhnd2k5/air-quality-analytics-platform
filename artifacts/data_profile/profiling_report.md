# Full Dataset Profiling Report (12 PRSA Stations)

**Ngày thực hiện:** 2026-09-22  
**Phạm vi:** 12 trạm quan trắc chất lượng không khí Bắc Kinh (PRSA Dataset 2013-03-01 đến 2017-02-28)  
**Tự động tạo bởi:** `scripts/run_profiling.py`

---

## 1. Tóm tắt điều hành (Executive Summary)

- **Tổng số trạm quan sát:** 12 trạm
- **Tổng số bản ghi giờ (Station-Hours):** 420,768 dòng (mỗi trạm đúng 35,064 giờ)
- **Độ dài chuỗi thời gian:** Từ `2013-03-01 00:00:00` đến `2017-02-28 23:00:00` (4 năm tròn = 1,461 ngày = 35,064 giờ)
- **Schema Consistency:** ĐỒNG NHẤT 100% (18 cột khớp nhau trên toàn bộ 12 trạm)
- **Tính toàn vẹn dòng thời gian (Timeline Continuity):** HOÀN HẢO (0 duplicate timestamp, 0 missing hours)
- **Giá trị âm bất thường (Invalid Negatives):** Không có vi phạm vật lý (0 bản ghi)

---

## 2. Tổng quan 12 trạm (Station Profile)

| STT | Trạm | File | Số dòng | Timeline | Duplicates | Missing Hours | Trạng thái |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| 1 | Aotizhongxin | `PRSA_Data_Aotizhongxin_20130301-20170228.csv` | 35,064 | 2013-03-01 -> 2017-02-28 | 0 | 0 | OK |
| 2 | Changping | `PRSA_Data_Changping_20130301-20170228.csv` | 35,064 | 2013-03-01 -> 2017-02-28 | 0 | 0 | OK |
| 3 | Dingling | `PRSA_Data_Dingling_20130301-20170228.csv` | 35,064 | 2013-03-01 -> 2017-02-28 | 0 | 0 | OK |
| 4 | Dongsi | `PRSA_Data_Dongsi_20130301-20170228.csv` | 35,064 | 2013-03-01 -> 2017-02-28 | 0 | 0 | OK |
| 5 | Guanyuan | `PRSA_Data_Guanyuan_20130301-20170228.csv` | 35,064 | 2013-03-01 -> 2017-02-28 | 0 | 0 | OK |
| 6 | Gucheng | `PRSA_Data_Gucheng_20130301-20170228.csv` | 35,064 | 2013-03-01 -> 2017-02-28 | 0 | 0 | OK |
| 7 | Huairou | `PRSA_Data_Huairou_20130301-20170228.csv` | 35,064 | 2013-03-01 -> 2017-02-28 | 0 | 0 | OK |
| 8 | Nongzhanguan | `PRSA_Data_Nongzhanguan_20130301-20170228.csv` | 35,064 | 2013-03-01 -> 2017-02-28 | 0 | 0 | OK |
| 9 | Shunyi | `PRSA_Data_Shunyi_20130301-20170228.csv` | 35,064 | 2013-03-01 -> 2017-02-28 | 0 | 0 | OK |
| 10 | Tiantan | `PRSA_Data_Tiantan_20130301-20170228.csv` | 35,064 | 2013-03-01 -> 2017-02-28 | 0 | 0 | OK |
| 11 | Wanliu | `PRSA_Data_Wanliu_20130301-20170228.csv` | 35,064 | 2013-03-01 -> 2017-02-28 | 0 | 0 | OK |
| 12 | Wanshouxigong | `PRSA_Data_Wanshouxigong_20130301-20170228.csv` | 35,064 | 2013-03-01 -> 2017-02-28 | 0 | 0 | OK |

---

## 3. Thống kê Missing Value theo biến

### 3.1. Tỷ lệ Missing trung bình toàn dataset

| Biến | Phân loại | Tỷ lệ Missing TB (%) | Chuỗi Missing dài nhất (giờ) | Đánh giá & Khuyến nghị |
| :--- | :--- | :---: | :---: | :--- |
| `CO` | Chất ô nhiễm | 4.920% | 1517h | Gap dài (>3 ngày): Cần flag missing rõ ràng, không fill bừa vào target ML |
| `O3` | Chất ô nhiễm | 3.155% | 497h | Gap dài (>3 ngày): Cần flag missing rõ ràng, không fill bừa vào target ML |
| `NO2` | Chất ô nhiễm | 2.880% | 900h | Gap dài (>3 ngày): Cần flag missing rõ ràng, không fill bừa vào target ML |
| `SO2` | Chất ô nhiễm | 2.144% | 457h | Gap dài (>3 ngày): Cần flag missing rõ ràng, không fill bừa vào target ML |
| `PM2.5` | Chất ô nhiễm | 2.077% | 343h | Gap dài (>3 ngày): Cần flag missing rõ ràng, không fill bừa vào target ML |
| `PM10` | Chất ô nhiễm | 1.533% | 343h | Gap dài (>3 ngày): Cần flag missing rõ ràng, không fill bừa vào target ML |
| `wd` | Hướng gió | 0.433% | 13h | Gap ngắn: Forward fill / mode theo cửa sổ ngắn + gắn flag (không nội suy tuyến tính) |
| `DEWP` | Khí tượng | 0.096% | 7h | Gap ngắn: Nội suy tuyến tính (Linear interpolation) an toàn |
| `TEMP` | Khí tượng | 0.094% | 7h | Gap ngắn: Nội suy tuyến tính (Linear interpolation) an toàn |
| `PRES` | Khí tượng | 0.093% | 7h | Gap ngắn: Nội suy tuyến tính (Linear interpolation) an toàn |
| `RAIN` | Khí tượng | 0.093% | 6h | Gap ngắn: Nội suy tuyến tính (Linear interpolation) an toàn |
| `WSPM` | Khí tượng | 0.076% | 5h | Gap ngắn: Nội suy tuyến tính (Linear interpolation) an toàn |

---

## 4. Thống kê phân phối và giá trị biên (Extreme Values)

| Biến | Min | P25 | Median | P75 | P99 | Max | Mean | Std | Giá trị âm (<0) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `PM2.5` | 2.0 | 20.75 | 55.33 | 110.65 | 367.92 | 999.0 | 79.78 | 80.38 | 0 |
| `PM10` | 2.0 | 36.5 | 82.33 | 144.92 | 419.94 | 999.0 | 104.58 | 91.05 | 0 |
| `SO2` | 0.2856 | 2.75 | 7.42 | 19.58 | 102.42 | 500.0 | 15.82 | 21.37 | 0 |
| `NO2` | 1.0265 | 24.75 | 43.75 | 69.53 | 150.75 | 290.0 | 50.58 | 33.18 | 0 |
| `CO` | 100.0 | 491.67 | 866.67 | 1525.0 | 5801.08 | 10000.0 | 1230.62 | 1146.25 | 0 |
| `O3` | 0.2142 | 11.8 | 44.18 | 81.42 | 244.6 | 1071.0 | 57.35 | 56.47 | 0 |
| `TEMP` | -19.9 | 3.13 | 14.51 | 23.26 | 33.8 | 41.6 | 13.54 | 11.43 | 64249 (hợp lệ nhiệt độ) |
| `PRES` | 982.4 | 1002.25 | 1010.38 | 1018.98 | 1031.47 | 1042.8 | 1010.75 | 10.27 | 0 |
| `DEWP` | -43.4 | -8.91 | 3.02 | 15.11 | 24.47 | 29.1 | 2.49 | 13.78 | 185393 (hợp lệ nhiệt độ) |
| `RAIN` | 0.0 | 0.0 | 0.0 | 0.0 | 1.36 | 72.5 | 0.06 | 0.82 | 0 |
| `WSPM` | 0.0 | 0.92 | 1.39 | 2.22 | 6.01 | 13.2 | 1.73 | 1.23 | 0 |

---

## 5. Căn cứ cho Decision Gate (P1-39 đến P1-47)

1. **Grain DWH (P1-39)**: Đã xác thực dữ liệu là chuẩn `station-hour`. Mỗi trạm chứa đủ 35,064 giờ liên tục, không trùng lặp timestamp.
2. **Timeline 12 trạm (P1-40)**: Cả 12 trạm có cùng timeline chính xác (`2013-03-01 00:00` đến `2017-02-28 23:00`).
3. **Phân loại Missing (P1-42, P1-43)**: Đa phần các chuỗi missing của khí tượng ngắn hơn chất ô nhiễm. Với $PM_{2.5}$, có những chuỗi đứt đoạn cảm biến, cần quy định rõ chính sách không rò rỉ dữ liệu (no data leakage) khi huấn luyện mô hình.
4. **Extreme & Negative Values (P1-46)**: Toàn bộ chất ô nhiễm và lượng mưa đều $\ge 0$. Nhiệt độ `TEMP` và điểm sương `DEWP` có giá trị âm vào mùa đông là hoàn toàn tự nhiên và chính xác.
