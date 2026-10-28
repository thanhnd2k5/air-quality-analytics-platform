const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? ''

// Responses are memoised per URL: pages share meta/stations calls, a request already in
// flight is reused, and going back to a page renders without waiting. Failed requests are
// dropped so they retry; a page reload (F5) always starts from fresh data.
const CACHE_TTL_MS = 5 * 60 * 1000
const CACHE_MAX_ENTRIES = 200
const cache = new Map<string, { at: number; promise: Promise<unknown> }>()

export function apiGet<T>(path: string): Promise<T> {
  const url = `${API_BASE}${path}`
  const hit = cache.get(url)
  if (hit && Date.now() - hit.at < CACHE_TTL_MS) {
    cache.delete(url) // re-insert to keep Map order = least recently used first
    cache.set(url, hit)
    return hit.promise as Promise<T>
  }
  const promise = request<T>(url)
  cache.set(url, { at: Date.now(), promise })
  promise.catch(() => {
    if (cache.get(url)?.promise === promise) cache.delete(url)
  })
  for (const key of cache.keys()) {
    if (cache.size <= CACHE_MAX_ENTRIES) break
    cache.delete(key)
  }
  return promise
}

/** Status calls (health, data quality) must show the current state: no memo. */
export function apiGetFresh<T>(path: string): Promise<T> {
  return request<T>(`${API_BASE}${path}`)
}

async function request<T>(url: string): Promise<T> {
  let res: Response
  try {
    res = await fetch(url)
  } catch {
    throw new Error(
      `Không kết nối được API (${url}). ` +
        `Chạy \`docker compose up -d dashboard-api\` và mở http://127.0.0.1:8100/api/health. ` +
        `Nếu health OK mà vẫn lỗi: CORS — recreate dashboard-api sau khi pull fix compose.`,
    )
  }
  const body = await res.text()
  const trimmed = body.trimStart()
  if (trimmed.startsWith('<!') || trimmed.startsWith('<html')) {
    const origin = typeof window !== 'undefined' ? window.location.origin : '?'
    throw new Error(
      `API trả HTML thay vì JSON (${url}) từ tab ${origin}. ` +
        `Mở đúng Vite dashboard (ưu tiên :5180; đừng dùng tab app khác ở 5173/5174).`,
    )
  }
  if (!res.ok) {
    let detail = body
    try {
      const parsed = JSON.parse(body)
      if (typeof parsed?.detail === 'string') detail = parsed.detail
    } catch {
      // not JSON: show the raw body
    }
    throw new Error(`${res.status} ${res.statusText}: ${detail}`)
  }
  try {
    return JSON.parse(body) as T
  } catch {
    throw new Error(`Không parse được JSON từ ${url}: ${body.slice(0, 120)}`)
  }
}
