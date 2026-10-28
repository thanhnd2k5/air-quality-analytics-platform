#!/usr/bin/env python3
"""Rebuild the whole project from scratch with ONE command.

    python scripts/run_all.py

Raw UCI download → MinIO lake → processed Parquet → Open-Meteo enrichment → PostgreSQL
staging → dbt warehouse (star schema + cuboids + data cube) → feature matrix rebuilt from
the warehouse → alert classification trained + evaluated (main mining task) → mart checks
→ OLAP checks + executed OLAP notebook → dashboard API.

Supporting analyses (station clustering, PM2.5 regression) are locked artifacts in the
repo: by default they are loaded into the marts and verified, not re-fitted, because a
re-fit rewrites lock metadata (timestamps, curated labels). Re-fitting gives the same
numbers; use --retrain-all to do it anyway.

Every step is idempotent (re-running skips work already done). Prerequisites: Docker
(Desktop) running, Python 3.10+ with `pip install -r requirements.txt`, internet access
for the first run (UCI zip + Open-Meteo archive API).

Options:
    --list                 show the steps and exit
    --only a,b             run only these steps
    --from STEP            start at STEP (earlier steps assumed done)
    --skip a,b             skip these steps
    --retrain-all          also re-fit clustering and re-train the PM2.5 regression
                           (overwrites their lock files; review with git diff)
    --with-airflow         also start Airflow webserver + scheduler
    --with-eda             also re-run the Phase 8 EDA batch scripts
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PY = sys.executable
LOG_DIR = ROOT / "artifacts" / "run_all" / "logs"
SUMMARY = ROOT / "artifacts" / "run_all" / "run_summary.json"
# Only written by full runs (no --only/--from/--skip) so partial re-runs keep the evidence.
SUMMARY_FULL = ROOT / "artifacts" / "run_all" / "run_summary_full.json"
REQUIRED_MODULES = ("pandas", "pyarrow", "sklearn", "psycopg2", "minio", "dotenv", "matplotlib", "nbclient")
PLACEHOLDERS = {
    "POSTGRES_PASSWORD": "postgres_password_here",
    "MINIO_ROOT_PASSWORD": "miniopassword_here",
    "MINIO_SECRET_KEY": "miniopassword_here",
    "_AIRFLOW_WWW_USER_PASSWORD": "admin_password_here",
}


class StepError(RuntimeError):
    pass


@dataclass
class Ctx:
    args: argparse.Namespace
    commands: list[dict] = field(default_factory=list)


@dataclass
class Step:
    name: str
    title: str
    fn: Callable[[Ctx], None]


# --------------------------------------------------------------------------- helpers


def _log(msg: str) -> None:
    print(msg, flush=True)


def run(ctx: Ctx, step: str, cmd: list[str], *, label: str | None = None, env: dict | None = None) -> None:
    """Run a command, stream it to a log file, fail the step on non-zero exit."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{step}.log"
    shown = label or " ".join(Path(c).name if i == 0 else c for i, c in enumerate(cmd))
    started = time.time()
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n$ {' '.join(cmd)}\n")
        log.flush()
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            stdout=log,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", **(env or {})},
            check=False,
        )
    secs = time.time() - started
    ctx.commands.append({"step": step, "cmd": shown, "returncode": proc.returncode, "seconds": round(secs, 1)})
    status = "ok" if proc.returncode == 0 else f"FAILED (exit {proc.returncode})"
    _log(f"    {status:<8} {shown}  [{secs:.0f}s]")
    if proc.returncode != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]
        _log("      --- last log lines (" + str(log_path.relative_to(ROOT)) + ") ---")
        for line in tail:
            _log("      " + line)
        raise StepError(f"{shown} exited with {proc.returncode}")


def script(ctx: Ctx, step: str, name: str, *args: str) -> None:
    run(ctx, step, [PY, str(ROOT / "scripts" / name), *args], label=f"python scripts/{name} {' '.join(args)}".strip())


def dbt(ctx: Ctx, step: str, *args: str) -> None:
    from src.utils.dbt_runner import dbt_command

    use_docker = shutil.which("docker") is not None
    run(ctx, step, dbt_command(list(args), docker=use_docker), label=f"dbt {' '.join(args)}")


def compose(ctx: Ctx, step: str, *args: str) -> None:
    run(ctx, step, ["docker", "compose", *args], label=f"docker compose {' '.join(args)}")


def wait_healthy(container: str, timeout: int = 240) -> None:
    deadline = time.time() + timeout
    status = "?"
    while time.time() < deadline:
        out = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Health.Status}}", container],
            capture_output=True, text=True, check=False,
        )
        status = out.stdout.strip()
        if status == "healthy":
            return
        time.sleep(3)
    raise StepError(f"{container} not healthy after {timeout}s (last status: {status})")


def load_env() -> None:
    from dotenv import dotenv_values

    for key, value in dotenv_values(ROOT / ".env").items():
        if value is not None:
            os.environ.setdefault(key, value)


# --------------------------------------------------------------------------- steps


def step_prereq(ctx: Ctx) -> None:
    missing = []
    for mod in REQUIRED_MODULES:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        raise StepError(f"missing Python packages {missing} — run: pip install -r requirements.txt")
    if shutil.which("docker") is None:
        raise StepError("docker not found — install/start Docker Desktop")
    info = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True)
    if info.returncode != 0:
        raise StepError("Docker daemon not reachable — start Docker Desktop and retry")
    _log(f"    ok       Python {sys.version.split()[0]}, Docker {info.stdout.strip()}")

    env_path = ROOT / ".env"
    if not env_path.exists():
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        pg, minio, admin = secrets.token_hex(8), secrets.token_hex(12), secrets.token_hex(8)
        values = {"POSTGRES_PASSWORD": pg, "MINIO_ROOT_PASSWORD": minio, "MINIO_SECRET_KEY": minio,
                  "_AIRFLOW_WWW_USER_PASSWORD": admin}
        lines = []
        for line in text.splitlines():
            key = line.split("=", 1)[0]
            if key in values and line.strip() == f"{key}={PLACEHOLDERS[key]}":
                line = f"{key}={values[key]}"
            lines.append(line)
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _log("    created  .env from .env.example with random local passwords (not committed)")
    load_env()
    if os.environ.get("MINIO_SECRET_KEY") != os.environ.get("MINIO_ROOT_PASSWORD"):
        raise StepError(".env: MINIO_SECRET_KEY must equal MINIO_ROOT_PASSWORD (SignatureDoesNotMatch otherwise)")


def step_download(ctx: Ctx) -> None:
    script(ctx, "download", "download_uci_dataset.py")


def step_infra(ctx: Ctx) -> None:
    services = ["postgres", "minio"]
    if ctx.args.with_airflow:
        compose(ctx, "infra", "up", "airflow-init")
        services += ["airflow-webserver", "airflow-scheduler"]
    try:
        compose(ctx, "infra", "up", "-d", *services)
    except StepError as exc:
        log = (LOG_DIR / "infra.log").read_text(encoding="utf-8", errors="replace")
        if "address already in use" in log or "port is already allocated" in log:
            raise StepError(
                "a host port is taken by another program — change POSTGRES_PORT / MINIO_PORT / "
                "MINIO_CONSOLE_PORT (and MINIO_ENDPOINT) in .env, then re-run"
            ) from exc
        raise
    wait_healthy("air_quality_postgres")
    wait_healthy("air_quality_minio")
    from src.utils.minio_client import ensure_bucket, get_minio_client

    created = ensure_bucket(get_minio_client())
    _log(f"    ok       postgres + minio healthy; bucket {'created' if created else 'exists'}")


def step_lake(ctx: Ctx) -> None:
    script(ctx, "lake", "ingest_uci_station.py", "--all")
    script(ctx, "lake", "process_uci_station.py", "--all")


def step_openmeteo(ctx: Ctx) -> None:
    script(ctx, "openmeteo", "ingest_openmeteo_station.py", "--all")
    script(ctx, "openmeteo", "process_openmeteo_station.py", "--all")


def step_staging(ctx: Ctx) -> None:
    script(ctx, "staging", "load_staging.py", "--all")
    script(ctx, "staging", "verify_staging_load.py", "--all")


def step_warehouse(ctx: Ctx) -> None:
    dbt(ctx, "warehouse", "seed", "--full-refresh")
    # Prediction marts read staging tables that only exist after the mining steps.
    dbt(ctx, "warehouse", "run", "--exclude", "mart_pm25_predictions", "mart_pm25_alerts")


def step_clustering(ctx: Ctx) -> None:
    if not ctx.args.retrain_all:
        _log("    locked   station clusters = dbt seed station_cluster_assignment (checked in 'checks')")
        return
    script(ctx, "clustering", "run_clustering_phase9b.py")
    script(ctx, "clustering", "run_clustering_phase9.py")
    script(ctx, "clustering", "clustering_k_sweep.py")  # K = 2…11 for the dashboard chart (display only)


def step_forecast(ctx: Ctx) -> None:
    script(ctx, "forecast", "run_forecasting_v2a.py")  # feature matrix rebuilt from the warehouse
    if not ctx.args.retrain_all:
        script(ctx, "forecast", "run_forecasting_phase10d.py")  # locked predictions → mart + test
        return
    script(ctx, "forecast", "run_forecasting_v2b.py")
    script(ctx, "forecast", "promote_forecast_v2.py", "--no-backup")  # → production lock + mart reload


def step_classify(ctx: Ctx) -> None:
    script(ctx, "classify", "run_classification.py")
    run(
        ctx, "classify",
        [PY, "-c", "from src.classification.persist import load_alerts_to_staging as f; print(f())"],
        label="load alerts → staging.pm25_alert_predictions_raw",
    )
    dbt(ctx, "classify", "run", "--select", "mart_pm25_alerts")


def step_dbt_test(ctx: Ctx) -> None:
    dbt(ctx, "dbt_test", "test")


def step_checks(ctx: Ctx) -> None:
    for name in ("check_mart_cluster.py", "check_mart_episodes.py", "check_mart_predictions.py",
                 "check_mart_alerts.py"):
        script(ctx, "checks", name)
    if ctx.args.with_eda:
        script(ctx, "checks", "run_eda_phase8b.py")
        script(ctx, "checks", "run_eda_phase8c.py")


def step_olap(ctx: Ctx) -> None:
    script(ctx, "olap", "run_olap_checks.py")
    script(ctx, "olap", "build_olap_notebook.py", "--execute")


def step_dashboard(ctx: Ctx) -> None:
    try:
        compose(ctx, "dashboard", "up", "-d", "--build", "dashboard-api")
    except StepError:
        # pip inside `docker build` sometimes hits transient DNS errors → retry once.
        _log("    retry    image build (network hiccups during pip install are common)")
        compose(ctx, "dashboard", "up", "-d", "--build", "dashboard-api")
    port = os.environ.get("DASHBOARD_API_PORT", "8100")
    url = f"http://127.0.0.1:{port}/api/health/db"
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 — localhost
                if resp.status == 200:
                    _log(f"    ok       dashboard API {url}")
                    _log("             UI: cd dashboard/web && npm install && npm run dev  (→ http://localhost:5180)")
                    return
        except Exception:  # noqa: BLE001 — still starting
            time.sleep(3)
    raise StepError(f"dashboard API not answering on {url}")


STEPS = [
    Step("prereq", "Kiểm tra Python/Docker, tạo .env nếu thiếu", step_prereq),
    Step("download", "Tải bộ dữ liệu UCI #501 (12 CSV)", step_download),
    Step("infra", "Docker: PostgreSQL + MinIO (+ Airflow), tạo bucket", step_infra),
    Step("lake", "CSV → MinIO raw → Parquet processed", step_lake),
    Step("openmeteo", "Open-Meteo API → raw → processed", step_openmeteo),
    Step("staging", "Parquet → PostgreSQL staging + đối soát", step_staging),
    Step("warehouse", "dbt seed + run: lược đồ sao, khối con, data cube", step_warehouse),
    Step("clustering", "Phân cụm trạm (bổ trợ, đã khoá)", step_clustering),
    Step("forecast", "Ma trận đặc trưng từ kho + nạp dự báo hồi quy (bổ trợ)", step_forecast),
    Step("classify", "Phân loại cảnh báo vượt ngưỡng (bài toán khai phá chính)", step_classify),
    Step("dbt_test", "dbt test toàn bộ", step_dbt_test),
    Step("checks", "Đối chiếu mart với artifact đã khoá", step_checks),
    Step("olap", "5 thao tác OLAP + kiểm chứng khối + chạy notebook", step_olap),
    Step("dashboard", "Dashboard API (FastAPI) trong Docker", step_dashboard),
]


def select_steps(args: argparse.Namespace) -> list[Step]:
    names = [s.name for s in STEPS]
    for opt in ("only", "skip"):
        for n in getattr(args, opt) or []:
            if n not in names:
                raise SystemExit(f"unknown step '{n}' — choose from {names}")
    if args.from_step and args.from_step not in names:
        raise SystemExit(f"unknown step '{args.from_step}' — choose from {names}")
    chosen = STEPS
    if args.from_step:
        chosen = STEPS[names.index(args.from_step):]
    if args.only:
        chosen = [s for s in STEPS if s.name in args.only]
    chosen = [s for s in chosen if s.name not in (args.skip or [])]
    # .env must be loaded for every run, even a partial one.
    if chosen and chosen[0].name != "prereq":
        chosen = [STEPS[0], *chosen]
    return chosen


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild the air-quality project end to end")
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()]  # noqa: E731
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--only", type=split)
    parser.add_argument("--skip", type=split)
    parser.add_argument("--from", dest="from_step")
    parser.add_argument("--retrain-all", action="store_true")
    parser.add_argument("--with-airflow", action="store_true")
    parser.add_argument("--with-eda", action="store_true")
    args = parser.parse_args()
    # Windows consoles default to cp1252; step titles are Vietnamese.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    if args.list:
        for i, s in enumerate(STEPS, 1):
            print(f"{i:2d}. {s.name:<10} {s.title}")
        return 0

    ctx = Ctx(args=args)
    steps = select_steps(args)
    started = time.time()
    results = []
    ok = True
    for i, step in enumerate(steps, 1):
        _log(f"[{i}/{len(steps)}] {step.name} — {step.title}")
        (LOG_DIR / f"{step.name}.log").unlink(missing_ok=True)
        t0 = time.time()
        try:
            step.fn(ctx)
            results.append({"step": step.name, "status": "ok", "seconds": round(time.time() - t0, 1)})
        except StepError as exc:
            results.append({"step": step.name, "status": "failed", "error": str(exc),
                            "seconds": round(time.time() - t0, 1)})
            _log(f"    ✗ {exc}")
            ok = False
            break

    summary = {
        "ok": ok,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "total_seconds": round(time.time() - started, 1),
        "options": {k: v for k, v in vars(args).items() if k != "list"},
        "steps": results,
        "commands": ctx.commands,
    }
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not (args.only or args.from_step or args.skip):
        SUMMARY_FULL.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    mins = summary["total_seconds"] / 60
    _log(("✓ DONE" if ok else "✗ STOPPED") + f" in {mins:.1f} min — summary: {SUMMARY.relative_to(ROOT)}")
    if not ok:
        _log("  Fix the problem, then resume with: python scripts/run_all.py --from " + results[-1]["step"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
