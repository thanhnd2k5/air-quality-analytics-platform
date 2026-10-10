# Dashboard (Phase 11)

Read-only web app: **FastAPI** + **React (Vite + Mantine + ECharts + Leaflet)** đọc PostgreSQL `dwh` / `mart`.

UI tiếng Việt. Không auth / CRUD / train model.

## Trang

| Route | Nội dung |
|---|---|
| `/` | Tổng quan — KPI + xu hướng |
| `/tram` | Xếp hạng trạm + cluster |
| `/dot-o-nhiem` | Episode + sự kiện đa-trạm |
| `/thoi-tiet` | PM2.5 vs weather |
| `/du-bao` | Actual vs HistGB / persistence |
| `/ban-do` | 12 marker Leaflet |

## Demo nhanh (Windows)

### 1) Postgres + API (Docker)

```powershell
# Từ root repo — cần Docker Desktop đang chạy
docker compose up -d postgres dashboard-api

# Kiểm tra
docker compose ps postgres dashboard-api
Invoke-RestMethod http://127.0.0.1:8100/api/health
Invoke-RestMethod http://127.0.0.1:8100/api/health/db
```

API OpenAPI: http://localhost:8100/docs

### 2) Web (local Node)

```powershell
cd dashboard/web
npm install
npm run dev
```

Mở **đúng URL Vite in ra** (mặc định ưu tiên **5180**; nếu bận thì 5181…).  
Dev dùng `.env.development` → gọi thẳng `http://127.0.0.1:8100` (không phụ thuộc proxy).  

**Hay lỗi:** tab đang mở `localhost:5173` / `5174` là Vite app khác → `/api` trả HTML → “Unexpected token '<'”. API `:8100` vẫn OK.

### API local (không Docker API)

Nếu muốn chạy uvicorn trên máy host (Postgres vẫn Docker, port host trong `.env` — thường `5433`):

```powershell
cd dashboard/api
py -3 -m pip install -r requirements.txt
py -3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8100
```

**Lưu ý:** đừng chạy đồng thời uvicorn host và `dashboard-api` container (cùng host port 8100). Port **8000** trên máy bạn có thể đang là project khác — dashboard mặc định dùng **8100**.

## Biến môi trường (`.env`)

| Biến | Ý nghĩa |
|---|---|
| `POSTGRES_*` | Kết nối DWH |
| `DASHBOARD_API_PORT` | Host port API (mặc định **8100**) |
| `CORS_ORIGINS` | Origin exact thêm (tuỳ chọn) |
| `CORS_ORIGIN_REGEX` | Cho phép `localhost` / `127.0.0.1` mọi port — dùng `[0-9]`/`[.]` (tránh `\\d` trong compose) |
| `VITE_API_BASE_URL` | Dev: `dashboard/web/.env.development` → `http://127.0.0.1:8100`. Để trống = dùng Vite proxy `/api` |

## Endpoints chính

- `GET /api/health`, `/api/health/db`
- `GET /api/stations`, `/api/stations/compare`
- `GET /api/overview/meta|kpis|trends`
- `GET /api/episodes`, `/api/weather`
- `GET /api/predictions`, `/api/predictions/meta`
- `GET /api/map/snapshot`

## Phạm vi / ngoài phạm vi

- Trong: filter → chart/table/map từ marts
- Ngoài: auth, heatmap kiểu Windy, train model từ UI, đọc raw CSV

## Troubleshooting

| Hiện tượng | Cách xử lý |
|---|---|
| `health/db` 500 / connection refused | Bật Docker Desktop; `docker compose up -d postgres` |
| Docker “biến mất” | Engine Desktop tắt — bật lại; Settings → Start when you log in; tắt Resource Saver nếu có |
| `Failed to fetch` (API health vẫn OK) | CORS: `docker compose up -d dashboard-api --force-recreate`; mở đúng `http://localhost:5180/` |
| HTML / `Unexpected token '<'` | Đang mở Vite app khác (5173/5174) — dùng URL Vite của dashboard |
| 404 JSON `Không thể xử lý yêu cầu` | Đang trúng app khác trên `:8000` — API dashboard ở **8100** |
| Port 8100 đã dùng | Đổi `DASHBOARD_API_PORT` trong `.env` + `.env.development` + proxy `vite.config.ts` |
