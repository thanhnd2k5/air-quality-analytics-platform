| Cột (UCI) | Cột trong kho | Thiếu | Tỷ lệ | Trạm tệ nhất | Chuỗi thiếu dài nhất | Còn thiếu trong fact | Cách xử lý |
|---|---|---:|---:|---:|---:|---:|---|
| PM2.5 | `pm25_ug_m3` | 8,739 | 2.08% | 2.72% | 343 giờ | 8,739 | Giữ NULL, không nội suy; gắn cờ has_missing_pollutant / MISSING_MEASUREMENT. Khai phá: dòng thiếu PM2.5 tại t hoặc t+1 bị loại khỏi ma trận đặc trưng. Giá trị trần 999 gắn cờ SUSPECT_CAP. |
| PM10 | `pm10_ug_m3` | 6,449 | 1.53% | 2.22% | 343 giờ | 6,449 | Giữ NULL trong kho. Khai phá: điền median của tập TRAIN + cờ *_missing (không dùng thông tin val/test). Giá trị trần 999 gắn cờ SUSPECT_CAP. |
| SO2 | `so2_ug_m3` | 9,021 | 2.14% | 3.70% | 457 giờ | 9,021 | Giữ NULL + cờ; không dùng làm đặc trưng khai phá. |
| NO2 | `no2_ug_m3` | 12,116 | 2.88% | 4.67% | 900 giờ | 12,116 | Giữ NULL trong kho. Khai phá: điền median của tập TRAIN + cờ *_missing (không dùng thông tin val/test). |
| CO | `co_ug_m3` | 20,701 | 4.92% | 9.12% | 1517 giờ | 20,701 | Giữ NULL trong kho. Khai phá: điền median của tập TRAIN + cờ *_missing (không dùng thông tin val/test). Giá trị trần 10000 gắn cờ SUSPECT_CAP. |
| O3 | `o3_ug_m3` | 13,277 | 3.15% | 6.01% | 497 giờ | 13,277 | Giữ NULL + cờ; không dùng làm đặc trưng khai phá. |
| TEMP | `temperature_c` | 398 | 0.10% | 0.15% | 7 giờ | 0 | Lấp từ Open-Meteo (ERA5) khi UCI thiếu; cột *_source ghi nguồn. Khai phá: median TRAIN + cờ *_missing nếu vẫn thiếu. |
| PRES | `pressure_hpa` | 393 | 0.09% | 0.15% | 7 giờ | 0 | Lấp từ Open-Meteo (ERA5) khi UCI thiếu; cột *_source ghi nguồn. Khai phá: median TRAIN + cờ *_missing nếu vẫn thiếu. |
| DEWP | `dew_point_c` | 403 | 0.10% | 0.15% | 7 giờ | 0 | Lấp từ Open-Meteo (ERA5) khi UCI thiếu; cột *_source ghi nguồn. Khai phá: median TRAIN + cờ *_missing nếu vẫn thiếu. Dùng cùng TEMP để suy ra độ ẩm tương đối (công thức Magnus). |
| RAIN | `rain_mm` | 390 | 0.09% | 0.16% | 6 giờ | 0 | Lấp từ Open-Meteo (ERA5) khi UCI thiếu; cột *_source ghi nguồn. Khai phá: median TRAIN + cờ *_missing nếu vẫn thiếu. |
| WSPM | `wind_speed_m_s` | 318 | 0.08% | 0.14% | 5 giờ | 0 | Lấp từ Open-Meteo (ERA5) khi UCI thiếu; cột *_source ghi nguồn. Khai phá: median TRAIN + cờ *_missing nếu vẫn thiếu. |
| wd | `wind_direction` | 1,822 | 0.43% | 1.38% | 13 giờ | 0 | Lấp từ hướng gió Open-Meteo (độ → 16 hướng, macro compass_16); nếu vẫn thiếu → khoá UNKNOWN (0) của dim_wind_direction. |

Tổng 420,768 dòng (12 trạm × 35 064 giờ, 2013-03-01 → 2017-02-28). Các cột No, year, month, day, hour, station không thiếu; ghép thành event_time_local.
