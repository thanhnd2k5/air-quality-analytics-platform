const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? ''

export async function apiGet<T>(path: string): Promise<T> {
  const url = `${API_BASE}${path}`
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
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
  try {
    return JSON.parse(body) as T
  } catch {
    throw new Error(`Không parse được JSON từ ${url}: ${body.slice(0, 120)}`)
  }
}
