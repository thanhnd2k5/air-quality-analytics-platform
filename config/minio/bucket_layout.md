# MinIO bucket layout

Single bucket (ARCHITECTURE §8):

```text
air-quality-lake/
├── raw/
│   ├── uci/air_quality/
│   │   └── station=<Station>/
│   │       └── ingestion_date=YYYY-MM-DD/
│   │           ├── PRSA_Data_<Station>_....csv
│   │           └── PRSA_Data_<Station>_....csv.meta.json
│   └── openmeteo/historical_weather/
├── reference/
│   └── stations/
└── processed/
    ├── air_quality/
    └── weather/
```

Environment variable: `MINIO_BUCKET=air-quality-lake`

## Phase 3 – UCI raw object convention

Object key:

```text
raw/uci/air_quality/station=<Station>/ingestion_date=YYYY-MM-DD/<original_filename>
```

Example:

```text
raw/uci/air_quality/station=Wanshouxigong/ingestion_date=2026-10-06/PRSA_Data_Wanshouxigong_20130301-20170228.csv
```

Rules:

- Keep the original CSV filename (no rename / no transform).
- Do **not** overwrite an existing object at the same key.
- Same content (SHA-256 match) on rerun → skip upload, treat as success.
- Different content on the same key → fail clearly (do not overwrite).

Sidecar metadata (`.meta.json` next to the CSV object):

```text
station
source_file
source_relative_path
sha256
byte_size
ingestion_ts
ingestion_date
source_identifier   # e.g. uci_prsa
```

Also set MinIO user-metadata with at least: `station`, `source_file`, `sha256`, `ingestion_ts`.

## Image note (2026-09)

Official `minio/minio` was removed from Docker Hub. Compose uses `coollabsio/minio`
(community build from MinIO source). Quay (`quay.io/minio/minio`) is an alternative
if authenticated pull is available.

Bootstrap prefixes after MinIO is healthy:

```powershell
bash scripts/infra/init_minio.sh
# or (PowerShell): docker cp + docker exec bootstrap_minio_inside.sh
```
