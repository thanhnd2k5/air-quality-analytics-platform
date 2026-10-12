"""PM2.5 exceedance alert classification (main data-mining task of the project).

Business question: should the monitoring centre raise a "limit outdoor activity"
alert for the next hour at a given station? Positive class = PM2.5(t+h) ≥ 115 µg/m³
(the episode threshold locked in Phase 8c).

Reuses the Vòng A feature matrix (``artifacts/forecasting/feature_matrix_v2.parquet``)
and the chronological train / val / test split locked in Phase 10.
"""
