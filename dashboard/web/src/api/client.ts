const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? ''

export async function apiGet<T>(path: string): Promise<T> {
  const url = `${API_BASE}${path}`
  const res = await fetch(url)
  const body = await res.text()
  const trimmed = body.trimStart()
  if (trimmed.startsWith('<!') || trimmed.startsWith('<html')) {
    throw new Error(
      `API trả HTML thay vì JSON (${url}). Kiểm tra dashboard-api :8100 và mở đúng cổng Vite của project này (proxy /api), không dùng tab Vite app khác.`,
    )
  }
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
  try {
    return JSON.parse(body) as T
  } catch {
    throw new Error(`Không parse được JSON từ ${url}: ${body.slice(0, 120)}`)
  }
}
