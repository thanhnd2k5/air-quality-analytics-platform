"""Where run_all.py's artifacts/ live: ARTIFACTS_DIR in Docker (mounted read-only), else the repo."""

from pathlib import Path

from app.config import get_settings


def artifacts_path() -> Path:
    configured = get_settings().artifacts_dir
    # dashboard/api/app/artifacts.py → repo root is three levels above app/.
    return Path(configured) if configured else Path(__file__).resolve().parents[3] / "artifacts"
