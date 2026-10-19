import './style.css'

import {
  ApiError,
  getCurrentUser,
  login,
  logout,
  type CurrentUser,
} from './api/auth'


const app = document.querySelector<HTMLDivElement>('#app')

if (!app) {
  throw new Error('Application root element not found')
}


function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message
  }

  return '서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.'
}


function renderLogin(initialMessage = ''): void {
  app!.innerHTML = `
    <main class="auth-layout">
      <section class="auth-card">

        <header class="auth-header">
          <div class="brand-mark">SKCT</div>

          <h1>SKCT Platform</h1>

          <p>
            Online Examination & Analytics
          </p>
        </header>

        <form id="login-form" class="auth-form">

          <div class="form-field">
            <label for="skala-id">
              SKALA 고유번호
            </label>

            <input
              id="skala-id"
              name="skala_id"
              type="text"
              placeholder="예: G051"
              autocomplete="username"
              maxlength="64"
              required
            />
          </div>

          <div class="form-field">
            <label for="password">
              비밀번호
            </label>

            <input
              id="password"
              name="password"
              type="password"
              placeholder="비밀번호 입력"
              autocomplete="current-password"
              required
            />
          </div>

          <p
            id="login-feedback"
            class="feedback"
            role="alert"
            aria-live="polite"
          ></p>

          <button
            id="login-button"
            type="submit"
            class="primary-button"
          >
            로그인
          </button>

        </form>

        <footer class="auth-footer">
          <p>SKCT 학습 및 성적관리 플랫폼</p>
          <span>Independent Educational Project</span>
        </footer>

      </section>
    </main>
  `

  const form = document.querySelector<HTMLFormElement>(
    '#login-form',
  )

  const feedback = document.querySelector<HTMLElement>(
    '#login-feedback',
  )

  const submitButton = document.querySelector<HTMLButtonElement>(
    '#login-button',
  )

  if (!form || !feedback || !submitButton) {
    throw new Error('Login form initialization failed')
  }

  feedback.textContent = initialMessage

  form.addEventListener('submit', async (event) => {
    event.preventDefault()

    if (submitButton.disabled) {
      return
    }

    const formData = new FormData(form)

    const skalaId = String(formData.get('skala_id') ?? '')
    const password = String(formData.get('password') ?? '')

    feedback.textContent = ''
    submitButton.disabled = true
    submitButton.textContent = '로그인 중...'

    try {
      const user = await login({
        skala_id: skalaId,
        password,
      })

      renderDashboard(user)

    } catch (error) {
      feedback.textContent = getErrorMessage(error)

    } finally {
      submitButton.disabled = false
      submitButton.textContent = '로그인'
    }
  })
}


function renderDashboard(user: CurrentUser): void {
  app!.innerHTML = `
    <main class="dashboard-layout">

      <header class="dashboard-header">
        <div class="dashboard-brand">
          <strong>SKCT Platform</strong>
        </div>

        <button
          id="logout-button"
          class="secondary-button"
          type="button"
        >
          로그아웃
        </button>
      </header>

      <section class="welcome-card">

        <div class="welcome-heading">
          <div>
            <p class="section-caption">MY ACCOUNT</p>
            <h1 id="welcome-title"></h1>
          </div>

          <span id="role-badge" class="role-badge"></span>
        </div>

        <div class="account-information">
          <div>
            <span>SKALA 고유번호</span>
            <strong id="account-id"></strong>
          </div>

          <div>
            <span>계정 상태</span>
            <strong>ACTIVE</strong>
          </div>
        </div>

        <div class="placeholder-section">
          <h2 id="section-title"></h2>
          <p id="section-description"></p>
        </div>

        <p
          id="logout-feedback"
          class="feedback"
          role="alert"
          aria-live="polite"
        ></p>

      </section>

    </main>
  `

  const title = document.querySelector<HTMLElement>(
    '#welcome-title',
  )!

  const accountId = document.querySelector<HTMLElement>(
    '#account-id',
  )!

  const roleBadge = document.querySelector<HTMLElement>(
    '#role-badge',
  )!

  const sectionTitle = document.querySelector<HTMLElement>(
    '#section-title',
  )!

  const sectionDescription = document.querySelector<HTMLElement>(
    '#section-description',
  )!

  title.textContent = `${user.name}님, 환영합니다.`
  accountId.textContent = user.skala_id

  const isAdmin = user.role === 'ADMIN'

  roleBadge.textContent = isAdmin ? 'ADMIN' : 'USER'

  sectionTitle.textContent = isAdmin
    ? '관리자 공간'
    : '나의 학습 공간'

  sectionDescription.textContent = isAdmin
    ? '관리자 기능은 다음 개발 단계에서 추가됩니다.'
    : '시험 응시 및 성적관리 기능은 추후 추가됩니다.'

  const logoutButton = document.querySelector<HTMLButtonElement>(
    '#logout-button',
  )!

  const feedback = document.querySelector<HTMLElement>(
    '#logout-feedback',
  )!

  logoutButton.addEventListener('click', async () => {
    logoutButton.disabled = true
    feedback.textContent = ''

    try {
      await logout()
      renderLogin()

    } catch (error) {
      feedback.textContent = getErrorMessage(error)
      logoutButton.disabled = false
    }
  })
}


async function initializeApp(): Promise<void> {
  app!.innerHTML = `
    <div class="loading-screen" role="status">
      로그인 상태를 확인하고 있습니다...
    </div>
  `

  try {
    const user = await getCurrentUser()

    if (user) {
      renderDashboard(user)
    } else {
      renderLogin()
    }

  } catch (error) {
    renderLogin(getErrorMessage(error))
  }
}


void initializeApp()