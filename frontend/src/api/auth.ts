export interface CurrentUser {
  id: number
  skala_id: string
  name: string
  role: 'USER' | 'ADMIN'
  status: 'ACTIVE'
}

export interface LoginRequest {
  skala_id: string
  password: string
}

export class ApiError extends Error {
  public readonly status: number

  constructor(message: string, status: number) {
    super(message)

    this.name = 'ApiError'
    this.status = status
  }
}

async function handleResponse<T>(
  response: Response,
): Promise<T> {
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)

    let message = `요청 실패 (HTTP ${response.status})`

    if (
      body !== null &&
      typeof body === 'object' &&
      'detail' in body &&
      typeof body.detail === 'string'
    ) {
      message = body.detail
    }

    throw new ApiError(message, response.status)
  }

  return (await response.json()) as T
}

export async function login(
  credentials: LoginRequest,
): Promise<CurrentUser> {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(credentials),
  })

  return handleResponse<CurrentUser>(response)
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const response = await fetch('/api/auth/me', {
    credentials: 'same-origin',
    cache: 'no-store',
  })

  if (response.status === 401) {
    return null
  }

  return handleResponse<CurrentUser>(response)
}

async function getCsrfToken(): Promise<string> {
  const response = await fetch('/api/auth/csrf', {
    credentials: 'same-origin',
    cache: 'no-store',
  })

  const data = await handleResponse<{
    csrf_token: string
  }>(response)

  return data.csrf_token
}

export async function logout(): Promise<void> {
  const csrfToken = await getCsrfToken()

  const response = await fetch('/api/auth/logout', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'X-CSRF-Token': csrfToken,
    },
  })

  if (!response.ok) {
    await handleResponse<unknown>(response)
  }
}