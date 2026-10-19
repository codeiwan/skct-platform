import { ApiError, getCsrfToken } from './auth'

export interface PendingUser {
  id: number
  skala_id: string
  name: string
  created_at: string
}

export interface ReviewUserResponse {
  id: number
  skala_id: string
  name: string
  status: 'ACTIVE' | 'REJECTED'
}

export type ReviewAction = 'approve' | 'reject'

async function parseResponse<T>(
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

export async function getPendingUsers(): Promise<PendingUser[]> {
  const response = await fetch('/api/admin/users/pending', {
    credentials: 'same-origin',
    cache: 'no-store',
  })

  return parseResponse<PendingUser[]>(response)
}

export async function reviewUser(
  userId: number,
  action: ReviewAction,
): Promise<ReviewUserResponse> {
  const csrfToken = await getCsrfToken()

  const response = await fetch(
    `/api/admin/users/${userId}/${action}`,
    {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    },
  )

  return parseResponse<ReviewUserResponse>(response)
}