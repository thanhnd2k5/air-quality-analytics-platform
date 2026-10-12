#!/usr/bin/env python3
"""Promote HistGB v2 → production lock / model / predictions, then reload mart (P10d).

Does NOT retrain. Copies Vòng A artifacts onto production paths, then runs
scripts/run_forecasting_phase10d.py.

Example:
    py -3 scripts/promote_forecast_v2.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "forecasting"
MODELS_V1 = ROOT / "models" / "pm25_forecast"
MODELS_V2 = ROOT / "models" / "pm25_forecast_v2"
BACKUP = OUT / "promote_backup_v1"


def _copy_file(src: Path, dst: Path) -> None:
    if not src.is_file():
        raise FileNotFoundError(f"Missing required source: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _backup_v1() -> list[str]:
    BACKUP.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    pairs = [
        (OUT / "model_lock.json", BACKUP / "model_lock.json"),
        (OUT / "predictions_locked.parquet", BACKUP / "predictions_locked.parquet"),
        (OUT / "model_metrics.csv", BACKUP / "model_metrics.csv"),
        (MODELS_V1 / "model.joblib", BACKUP / "model.joblib"),
        (MODELS_V1 / "metadata.json", BACKUP / "metadata.json"),
    ]
    for src, dst in pairs:
        if src.is_file():
            shutil.copy2(src, dst)
            saved.append(str(src.relative_to(ROOT)).replace("\\", "/"))
    return saved


def _build_production_lock(v2: dict, *, promoted_at: str) -> dict:
    lock = {
        "ok": True,
        "phase": "Promote_VongA",
        "variant": "v2",
        "locked_model": v2["locked_model"],
        "lock_rule": v2.get("lock_rule"),
        "random_state": v2.get("random_state"),
        "sample_weight": v2.get("sample_weight"),
        "beats_persistence_on_test": v2.get("beats_persistence_on_test"),
        "val_mae": v2.get("val_mae"),
        "test_mae": v2.get("test_mae"),
        "comparison_vs_v1": v2.get("comparison_vs_v1"),
        "metrics_table": "artifacts/forecasting/model_metrics.csv",
        "predictions": "artifacts/forecasting/predictions_locked.parquet",
        "model_artifact": "models/pm25_forecast/model.joblib",
        "metadata": "models/pm25_forecast/metadata.json",
        "split": v2.get("split"),
        "feature_cols": v2.get("feature_cols"),
        "target_col": v2.get("target_col"),
        "per_model_metrics": v2.get("per_model_metrics"),
        "promoted_from": {
            "model_lock_v2": "artifacts/forecasting/model_lock_v2.json",
            "predictions_v2": "artifacts/forecasting/predictions_v2.parquet",
            "model_dir": "models/pm25_forecast_v2",
        },
        "promoted_at": promoted_at,
        "created_at": v2.get("created_at"),
        "note": "Production lock after Vòng A promote; v1 backup under artifacts/forecasting/promote_backup_v1/",
    }
    return lock


def promote_files() -> dict:
    v2_lock_path = OUT / "model_lock_v2.json"
    if not v2_lock_path.is_file():
        raise FileNotFoundError("Missing model_lock_v2.json — run Vòng A first")
    v2 = json.loads(v2_lock_path.read_text(encoding="utf-8"))
    if not v2.get("ok"):
        raise RuntimeError(f"model_lock_v2 not ok: {v2}")

    backed_up = _backup_v1()
    promoted_at = datetime.now(timezone.utc).isoformat()

    _copy_file(OUT / "predictions_v2.parquet", OUT / "predictions_locked.parquet")
    _copy_file(OUT / "model_metrics_v2.csv", OUT / "model_metrics.csv")
    _copy_file(MODELS_V2 / "model.joblib", MODELS_V1 / "model.joblib")

    meta = json.loads((MODELS_V2 / "metadata.json").read_text(encoding="utf-8"))
    meta["promoted_at"] = promoted_at
    meta["note"] = "Promoted to production from Vòng A HistGB v2"
    meta.pop("variant", None)
    (MODELS_V1 / "metadata.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )

    lock = _build_production_lock(v2, promoted_at=promoted_at)
    (OUT / "model_lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")

    # Keep experimental v2 lock annotated
    v2["promoted_to_production"] = True
    v2["promoted_at"] = promoted_at
    v2_lock_path.write_text(json.dumps(v2, indent=2) + "\n", encoding="utf-8")

    return {
        "backed_up": backed_up,
        "promoted_at": promoted_at,
        "test_mae": lock["test_mae"],
        "n_features": len(lock.get("feature_cols") or []),
    }


def main() -> int:
    try:
        info = promote_files()
        print(json.dumps({"step": "promote_files", "ok": True, **info}, ensure_ascii=True))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "step": "promote_files", "error": str(exc)}, ensure_ascii=True))
        return 1

    rc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_forecasting_phase10d.py")],
        cwd=str(ROOT),
        check=False,
    )
    ok = rc.returncode == 0
    print(
        json.dumps(
            {
                "ok": ok,
                "step": "mart_reload_p10d",
                "returncode": rc.returncode,
                "promote": info,
            },
            ensure_ascii=True,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
