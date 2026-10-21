# Evaluation hygiene — labels stay inside the split, cluster fit on train

**Decision:** the locked alert classifier and the locked station clusters stay as published. The next onset experiment uses the two rules below. The published t+1 numbers are not rewritten.

**Source:** `artifacts/classification/evaluation_hygiene/hygiene_report.json`  
**Rules:** `src/classification/label_window.py`, `src/clustering/window_profiles.py`  
The fold calendar and the eight-hour confirmation cutoff were written in code before this run. 2016 H2 is scored once, on a period that earlier decisions already used.

A rerun of the published procedure reproduces the stored HistGB row exactly: test F1 0.926969, onset 304/1,000, threshold 0.50.

## Labels that cross the split

An origin keeps its split only when the label's last hour is on or before that split's end. For the current alert that hour is t+1. For the onset label it is t+8, because a 3-hour run may start at t+6.

| Rule | Train outside | Val outside | Test outside |
|---|---:|---:|---:|
| Stored t+1 | 9 / 276,380 | 12 / 47,338 | 0 / 48,781 |
| Origin + 6h | 48 | 72 | 60 |
| Origin + 8h | 61 | 96 | 83 |

Every stored target time is the origin plus one hour (372,499 matches, 0 mismatches). Test has no t+1 label past 2016-12-31 23:00 because those origins are already absent from the matrix. The 6-hour and 8-hour counts are origins that are still in the matrix and would read a later hour.

Dropping the 9 train rows and 12 validation rows, then refitting, leaves the test set at the same 48,781 rows.

| | Published | Purged, same features |
|---|---:|---:|
| Val F1 | 0.897336 | 0.897965 |
| Test F1 | 0.926969 | 0.925786 |
| Test onset | 304 / 1,000 | 299 / 1,000 |

The threshold stays 0.50. The third decimal of test F1 moves by 0.001.

## Cluster fit on the train window

Profiles rebuilt from the UCI files for March 2013–December 2016 match `station_profiles.csv` on every feature, including episode counts. Cutting a run at the window changes one station's episode hours by at most 33 and does not move a station. KMeans at the locked K=2, seed 42, reproduces the locked partition. Silhouette on {2, 3, 4} still selects 2.

The same fit on each development train window also reproduces the locked partition. No station moves.

| Fold | Train through | Val | Moved stations |
|---|---|---|---|
| 2015 | 2014-12-31 | calendar 2015 | none |
| 2015h2 | 2015-06-30 | 2015 H2 | none |
| 2016h1 | 2015-12-31 | 2016 H1 | none |

The full-period cluster is still the right EDA summary. It is also the same feature the classifier already sees, so refitting it on train does not change this model.

## `cluster_id` beside `station_key`

On the 2015 and 2015h2 folds the purged model with the locked cluster and the purged model without `cluster_id` score the same F1 and the same onset. On 2016 H1 the validation F1 values are 0.897965 and 0.897948. The second model selects threshold 0.45 instead of 0.50, and its test onset is 355/1,000 rather than 299/1,000.

That onset gap is the threshold. At one shared cut the two models agree.

| Cut | Cluster test F1 | No cluster test F1 | Cluster onset | No cluster onset | Cluster FP | No cluster FP |
|---|---:|---:|---:|---:|---:|---:|
| 0.45 | 0.926162 | 0.925887 | 353 / 1,000 | 355 / 1,000 | 992 | 999 |
| 0.50 | 0.925786 | 0.925907 | 299 / 1,000 | 295 / 1,000 | 889 | 879 |

Validation false positives at 0.50 are 751 and 754. At 0.45 they are 845 and 847. Source: `paired_thresholds.csv`.

Weather and co-pollutant gaps in the matrix were already filled with medians from the official train. The 2016 H1 fold uses that same train. The two earlier folds reuse those fills, so their absolute F1 is not a fully refit pipeline. The within-fold comparison still uses one matrix.

## What the onset experiment uses

- An origin enters a split only when hour t+8 is still inside that split. The counts to drop are the 61 / 96 / 83 rows above.
- A cluster feature, if one is used, is fit on that fold's train. On these windows the partition did not change.
- The comparison includes a model without `cluster_id`.
- Onset is compared at a shared false-alarm count. Each model's own F1 threshold is reported beside that, and is not the only comparison.

The regression lock, the alert lock, and `cluster_lock.json` were not written by this run.
