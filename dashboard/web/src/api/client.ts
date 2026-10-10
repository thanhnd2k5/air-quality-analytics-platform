const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? ''

export async function apiGet<T>(path: string): Promise<T> {
  const url = `${API_BASE}${path}`
  const res = await fetch(url)
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
  return res.json() as Promise<T>
}
