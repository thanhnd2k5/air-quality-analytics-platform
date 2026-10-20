# Robust spatial M5 — branch closed, keep M2

**Decision:** `KEEP_M2`  
**Branch:** closed. One median POC. No further aggregator on this dataset.  
**Lock:** unchanged. HistGB v2 stays `LOCKED`. M2 stays `PROMOTE_CANDIDATE` and is not promoted into the lock. M5 is not a replacement candidate.

Median can limit the pull of one anomalous neighbor. That benefit is not stable enough to replace IDW. Validation and test disagree, and the validation slice is below the pre-registered floor of 30 origin hours.

M0 and M2 reproduce the spatial ablation exactly (test MAE 8.872 and 8.574; winter-test 14.080 and 13.680; gap 0). Same 372,499 rows, same HistGB settings, same sample weights. M5 swaps only the four IDW spatial columns for the median of the same three neighbors at t, t−1h and t−3h. `spatial_gradient_median` is own PM2.5(t) minus that median. The suspect flag is applied after the forecast. It is not a feature, and it does not change a stored PM2.5.

A median row is null only when all three neighbors are null, the same hours as the IDW mean (553 hours at t). One finite neighbor is used as itself (6,363). Two finite neighbors use their midpoint (52,252). Three are present on 313,331 hours.

Cuts below were written down before the fit. 2016-12-20 was not one of them.

## Final comparison

M5 stays better than the locked baseline and a little worse than M2.

| Slice | M0 | M2 | M5 | M5−M0 | M5−M2 |
|---|---:|---:|---:|---:|---:|
| Val | 8.886 | 8.507 | 8.526 | −0.359 | +0.019 |
| Test | 8.872 | 8.574 | 8.604 | −0.268 | +0.031 |
| Winter val | 8.992 | 8.509 | 8.519 | −0.472 | +0.011 |
| Winter test | 14.080 | 13.680 | 13.741 | −0.339 | +0.060 |
| Heating test | 12.940 | 12.515 | 12.588 | −0.352 | +0.072 |
| High-PM val (≥115) | 18.108 | 17.191 | 17.304 | −0.803 | +0.113 |
| High-PM test | 15.367 | 14.822 | 14.894 | −0.474 | +0.071 |
| Rapid rise test | 29.336 | 27.407 | 27.548 | −1.789 | +0.140 |
| Rapid drop test | 32.546 | 30.592 | 30.909 | −1.638 | +0.317 |

M5 clears the old promote gate against M0 (val and test ≤ −0.15, winter and high-PM not worse by more than 0.10, 11 of 12 stations). That gate is not the decision. Against M2 the giveback is small on average and larger when the level is moving quickly. Eleven stations still beat M0. Shunyi is the one that does not (+0.065). The largest giveback versus M2 is Guanyuan, +0.094.

## Suspect-neighbor hours

An origin hour is in the suspect slice when at least one of the three neighbors is `suspect_spatiotemporal` at t, t−1h or t−3h. Negative ΔMAE means M5 is better than M2.

| Slice | Hours | ΔMAE M5−M2 |
|---|---:|---:|
| Validation | 14 | +2.60 |
| Test | 60 | −1.08 |
| Test, 2016-12-20 removed | 51 | −1.01 |

The test gain of about 1 µg/m³ remains after 20 December is removed, so that afternoon is not the whole test result. Validation, the period that was not used to inspect this day, goes the other way: M2 MAE 9.24, M5 11.84, on 14 hours in three small clusters (2 Mar, 5 Apr, 10 Jun 2016). Those levels are ordinary. The IDW mean was the better summary there.

Fourteen hours cannot prove that median has no value, and they are below the floor of 30. They are enough to refuse a claim that the robustness benefit is stable.

On the 60 test hours, the center of the absolute-error distribution barely moves (P50 16.3 → 16.1). P99 falls from 171 to 158 and is still above M0’s 137. P90 rises from 84 to 91. The mean improvement is a thinner upper tail, not a better typical hour.

Unflagged hours give back 0.03 µg/m³ (test ΔMAE +0.032 on 48,721 hours; ordinary unflagged +0.021 on 46,362). Their P50 and P99 stay on top of M2. Hours with a large local-neighbor gap and no flag (|own − median| ≥ 50) are 0.25 µg/m³ worse on test (n = 2,359) and slightly better on validation (−0.068, n = 1,554). Median does not treat every large gap as a bad observation, and it also does not help those hours.

## The limit that closes the branch

Two consecutive Gucheng origin hours, diagnostic only. The formula was not adjusted to this day.

| Origin | Three neighbor PM2.5 | IDW | Median | Flag |
|---|---|---:|---:|---|
| 2016-12-20 15:00 | Wanliu 338, Guanyuan 420, Wanshouxigong 3 | 266 | 338 | Wanshouxigong flagged |
| 2016-12-20 16:00 | Wanliu 204, Guanyuan 508, Wanshouxigong 170 | 295 | 204 | none of the three flagged |

At 15:00 the next hour’s actual is 634. Absolute error is 132 (M0), 212 (M2), 175 (M5). Median does the job it was built for: it reduces the pull of the single 3. All three forecasts stay low. 338 and 420 are the other recorded levels, so the forecast is still 174 µg/m³ low.

At 16:00 the same definition cuts the other way. The three neighbors are unflagged and genuinely far apart. Absolute error goes from 120 (M2) to 147 (M5). A lone spike is what the median is for. A real spread across the three neighbors is not.

An aggregator that resists an outlier is not automatically the aggregator that should be used when the spatial field really disagrees. Spatial aggregation has to keep information about how pollution is distributed, not only resist a bad point.

The Gucheng run 12:00–20:00 (9 target hours ≥ 500) is MAE 47.4 / 83.3 / 75.9. The city event 09:00–20:00 across Changping, Guanyuan, Gucheng and Wanliu (16 station-hours) is 52.6 / 90.1 / 76.7. M5 gives back some of M2’s damage and stays well above M0.

## Extreme episodes

The ≥500 tail stays a spatial-model problem. Median trims it slightly versus M2 and leaves it worse than M0.

Test hours with actual PM2.5 ≥ 500: n = 77, not 77 independent events. MAE is 43.44 (M0), 50.81 (M2), 49.82 (M5). Validation’s 73 hours go the other way and by more (M5 −4.70 versus M2), on a small set.

Station-episodes on the test tail: M5 better than M2 on 14 of 24, worse on 10. Better than M0 on 11, worse on 13. City events, one run of clock hours no matter how many stations are in it: 5 of 9 better than M2, 4 worse; 2 of 9 better than M0, 7 worse. The largest extra loss versus M2 is not 20 December. It is Gucheng 21 Dec 15:00–16:00 (MAE 38.0 → 56.4, two hours). The largest remaining loss versus M0 is still on 20 December.

This is why M2 remains the best candidate and still does not replace the lock. Average MAE improves. A local extreme that the neighbors do not share gets worse, and that safety gap is still open.

## Raw values stay as published

Wanshouxigong 2016-12-20 15:00 is 3 in the UCI file and 3 in the locked matrix. That equality was checked. It was not shown to be a sensor fault.

Two rules stay in force:

- Raw PM2.5 is preserved.
- `suspect_spatiotemporal` is a quality-review flag. It is not a finding that the row is wrong, and it is not a license to overwrite or drop the row.

The current quality rules do not have enough evidence to drive automatic exclusion in serving. The flag uses t+1, so it is offline. The causal version of the same cut is wide enough to mark real drops. Neither belongs in an automatic filter.

## What is not next

Trimmed mean, winsorized mean, and any blend of those with IDW are not to be fit on this test set. The median POC already spent the comparison this design allowed. Another formula aimed at 20 December would be a second look at the same evidence. A later spatial test needs a later time period.

Spatial variants on this dataset stop here. The research record is the contribution: spatial features improve average MAE; some local episodes are hurt by neighbor information; a few anomalous observations can amplify that; median softens some of those exceptions and gives up useful spatial disagreement; none of that is stable enough to replace the locked model.

## Research status

| Branch | Status |
|---|---|
| HistGB v2 | `LOCKED` |
| PBL | `CLOSE_BRANCH` |
| EDGAR | `EDA_ONLY` |
| Calendar | `EDA_ONLY` |
| Spatial M2 | `PROMOTE_CANDIDATE` — best candidate; lock not updated, extreme-episode safety still open |
| Upwind M4 | `KEEP_M2` |
| Robust spatial M5 | `KEEP_M2` — branch closed |

## Open direction, not started

Forecast reliability: an evaluation layer outside the current model, not an M6. The question is whether large errors can be recognized at forecast time from conditions already visible then — a fast rise or drop at the target station, a large gap between the target and its neighbors, an input that looks anomalous, a very high PM2.5 episode. Any such study uses train and validation. Test has already been read often enough that it is not an independent check for a new method.
