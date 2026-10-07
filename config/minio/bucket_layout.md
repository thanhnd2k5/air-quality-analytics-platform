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
│       └── station=<Station>/
│           └── ingestion_date=YYYY-MM-DD/
│               ├── historical_<start>_<end>.json
│               └── historical_<start>_<end>.json.meta.json
├── reference/
│   └── stations/
└── processed/
    ├── uci/air_quality/
    │   └── station=<Station>/
    │       └── process_date=YYYY-MM-DD/
    │           ├── <station>_hourly.parquet
    │           └── <station>_hourly.meta.json
    ├── quarantine/uci/air_quality/
    │   └── station=<Station>/
    │       └── process_date=YYYY-MM-DD/
    └── weather/openmeteo/
        └── station=<Station>/
            └── process_date=YYYY-MM-DD/
                ├── <station>_hourly.parquet
                └── <station>_hourly.meta.json
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

## Phase 4 – UCI processed object convention

Object key (Parquet):

```text
processed/uci/air_quality/station=<Station>/process_date=YYYY-MM-DD/<station>_hourly.parquet
```

Example:

```text
processed/uci/air_quality/station=Wanshouxigong/process_date=2026-10-07/wanshouxigong_hourly.parquet
```

Quarantine (invalid rows / hard failures that are row-scoped):

```text
processed/quarantine/uci/air_quality/station=<Station>/process_date=YYYY-MM-DD/<station>_quarantine.parquet
```

Rules:

- Read raw from MinIO only; never mutate raw objects or local `data/raw`.
- Do **not** overwrite an existing object at the same key.
- Same Parquet content (SHA-256 match) on rerun → skip upload, treat as success.
- Different content on the same key → fail clearly (do not overwrite).
- Filename uses lowercase station slug; Hive-style `station=<Station>` keeps the canonical station name (same as Phase 3 raw).

Sidecar metadata (`.meta.json` next to the Parquet object):

```text
station
source_object_key
source_sha256
source_file_name
source_system          # e.g. uci_prsa
sha256                 # of parquet bytes
byte_size
row_count
quarantine_row_count
process_ts             # deterministic: process_dateT00:00:00Z (in-row lineage)
run_ts                 # wall-clock of the upload run (audit)
process_date
schema_version
```

Idempotency: same `source_sha256` + `schema_version` at the processed key → skip upload (success).
Different source/schema at the same key → fail (no overwrite).

Also set MinIO user-metadata with at least: `station`, `source_object_key`, `sha256`, `process_ts`.

Canonical columns and DQ flags follow `docs/DATA_GUIDE.md` §5 / §37 and Phase 4 decisions in `docs/IMPLEMENTATION_PLAN.md` §9 (no imputation in this phase).

## Phase 5 – Open-Meteo raw + processed

Raw object key (yearly chunks over UCI range):

```text
raw/openmeteo/historical_weather/station=<Station>/ingestion_date=YYYY-MM-DD/historical_<start>_<end>.json
```

Example:

```text
raw/openmeteo/historical_weather/station=Wanshouxigong/ingestion_date=2026-10-07/historical_2015-01-01_2015-12-31.json
```

Rules:

- Store API JSON as-is (no column rename in raw).
- Do **not** overwrite an existing object at the same key.
- Idempotency: same `request_fingerprint` at the key → skip API fetch + upload (Open-Meteo responses include volatile fields such as `generationtime_ms`).
- Different fingerprint at the same key → fail (no overwrite).

Sidecar (`.meta.json`) must include request metadata (`DATA_GUIDE.md` §28): station, requested/returned lat/lon, timezone, date range, hourly variables, units, HTTP status, `request_fingerprint`, sha256, ingestion_ts.

Processed object key (`om_*` columns, `DATA_GUIDE.md` §26):

```text
processed/weather/openmeteo/station=<Station>/process_date=YYYY-MM-DD/<station>_hourly.parquet
```

- Combines yearly chunks from the **latest** `ingestion_date` partition into one hourly Parquet (older partitions are ignored).
- Does **not** overwrite UCI weather; no `weather_final` join here (Phase 6+).
- Idempotency: same combined `source_sha256` + `schema_version` → skip.

## Image note (2026-09)

Official `minio/minio` was removed from Docker Hub. Compose uses `coollabsio/minio`
(community build from MinIO source). Quay (`quay.io/minio/minio`) is an alternative
if authenticated pull is available.

Bootstrap prefixes after MinIO is healthy:

```powershell
bash scripts/infra/init_minio.sh
# or (PowerShell): docker cp + docker exec bootstrap_minio_inside.sh
```
