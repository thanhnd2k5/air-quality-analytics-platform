# MinIO bucket layout (Phase 2)

Single bucket (ARCHITECTURE §8):

```text
air-quality-lake/
├── raw/
│   ├── uci/air_quality/
│   └── openmeteo/historical_weather/
├── reference/
│   └── stations/
└── processed/
    ├── air_quality/
    └── weather/
```

Environment variable: `MINIO_BUCKET=air-quality-lake`

## Image note (2026-09)

Official `minio/minio` was removed from Docker Hub. Compose uses `coollabsio/minio`
(community build from MinIO source). Quay (`quay.io/minio/minio`) is an alternative
if authenticated pull is available.

Bootstrap prefixes after MinIO is healthy:

```powershell
bash scripts/infra/init_minio.sh
# or (PowerShell): docker cp + docker exec bootstrap_minio_inside.sh
```

