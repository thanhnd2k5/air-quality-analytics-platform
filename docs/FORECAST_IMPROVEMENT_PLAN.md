# Forecast improvement — Vòng A (Feature + HistGB v2)

Scope: giai đoạn 1/2. **Không** gồm LSTM (Vòng B) hay Promote mart/dashboard.

## Giữ nguyên

- Target: PM2.5(t+1h); split train≤2015 / val 2016 H1 / test 2016 H2
- Production lock: `artifacts/forecasting/model_lock.json` (HistGB test MAE ≈ 9.14)
- Artifact thí nghiệm: hậu tố `_v2` / `models/pm25_forecast_v2/`

## Checklist

- [x] **A1** Extract pollutants + `FEATURE_COLS_V2` + matrix/QC/dictionary  
  `py -3 scripts/run_forecasting_v2a.py` → 372 499 rows, 45 features, QC ok
- [x] **A2** HistGB v2 + sample weight + so sánh vs lock cũ  
  `py -3 scripts/run_forecasting_v2b.py` → test MAE **8.87** (v1 9.14, persistence 9.78)
- [x] **A3** Error analysis v2 + khuyến nghị  
  `py -3 scripts/run_forecasting_v2c.py` → `error_analysis_v2.md` (cân nhắc Promote; chưa chạy Promote)

## Feature v2 (causal)

- `pm25_delta_1`
- PM10 / CO / NO2 @ t + lags 1,2,3,6 + missing flags (impute train median)
- `hours_into_episode`, `in_episode_flag` (streak ≥3 tại threshold 115)

## Ngoài scope A

O3/SO2, cloud_cover Open-Meteo, regional K=6, retune grid, LSTM, ghi đè mart/UI.

## Promote (sau Vòng A)

- [x] `py -3 scripts/promote_forecast_v2.py` — copy v2 → `model_lock.json` / `predictions_locked` / `models/pm25_forecast/`, backup v1, reload mart (P10d)
- Dashboard Predictions đọc mart mới (không cần đổi code UI)

## Sau Promote

- Vòng B: nghiên cứu mở rộng (LSTM / cloud_cover / …) khi cần
