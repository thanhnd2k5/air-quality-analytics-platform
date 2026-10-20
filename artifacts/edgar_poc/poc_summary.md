# EDGAR HTAP v3 – Beijing Extraction POC Summary & Assessment

**Generated:** 2026-10-19 17:08:46 UTC  
**Target Project:** Beijing Multi-Site PM2.5 Hourly Forecasting (12 UCI Stations)  
**Baseline Model Status:** HistGB v2 locked (Test MAE: 8.87 µg/m³)  
**Evaluated Data:** EDGAR HTAP v3 PM2.5 Monthly Emissions (Year 2015 only)  

---

## 1. Executive Summary & Final Verdict

### Final Assessment Verdict: `EDA_ONLY`

> [!IMPORTANT]
> **Verdict Rationale:**
> - **Data Integrity is High:** Structurally sound, fully covers 12 months of 2015 across 16 sectors, zero missing/NaN in the extracted sample.
> - **Joins Seamlessly:** Offline join against UCI 2015 on `station + year + month` achieved 100% match (105,120 rows) with zero row inflation.
> - **Useful for Spatial EDA:** Road/Residential emissions show positive spatial association with station PM2.5 (station-level $r \approx 0.63$–$0.70$; unique-grid $r$ reported below). This is association, not causal proof.
> - **Forecasting value not yet demonstrated:** POC ran EDA and correlation only — no forecasting ablation. A monthly-static feature can still act as a location/seasonality prior; it has **not** been shown to improve HistGB v2 beyond baseline.
> - **Why stay `EDA_ONLY` for now:**
>   1. Hourly Pearson $r$ is low ($\approx 0.00$–$0.15$) because values are constant within each month — expected, not proof of zero predictive value.
>   2. Spatial coarseness: 12 stations → 9 unique 0.1° cells; 6 stations share 3 cells.
>   3. **Availability lag for operational replay:** Inventory published years after 2015. Using it to simulate real-time $T \rightarrow T+24h$ forecasting for 2015 misrepresents feature availability. Historical explanatory analysis is fine; operational/online forecasting must treat availability explicitly.
>   4. Storage: ~5 GB raw → ~19 KB extracted for 12 stations (2015).
> - **Scope limit:** All conclusions below are for **2015 only**; do not extrapolate to 2013–2017 without additional years.

---

## 2. Data Quality & Sanity Check Summary

### A. Structural Verification
- **Extracted Stations:** 12 / 12 (100% mapped).
- **Extracted Months:** 12 / 12 (January to December 2015 continuous).
- **Total Records:** 144 rows (`12 stations × 12 months`).
- **Duplicates:** 0 duplicates.
- **Missing / NaN Values:** 0 across all sectors (100% complete).
- **Unique 0.1° Grid Cells:** 9 unique cells for 12 stations.

### B. Value Checks per Emission Sector (`ton/month`)

| Sector Feature | Min | Max | Mean | Median | Std | Zero Count | Negative Count | Missing |
|---|---|---|---|---|---|---|---|---|
| `road_emission` | 2.6211 | 23.955 | 12.7554 | 15.7139 | 6.6887 | 0 | 0 | 0 |
| `brake_tyre_emission` | 0.7602 | 3.6828 | 1.9823 | 1.8853 | 1.0755 | 0 | 0 | 0 |
| `industry_emission` | 0.6493 | 56.5356 | 17.9714 | 19.1939 | 13.9737 | 0 | 0 | 0 |
| `residential_emission` | 6.326 | 95.6701 | 49.7926 | 63.2937 | 28.3038 | 0 | 0 | 0 |
| `energy_emission` | 0.2362 | 162.747 | 33.2351 | 8.4584 | 50.4973 | 0 | 0 | 0 |
| `traffic_emission` | 3.4145 | 27.3354 | 14.7377 | 17.9919 | 7.6352 | 0 | 0 | 0 |

### C. Sector Contribution Breakdown (Selected Sample Scope)

> **Scope:** Percent of the 5 selected sectors only, computed on the extracted 12-station sample for 2015 (not full Beijing inventory / not all 16 HTAP sectors).

Shares below are **% of the five extracted sectors**, on the **12-station 2015 sample** (shared cells are counted once per station, so urban cells are over-weighted vs a unique-cell sum). They are **not** the full Beijing inventory and **not** all 16 HTAP sectors.

- **Residential (`residential_emission`):** 43.02% of selected-sector sample (winter peak visible in monthly profile).
- **Energy (`energy_emission`):** 28.72% of selected-sector sample.
- **Industry (`industry_emission`):** 15.53% of selected-sector sample.
- **Road Transport (`road_emission`):** 11.02% of selected-sector sample.
- **Brake & Tyre Wear (`brake_tyre_emission`):** 1.71% of selected-sector sample.

Unique-cell shares (9 cells, no station double-count) are stored in `quality_report.json` under `sector_shares_pct_unique_cells`.

---

## 3. UCI Offline Merge & Correlation Analysis

### A. Join Metrics (Year 2015)
- **UCI 2015 Base Records:** 105,120 hourly observations.
- **Merged Records:** 105,120 hourly observations.
- **Row Inflation Detected?** NO (Exact 1:1 match).
- **Join Match Rate:** 100.0%.
- **Post-Join Missing Values:** 0 missing values.

### B. Correlation Analysis with Observed PM2.5

| Sector Feature | Hourly Pearson ($r$) | Hourly Spearman ($\rho$) | Monthly Agg Pearson ($r$) | Spatial $r$ (12 stations) | Spatial $r$ (9 unique cells) |
|---|---|---|---|---|---|
| `road_emission` | +0.1477 | +0.1294 | +0.4023 | +0.7019 | +0.6723 |
| `brake_tyre_emission` | +0.0570 | +0.0607 | +0.1555 | +0.6359 | +0.5920 |
| `industry_emission` | +0.0026 | +0.0036 | +0.0098 | +0.4445 | +0.4363 |
| `residential_emission` | +0.1513 | +0.1451 | +0.4122 | +0.6689 | +0.6307 |
| `energy_emission` | +0.0834 | +0.1139 | +0.2306 | +0.4906 | +0.4505 |
| `traffic_emission` | +0.1375 | +0.1266 | +0.3743 | +0.7003 | +0.6701 |

> [!NOTE]
> **Key Analytical Observations:**
> 1. **Hourly $r$ is low ($\approx 0.00$–$0.15$):** Expected when a monthly constant meets hourly PM2.5 variability. This does **not** by itself prove zero forecasting value; ablation would be required.
> 2. **Monthly $r \approx 0.40$ (Residential / Road):** Largely seasonal co-occurrence (winter heating + winter meteorology), not isolated causal attribution.
> 3. **Spatial association:** Station-level spatial $r$ for Road/Residential is high, but only **9 independent EDGAR cells** exist. Unique-grid correlations (shared stations collapsed via mean PM2.5) are the more conservative spatial estimate.
> 4. Spatial association ≠ proof that traffic emissions *cause* higher station PM2.5.

### C. EDA Figures

- `artifacts/edgar_poc/figures/edgar_spatial_emissions_2015.png` — annual traffic / industry / residential by unique 0.1° cell (no interpolation).
- `artifacts/edgar_poc/figures/edgar_sector_structure_2015.png` — monthly stacked profile + share of the five selected sectors.

---

## 4. Operational Feasibility & Risk Analysis

| Dimension | EDGAR HTAP v3 Reality | Implication |
|---|---|---|
| **Publication lag** | Inventory released years after 2015 | Cannot assume availability for real-time 2015 operational forecast replay. Fine for retrospective explanation. |
| **Temporal granularity** | Monthly totals (`ton/month`) | Acts as a slow prior; may overlap with `month_sin`/`month_cos` / meteorology. Ablation needed before claiming redundancy. |
| **Spatial granularity** | 0.1° × 0.1° (~9 × 11 km) | 12 stations → 9 cells; limited station-level discrimination. |
| **Storage** | ~5 GB raw / year | Extracted table is ~19 KB; multi-year download not justified for current EDA-only use. |
| **Leakage framing** | Post-hoc inventory | Historical analysis ≠ automatic leakage. Leakage risk appears when the experimental protocol pretends the feature was available at forecast time. |

---

## 5. Strategic Recommendations & Next Steps

1. **Do NOT download 2013/2014/2016/2017 for now:** Enough 2015 evidence to keep `EDA_ONLY` and prioritize CDC. Multi-year only if a specific spatial-trend question needs it.
2. **Preserve HistGB v2 lock:** Do not add EDGAR to `FEATURE_COLS` without a forecasting ablation.
3. **Keep spatial EDA artifacts:** Use extracted CSV + figures for reporting (urban vs suburban emission contrast, residential winter peak).
4. **Optional later:** If forecasting value is reconsidered, run a controlled ablation (with vs without EDGAR) under an explicit availability scenario — do not promote from correlation alone.
