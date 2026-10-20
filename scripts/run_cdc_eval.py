#!/usr/bin/env python3
"""CLI: CDC serving demo - predict t+1 then backfill actuals / MAE.

Examples:
    py scripts/run_cdc_eval.py --watermark-start "2015-12-31 23:00:00" --watermark-end "2016-01-01 01:00:00"
    py scripts/run_cdc_eval.py --mae-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.forecasting.cdc_serve import (  # noqa: E402
    compute_mae_snapshot,
    ensure_prediction_log,
    run_cdc_eval,
)
from src.ingestion.db_client import DEFAULT_WATERMARK  # noqa: E402
from src.staging.load import connect  # noqa: E402
from src.staging.operational_db_load import staging_operational_watermark  # noqa: E402


def emit(payload: dict, *, stream=sys.stdout) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2, default=str), file=stream)


def main() -> int:
    parser = argparse.ArgumentParser(description="CDC serve + continuous eval")
    parser.add_argument(
        "--watermark-start",
        default=None,
        help=(
            "Exclusive lower bound for new origins "
            f"(default: {DEFAULT_WATERMARK}; pass explicitly for narrow windows)"
        ),
    )
    parser.add_argument(
        "--watermark-end",
        default=None,
        help="Inclusive upper bound (default: staging operational MAX)",
    )
    parser.add_argument("--eval-batch-id", default=None, help="Optional batch id label")
    parser.add_argument(
        "--mae-only",
        action="store_true",
        help="Only print / refresh MAE artifact from existing prediction_log",
    )
    args = parser.parse_args()

    try:
        if args.mae_only:
            conn = connect()
            try:
                ensure_prediction_log(conn)
                snap = compute_mae_snapshot(conn)
                from src.forecasting.cdc_serve import write_mae_artifact

                path = write_mae_artifact(snap)
            finally:
                conn.close()
            emit({"status": "mae_only_ok", "snapshot": snap, "artifact_path": str(path)})
            return 0

        wm_end = args.watermark_end or staging_operational_watermark()
        wm_start = args.watermark_start
        if wm_start is None:
            # First hour of operational channel unless caller sets start.
            wm_start = DEFAULT_WATERMARK

        result = run_cdc_eval(
            watermark_start=wm_start,
            watermark_end=wm_end,
            eval_batch_id=args.eval_batch_id,
        )
        emit(result.to_dict())
        return 0 if result.status in {"ok", "empty_origins"} else 1
    except Exception as exc:  # noqa: BLE001
        emit({"status": "failed", "message": str(exc)}, stream=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
