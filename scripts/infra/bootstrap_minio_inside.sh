#!/bin/sh
set -eu
mc alias set local http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb --ignore-existing "local/${MINIO_BUCKET:-air-quality-lake}"
for p in \
  raw/uci/air_quality \
  raw/openmeteo/historical_weather \
  reference/stations \
  processed/air_quality \
  processed/weather
do
  printf '' | mc pipe "local/${MINIO_BUCKET:-air-quality-lake}/$p/.keep"
done
mc ls --recursive "local/${MINIO_BUCKET:-air-quality-lake}/"
