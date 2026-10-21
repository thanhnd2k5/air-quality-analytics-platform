# Six-hour episode onset — spatial features clear the bar, the t+1 lock stays

**Decision:** keep the locked t+1 alert classifier. For this separate question, the four M2 neighbor features clear the pre-registered bar against the level rule. A local classifier without those features does not. M2 is not promoted into the regression lock.

**Question:** PM2.5(t) is observed and below 115. Does a run of at least three hours at or above 115 start in t+1..t+6?  
**Rule:** `src/classification/onset.py`  
**Scores:** `artifacts/classification/onset_6h/onset_metrics.csv`

An origin is kept only when clock hours t+1 through t+8 exist and t+8 is still inside its split. A null PM2.5 breaks a run. The population is hours that are clean now, so persistence alerts never and its episode recall is 0.

The comparison ceiling was fixed first: at most 0.5 false-alarm origins per eligible station-day on validation. Each score picks the cut with the highest episode recall that stays under that ceiling. A model clears the bar when its validation episode recall is at least 0.05 above the chosen baseline on two of the three development folds. 2016 H2 uses the cuts chosen on 2016 H1. That half-year was already used for other decisions.

Eligible origins on the published split: train 206,833 (20,738 positive hours), validation 39,779 (2,662), test 37,135 (3,467). The denominators below are episodes, not hours.

## The baseline is the current level

On every fold the level rule beat the six-hour trend score. The level cut is the same on all three: alert when PM2.5(t) is at least 105. Trend recall on validation is 0.390, 0.549 and 0.396.

| Fold | Episodes | Level recall | Level FA/day | Local recall | Spatial recall | Spatial FA/day |
|---|---:|---:|---:|---:|---:|---:|
| 2015 | 1,414 | 0.638 | 0.324 | 0.624 | 0.686 | 0.471 |
| 2015 H2 | 554 | 0.619 | 0.309 | 0.612 | 0.675 | 0.416 |
| 2016 H1 | 550 | 0.627 | 0.344 | 0.593 | 0.707 | 0.496 |

Local HistGB, with `cluster_id` and without it, stays under the level rule. The 2015 fold gives those two the same recall, 0.624. Spatial clears the 0.05 margin on 2015 H2 (+0.056) and 2016 H1 (+0.080). The 2015 fold is short of the margin (+0.048). Two folds are enough for the bar. On those validation folds spatial also uses more of the 0.5 allowance than the level rule.

## 2016 H2, cuts taken from 2016 H1

| | Level, cut 105 | Local, cut 0.55 | Spatial, cut 0.50 |
|---|---:|---:|---:|
| Episodes detected | 468 / 730 | 429 / 730 | 506 / 730 |
| Episode recall | 0.641 | 0.588 | 0.693 |
| False alarms per station-day | 0.436 | 0.252 | 0.409 |
| Origin precision | 0.460 | 0.646 | 0.606 |
| Median lead of detected episodes | 1 h | 2 h | 3 h |
| Share of detected episodes with lead ≥ 3 h | 0.316 | 0.441 | 0.506 |
| Median alerts on a detected episode | 1 | 2 | 2 |

Spatial is 0.052 above the level rule, and its false-alarm rate on this half-year is lower than the level rule's. The local model is not. Median lead moves from one hour to three. Spatial sends a second alert on the episodes it catches.

The gain is not uniform. On this half-year the level rule detects a larger share of episodes that last 3–5 hours (0.643 against 0.562) and a larger share of summer episodes (0.718 against 0.612). Spatial detects a larger share of episodes that last 12 hours or more (0.829 against 0.632) and a larger share of autumn (0.734 against 0.682) and winter (0.695 against 0.471). Level stays ahead at Gucheng, Changping and Huairou. The episode list is `confirmation_episodes.csv`.

A second ceiling of 1.0 false alarm per station-day was scored and was not the decision. Spatial's recall stays higher there as well, and it spends more of that larger allowance.

## What this does not change

The regression lock, the t+1 alert lock, and the cluster lock were not written. The level rule remains the right simple baseline for a station that is already near 105. Neighbor features are the part that moves episode recall and lead time under the 0.5 ceiling. `cluster_id` is not.
