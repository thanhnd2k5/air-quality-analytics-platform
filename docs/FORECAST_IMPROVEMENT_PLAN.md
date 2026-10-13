# Forecast improvement — Feature + HistGB

## Vòng A (Feature + HistGB v2) — DONE + Promoted

Scope: giai đoạn 1. **Không** gồm LSTM.

### Giữ nguyên

- Target: PM2.5(t+1h); split train≤2015 / val 2016 H1 / test 2016 H2
- Production lock (sau Promote): `artifacts/forecasting/model_lock.json` (HistGB v2 test MAE ≈ 8.87)

### Checklist A

- [x] **A1** Extract pollutants + `FEATURE_COLS_V2` + matrix/QC/dictionary  
  `py -3 scripts/run_forecasting_v2a.py` → 372 499 rows, 45 features, QC ok
- [x] **A2** HistGB v2 + sample weight + so sánh vs lock cũ  
  `py -3 scripts/run_forecasting_v2b.py` → test MAE **8.87** (v1 9.14, persistence 9.78)
- [x] **A3** Error analysis v2 + khuyến nghị  
  `py -3 scripts/run_forecasting_v2c.py` → `error_analysis_v2.md`
- [x] Promote: `py -3 scripts/promote_forecast_v2.py`

### Feature v2 (causal)

- `pm25_delta_1`
- PM10 / CO / NO2 @ t + lags 1,2,3,6 + missing flags
- `hours_into_episode`, `in_episode_flag` (streak ≥3 tại threshold 115)

---

## Feature v3 (O3/SO2 + cloud_cover) — DONE thí nghiệm

Scope: thêm O3/SO2 + `cloud_cover_pct` trên HistGB (cùng hyperparams + sample weight). **Không** Promote trong vòng này trừ khi quyết định riêng.

Baseline so sánh: HistGB v2 production (test MAE ≈ **8.87**).

### Checklist B-feature

- [x] **B1** Extract O3/SO2/cloud_cover + `FEATURE_COLS_V3` + matrix/QC/dictionary  
  `py -3 scripts/run_forecasting_v3a.py` → 372 499 rows, 60 features, QC ok
- [x] **B2** HistGB v3 + sample weight + so sánh vs v2  
  `py -3 scripts/run_forecasting_v3b.py` → test MAE **8.860** (v2 8.872, persistence 9.783)
- [x] **B3** Error analysis v3 + khuyến nghị  
  `py -3 scripts/run_forecasting_v3c.py` → `error_analysis_v3.md` (cân nhắc Promote; gain nhỏ; winter hơi kém v2)

### Feature v3 (thêm so với v2)

- `o3_ug_m3`, `so2_ug_m3` @ t + lags 1,2,3,6 + missing
- `cloud_cover_pct` @ t + lag 1 + missing (Open-Meteo)

### Kết quả ngắn

| Model | Test MAE |
|-------|----------|
| Persistence | 9.783 |
| HistGB v2 (prod) | 8.872 |
| HistGB v3 | **8.860** |

Δ vs v2 ≈ **−0.012** (thắng mỏng). Winter MAE v3 ≈ 14.13 vs v2 ≈ 14.08 (hơi kém). Production lock **chưa** đổi.

### Ngoài scope (còn lại)

regional K=6, `hours_since_last_episode`, retune HistGB grid, ghi đè mart/UI trừ khi Promote riêng.

---

## Vòng B — LSTM thí nghiệm — DONE thí nghiệm

Scope: LSTM t+1h trên cửa sổ 24h (feature slim từ `feature_matrix_v2`), so với HistGB v2 production. **Không** Promote / không đụng mart / UI.

Baseline: persistence + HistGB v2 (test MAE ≈ **8.87**). Artifact prefix `lstm_exp_*`.

### Checklist LSTM

- [x] **L1** `LSTM_SEQ_COLS` + `src/forecasting/lstm_data.py` + `lstm_model.py` + unit tests + `torch`  
  `py -3 -m pytest tests/unit/test_forecasting_lstm.py -q`
- [x] **L2** Train + early stop + metrics/comparison (CUDA, best_epoch=19)  
  `py -3 scripts/run_forecasting_lstm_b.py` → test MAE **8.851** (v2 8.872, persistence 9.741)
- [x] **L3** Error analysis + khuyến nghị  
  `py -3 scripts/run_forecasting_lstm_c.py` → `lstm_exp_error_analysis.md`

### Quyết định kỹ thuật

- PyTorch 1× LSTM(hidden=64) + station emb(8) concat mỗi timestep; dropout 0.1
- SEQ_LEN=24; scale StandardScaler fit train-only; Adam lr=1e-3; batch=256; max 30 epoch; early stop val MAE patience=5
- Promote chỉ cân nhắc nếu test MAE &lt; 8.87 và &lt; persistence (plan riêng)

### Kết quả ngắn

| Model | Test MAE |
|-------|----------|
| Persistence (seq rows) | 9.741 |
| HistGB v2 (prod) | 8.872 |
| LSTM exp | **8.851** |

Δ vs v2 ≈ **−0.020** (thắng mỏng). Winter MAE LSTM ≈ 14.75 vs v2 ≈ 14.08 (kém hơn). High-bin ≥150 LSTM ≈ 15.26 vs v2 ≈ 16.60 (tốt hơn). Production lock **chưa** đổi.
