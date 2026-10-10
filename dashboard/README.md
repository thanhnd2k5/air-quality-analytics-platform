# Dashboard (Phase 11)

Read-only web app: **FastAPI** + **React (Vite)** đọc PostgreSQL `dwh` / `mart`.

## Yêu cầu

- Docker Desktop + `docker compose up -d postgres` (DWH/marts đã materialize)
- Python 3.10+ (`py -3` trên Windows)
- Node.js LTS

Biến môi trường dùng chung repo (`.env`): `POSTGRES_*`, `CORS_ORIGINS`, `VITE_API_BASE_URL`.

`GET /api/health` = process sống; `GET /api/health/db` = Postgres sẵn sàng.

## API

```bash
cd dashboard/api
py -3 -m pip install -r requirements.txt
py -3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: http://localhost:8000/api/health
- Stations: http://localhost:8000/api/stations
- OpenAPI: http://localhost:8000/docs

## Web

```bash
cd dashboard/web
npm install
npm run dev
```

Mở http://localhost:5173 — Vite proxy `/api` → `localhost:8000`.

## Phạm vi

- Chỉ hiển thị dữ liệu (không auth / CRUD / train model)
- Map: 12 marker Leaflet; heatmap nội suy = nice-to-have sau
