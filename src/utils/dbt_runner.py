"""Run dbt the repo-standard way: the dbt-postgres 1.9 Docker image on air-quality-network.

Falls back to a local ``dbt`` executable when Docker is not installed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DBT_IMAGE = "ghcr.io/dbt-labs/dbt-postgres:1.9.0"
NETWORK = "air-quality-network"


def dbt_command(args: list[str], *, docker: bool = True) -> list[str]:
    if docker:
        return [
            "docker", "run", "--rm",
            "--network", NETWORK,
            "--env-file", str(ROOT / ".env"),
            "-e", "POSTGRES_HOST=postgres",
            "-e", "POSTGRES_PORT=5432",
            "-e", "DBT_SEND_ANONYMOUS_USAGE_STATS=false",
            "-e", "DO_NOT_TRACK=1",
            # The bind-mounted target/partial_parse.msgpack can go stale when files are
            # edited from Windows → tests silently disappear. A full parse takes seconds.
            "-e", "DBT_PARTIAL_PARSE=false",
            "-v", f"{ROOT / 'dbt'}:/dbt",
            DBT_IMAGE,
            *args,
            "--project-dir", "/dbt/air_quality_dbt",
            "--profiles-dir", "/dbt",
        ]
    return [
        "dbt", *args,
        "--project-dir", str(ROOT / "dbt" / "air_quality_dbt"),
        "--profiles-dir", str(ROOT / "dbt"),
    ]


def run_dbt(args: list[str]) -> int:
    """Return dbt's exit code (0 = success)."""
    try:
        proc = subprocess.run(dbt_command(args), cwd=str(ROOT), check=False)
    except FileNotFoundError:
        proc = subprocess.run(dbt_command(args, docker=False), cwd=str(ROOT), check=False)
    return int(proc.returncode)
