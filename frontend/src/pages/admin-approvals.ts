import {
  getPendingUsers,
  reviewUser,
  type PendingUser,
  type ReviewAction,
} from '../api/admin'

import { ApiError } from '../api/auth'


function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message
  }

  return '서버에 연결할 수 없습니다.'
}


function formatDateTime(value: string): string {
  // 현재 SQLite 날짜는 UTC로 저장되지만
  // 응답 문자열에 시간대가 없을 수 있습니다.
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/.test(value)
  const utcValue = hasTimezone ? value : `${value}Z`

  const date = new Date(utcValue)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul',
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}


export function mountAdminApprovals(root: HTMLElement): void {
  root.innerHTML = `
    <section class="admin-approval-section">

      <div class="admin-approval-header">
        <div>
          <h2>회원가입 승인 관리</h2>
          <p>승인 대기 중인 회원가입 요청을 관리합니다.</p>
        </div>

        <button
          id="refresh-pending-users"
          class="secondary-button"
          type="button"
        >
          새로고침
        </button>
      </div>

      <p
        id="admin-approval-feedback"
        class="feedback"
        role="status"
        aria-live="polite"
      ></p>

      <div
        id="pending-user-list"
        class="pending-user-list"
      ></div>

    </section>
  `

  const refreshButton = root.querySelector<HTMLButtonElement>(
    '#refresh-pending-users',
  )!

  const list = root.querySelector<HTMLElement>(
    '#pending-user-list',
  )!

  const feedback = root.querySelector<HTMLElement>(
    '#admin-approval-feedback',
  )!

  let busy = false

  function setBusy(value: boolean): void {
    busy = value
    refreshButton.disabled = value

    list.querySelectorAll<HTMLButtonElement>('button').forEach(
      (button) => {
        button.disabled = value
      },
    )
  }

  function createUserRow(user: PendingUser): HTMLElement {
    const row = document.createElement('article')
    row.className = 'pending-user-item'

    const information = document.createElement('div')
    information.className = 'pending-user-information'

    const name = document.createElement('strong')
    name.textContent = user.name

    const skalaId = document.createElement('span')
    skalaId.textContent = `SKALA 고유번호: ${user.skala_id}`

    const createdAt = document.createElement('span')
    createdAt.textContent =
      `가입 신청: ${formatDateTime(user.created_at)}`

    information.append(name, skalaId, createdAt)

    const actions = document.createElement('div')
    actions.className = 'pending-user-actions'

    const approveButton = document.createElement('button')
    approveButton.type = 'button'
    approveButton.className = 'approval-button approve-button'
    approveButton.textContent = '승인'

    const rejectButton = document.createElement('button')
    rejectButton.type = 'button'
    rejectButton.className = 'approval-button reject-button'
    rejectButton.textContent = '반려'

    approveButton.addEventListener('click', () => {
      void handleReview(user, 'approve')
    })

    rejectButton.addEventListener('click', () => {
      void handleReview(user, 'reject')
    })

    actions.append(approveButton, rejectButton)
    row.append(information, actions)

    return row
  }

  async function refreshUsers(): Promise<void> {
    if (busy) return

    setBusy(true)
    list.textContent = '승인 대기 회원을 불러오는 중...'

    try {
      const users = await getPendingUsers()

      if (!root.isConnected) return

      list.replaceChildren()

      if (users.length === 0) {
        const empty = document.createElement('p')
        empty.className = 'pending-user-empty'
        empty.textContent = '현재 승인 대기 중인 회원이 없습니다.'

        list.append(empty)
        return
      }

      for (const user of users) {
        list.append(createUserRow(user))
      }

    } catch (error) {
      if (!root.isConnected) return

      list.textContent = getErrorMessage(error)

    } finally {
      setBusy(false)
    }
  }

  async function handleReview(
    user: PendingUser,
    action: ReviewAction,
  ): Promise<void> {
    if (busy) return

    if (action === 'reject') {
      const confirmed = window.confirm(
        `${user.name} (${user.skala_id}) 회원가입을 반려하시겠습니까?`,
      )

      if (!confirmed) return
    }

    setBusy(true)
    feedback.textContent = ''

    try {
      await reviewUser(user.id, action)

      if (!root.isConnected) return

      setBusy(false)
      await refreshUsers()

      if (!root.isConnected) return

      feedback.textContent =
        action === 'approve'
          ? `${user.name}님의 회원가입을 승인했습니다.`
          : `${user.name}님의 회원가입을 반려했습니다.`

    } catch (error) {
      if (!root.isConnected) return

      feedback.textContent = getErrorMessage(error)

    } finally {
      setBusy(false)
    }
  }

  refreshButton.addEventListener('click', () => {
    feedback.textContent = ''
    void refreshUsers()
  })

  void refreshUsers()
}