#!/usr/bin/env bash
# Bootstrap MinIO bucket + prefix markers (P2-14, P2-15).
# Usage (Git Bash / WSL after minio is healthy):
#   bash scripts/infra/init_minio.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONTAINER="${MINIO_CONTAINER:-air_quality_minio}"
BUCKET="${MINIO_BUCKET:-air-quality-lake}"

docker cp "${ROOT_DIR}/scripts/infra/bootstrap_minio_inside.sh" \
  "${CONTAINER}:/tmp/bootstrap_minio_inside.sh"
docker exec -e "MINIO_BUCKET=${BUCKET}" \
  "${CONTAINER}" sh /tmp/bootstrap_minio_inside.sh
