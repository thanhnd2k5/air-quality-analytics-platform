# Historical replay of the locked t+1 alert

**Decision:** the locked classifier is unchanged. This page only replays it.

The clock is the data watermark. A batch issues an alert only for origins that have arrived. `y_true` and `suspect_spatiotemporal` stay empty until the target hour is inside that watermark. The review flag is joined on the target hour, so it appears in the post-check and never in the feature frame passed to `predict`.

Window: 18–21 Dec 2016, six-hour batches, model `models/pm25_alert/model.joblib` at cutoff 0.50. Output: `artifacts/classification/replay/replay.json`, copied to `dashboard/web/public/replay/replay.json`. Page: `/phat-lai`.

Across the window the model issued 1,099 alerts on 1,152 station-hours. The air was already above 115 for almost the whole stretch, so model F1 and persistence F1 at the last watermark are both about 0.99. That comparison is not a new result.

The Wanshouxigong hour 2016-12-20 15:00 (PM2.5 = 3, review flag true) is attached to the origin 14:00, whose target is 15:00. Both the actual and the flag stay hidden until the 17:00 watermark, the batch that first contains 15:00.
