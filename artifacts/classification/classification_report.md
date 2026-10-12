# Phân loại cảnh báo vượt ngưỡng PM2.5 (bài toán khai phá chính)

**Câu hỏi nghiệp vụ:** trung tâm quan trắc có nên phát cảnh báo *hạn chế hoạt động ngoài trời* cho **giờ tới** tại từng trạm không? Nhãn dương: PM2.5(t+1h) ≥ 115 µg/m³ (ngưỡng đợt ô nhiễm đã khoá ở Phase 8c).

**Chia tập (khoá từ đầu, theo thời gian):** train 2013-03 → 2015-12 · val 2016-01 → 2016-06 · test 2016-07 → 2016-12. Độ sâu cây và ngưỡng xác suất chỉ chọn trên val; test chỉ dùng để báo cáo.

## Kết quả trên tập test

| Mô hình | Ngưỡng | TP | FP | FN | TN | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|---|---|---|---|---|---|
| Majority (luôn 'không') | — | 0 | 0 | 11,646 | 37,135 | 0.761 | 0.000 | 0.000 | 0.000 | — |
| Persistence (PM2.5(t) ≥ 115) | — | 10,646 | 999 | 1,000 | 36,136 | 0.959 | 0.914 | 0.914 | 0.914 | — |
| Cây quyết định (entropy) | 0.45 | 10,768 | 961 | 878 | 36,174 | 0.962 | 0.918 | 0.925 | 0.921 | 0.991 |
| HistGradientBoosting | 0.50 | 10,808 | 865 | 838 | 36,270 | 0.965 | 0.926 | 0.928 | 0.927 | 0.993 |

- **Mô hình khoá:** `hist_gradient_boosting` (F1 val cao nhất), ngưỡng xác suất 0.50.
- **Accuracy dễ đánh lừa:** mô hình majority đạt accuracy 0.761 nhưng recall = 0 — không phát được cảnh báo nào.
- **Bắt đầu đợt ô nhiễm (onset):** trong 1,000 giờ đang sạch nhưng giờ sau vượt ngưỡng, mô hình phát hiện 304 (30.4%); persistence = 0% theo định nghĩa.
- **McNemar so với persistence (test):** b=594, c=298, p=5.22e-23 → khác biệt có ý nghĩa thống kê.

## Độ nhạy theo tầm dự báo (test F1)

| Tầm (giờ) | Persistence | HistGB | Chênh lệch |
|---|---|---|---|
| 1 | 0.914 | 0.927 | +0.013 |
| 3 | 0.806 | 0.832 | +0.026 |
| 6 | 0.702 | 0.745 | +0.043 |

## Thuộc tính quan trọng nhất (cây quyết định)

1. `pm25_ug_m3` — 0.974
2. `pm25_delta_1` — 0.015
3. `wind_speed_m_s` — 0.005
4. `pm10_ug_m3` — 0.002
5. `relative_humidity_pct` — 0.001
6. `pm25_roll_mean_24` — 0.001
7. `season_code` — 0.000
8. `pm10_ug_m3_lag_2` — 0.000

Hình: `figures/confusion_matrices_test.png`, `figures/pr_curve_test.png`, `figures/threshold_tuning_val.png`, `figures/decision_tree_top.png`, `figures/feature_importance_tree.png`, `figures/horizon_sensitivity.png`.
