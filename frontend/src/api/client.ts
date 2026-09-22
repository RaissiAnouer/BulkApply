/**
 * API client — wraps fetch with JWT token handling.
 * All API calls go through this module.
 */

const TOKEN_KEY = 'autoapply_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

interface ApiError {
  detail: string | Array<{ msg: string }>
}

export class ApiException extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export function resolveApiUrl(url: string): string {
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url
  }
  const isFileProto = typeof window !== 'undefined' && window.location.protocol === 'file:'
  const base = isFileProto ? 'http://127.0.0.1:8000' : ''
  return url.startsWith('/') ? `${base}${url}` : `${base}/${url}`
}

export async function api<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // Only set Content-Type for JSON bodies (not FormData)
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(resolveApiUrl(url), { ...options, headers })

  if (!response.ok) {
    const data: ApiError = await response.json().catch(() => ({ detail: 'Request failed' }))
    let message: string
    if (typeof data.detail === 'string') {
      message = data.detail
    } else if (Array.isArray(data.detail)) {
      message = data.detail.map((e) => e.msg).join(', ')
    } else {
      message = 'Request failed'
    }
    throw new ApiException(response.status, message)
  }

  return response.json()
}
