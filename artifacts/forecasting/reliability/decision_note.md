# Forecast reliability — two visible marks, lock unchanged

**Decision:** `RELIABILITY_FLAG` for two pre-registered marks. The locked HistGB v2 forecast is unchanged.  
**Scored:** train and validation only. Test rows scored: 0.  
**Rule:** `src/forecasting/reliability.py`

A large error is an absolute locked-model error of at least 50 µg/m³. That rate is 4,096 / 276,380 on train (1.48%) and 750 / 47,338 on validation (1.58%). The 30 µg/m³ count is a sensitivity. It does not change the decision.

The bar was written before these counts. A mark has to flag at least 30 hours and at most 20% of hours, catch at least 25% of the large-error hours, and be at least twice as precise as the base rate. The same mark has to do that on train and on validation.

Every mark uses the origin hour only. The next hour's PM2.5 is not an input. The cuts are the project's existing round numbers: 20 µg/m³ for the previous-hour change, 50 µg/m³ for the gap against the median of the three nearest neighbors, the frozen causal suspect flag, and the locked episode flag.

## What clears the bar

| Mark | Split | Flagged | Flag rate | Precision | Recall | Lift | MAE flagged | MAE other |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Previous-hour change ≥ 20 | Train | 38,963 | 14.1% | 4.9% | 46.5% | 3.3 | 16.8 | 8.0 |
| Previous-hour change ≥ 20 | Val | 5,173 | 10.9% | 8.2% | 56.8% | 5.2 | 21.7 | 7.3 |
| Neighbor-median gap ≥ 50 | Train | 13,300 | 4.8% | 10.0% | 32.6% | 6.8 | 21.7 | 8.6 |
| Neighbor-median gap ≥ 50 | Val | 1,555 | 3.3% | 15.8% | 32.7% | 9.9 | 31.3 | 8.1 |

The change mark catches about half of the hours that miss by 50 µg/m³ or more. The gap mark catches about a third and is the sharper of the two. On validation the gap mark's MAE is 31.3 against 8.1 on the other hours.

Precision stays low because the event is rare. On validation, 8% of fast-change hours and 16% of large-gap hours actually miss by 50 or more. The mark says the risk is several times the usual rate. It does not say that this hour will be a large error. Most flagged hours are still ordinary.

The 30 µg/m³ sensitivity keeps the change mark and drops the gap mark. Gap recall there is 22.5% on train and 21.9% on validation, under the 25% line. The gap mark is a tail mark. It was not retuned to recover the 30 µg/m³ line.

## What does not clear it

| Mark | Why it stops |
|---|---|
| Causal suspect flag | Train 577 hours, 32 hits, recall 0.8%. Validation 66 hours, 3 hits, recall 0.4%. The lift is real and the coverage is not. |
| In-episode flag | Validation would pass (12.7% flagged, recall 51%, lift 4.1). Train flags 21.1% of hours, above the 20% cap, so the mark is not kept. The cap was not moved. |
| PM2.5 now ≥ 115 | Reference only, not a candidate. Train flags 25.2% of hours. |
| Union of the four candidate marks | Train 30.7% and validation 21.3% flagged. Recall is about 80%. Too common to be a warning. |

A union of only the two passing marks was not the pre-registered rule. It is not a third result.

## What this is

At forecast time the locked prediction can carry two extra marks: the station's PM2.5 has moved by at least 20 µg/m³ since the previous hour, or it sits at least 50 µg/m³ away from the median of its three nearest neighbors. Both are evaluation marks. Neither replaces the forecast, and neither is a new model.

Test was not used. These counts are not a claim about the second half of 2016.

## Research status

| Branch | Status |
|---|---|
| HistGB v2 | `LOCKED` — unchanged |
| Forecast reliability | `RELIABILITY_FLAG` — previous-hour change and neighbor-median gap; episode, suspect, and the four-mark union do not clear the bar |
