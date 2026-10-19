import './style.css'

import {
  ApiError,
  getCurrentUser,
  login,
  logout,
  register,
  type CurrentUser,
  type RegisterResponse,
} from './api/auth'


const app = document.querySelector<HTMLDivElement>('#app')

if (!app) {
  throw new Error('Application root element not found')
}


function getElement<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id)

  if (!element) {
    throw new Error(`Element not found: ${id}`)
  }

  return element as T
}


function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message
  }

  return '서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.'
}


// --------------------------------------------------
// 로그인 화면
// --------------------------------------------------

function renderLogin(initialMessage = ''): void {
  app!.innerHTML = `
    <main class="auth-layout">
      <section class="auth-card">

        <header class="auth-header">
          <div class="brand-mark">SKCT</div>
          <h1>SKCT Platform</h1>
          <p>Online Examination & Analytics</p>
        </header>

        <form id="login-form" class="auth-form">

          <div class="form-field">
            <label for="skala-id">SKALA 고유번호</label>
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
            <label for="password">비밀번호</label>
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

          <button
            id="register-link"
            type="button"
            class="text-button"
          >
            계정이 없으신가요? 회원가입
          </button>

        </form>

        <footer class="auth-footer">
          <p>SKCT 학습 및 성적관리 플랫폼</p>
          <span>Independent Educational Project</span>
        </footer>

      </section>
    </main>
  `

  const form = getElement<HTMLFormElement>('login-form')
  const feedback = getElement<HTMLElement>('login-feedback')
  const submitButton = getElement<HTMLButtonElement>('login-button')
  const registerButton = getElement<HTMLButtonElement>('register-link')

  feedback.textContent = initialMessage

  form.addEventListener('submit', async (event) => {
    event.preventDefault()

    if (submitButton.disabled) return

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

  registerButton.addEventListener('click', () => {
    renderRegister()
  })
}


// --------------------------------------------------
// 회원가입 화면
// --------------------------------------------------

function renderRegister(): void {
  app!.innerHTML = `
    <main class="auth-layout">
      <section class="auth-card">

        <header class="auth-header">
          <div class="brand-mark">SKCT</div>
          <h1>회원가입</h1>
          <p>SKCT Platform 계정 생성</p>
        </header>

        <form id="register-form" class="auth-form">

          <div class="form-field">
            <label for="register-skala-id">
              SKALA 고유번호
            </label>
            <input
              id="register-skala-id"
              name="skala_id"
              type="text"
              placeholder="예: G051"
              autocomplete="username"
              maxlength="64"
              required
            />
          </div>

          <div class="form-field">
            <label for="register-name">이름</label>
            <input
              id="register-name"
              name="name"
              type="text"
              placeholder="이름 입력"
              autocomplete="name"
              maxlength="100"
              required
            />
          </div>

          <div class="form-field">
            <label for="register-password">비밀번호</label>
            <input
              id="register-password"
              name="password"
              type="password"
              placeholder="8자 이상 입력"
              autocomplete="new-password"
              minlength="8"
              maxlength="128"
              required
            />
          </div>

          <div class="form-field">
            <label for="register-password-confirm">
              비밀번호 확인
            </label>
            <input
              id="register-password-confirm"
              name="password_confirm"
              type="password"
              placeholder="비밀번호 다시 입력"
              autocomplete="new-password"
              minlength="8"
              maxlength="128"
              required
            />
          </div>

          <p class="auth-note">
            회원가입 후 관리자 승인이 완료되어야
            로그인할 수 있습니다.
          </p>

          <p
            id="register-feedback"
            class="feedback"
            role="alert"
            aria-live="polite"
          ></p>

          <button
            id="register-button"
            class="primary-button"
            type="submit"
          >
            회원가입 신청
          </button>

          <button
            id="back-to-login"
            class="text-button"
            type="button"
          >
            로그인 화면으로 돌아가기
          </button>

        </form>

      </section>
    </main>
  `

  const form = getElement<HTMLFormElement>('register-form')
  const feedback = getElement<HTMLElement>('register-feedback')
  const submitButton = getElement<HTMLButtonElement>('register-button')
  const backButton = getElement<HTMLButtonElement>('back-to-login')

  backButton.addEventListener('click', () => {
    renderLogin()
  })

  form.addEventListener('submit', async (event) => {
    event.preventDefault()

    if (submitButton.disabled) return

    const formData = new FormData(form)

    const skalaId = String(
      formData.get('skala_id') ?? '',
    ).trim()

    const name = String(
      formData.get('name') ?? '',
    ).trim()

    const password = String(
      formData.get('password') ?? '',
    )

    const passwordConfirm = String(
      formData.get('password_confirm') ?? '',
    )

    feedback.textContent = ''

    if (!skalaId || !name) {
      feedback.textContent =
        'SKALA 고유번호와 이름을 입력해 주세요.'
      return
    }

    if (password !== passwordConfirm) {
      feedback.textContent =
        '비밀번호가 일치하지 않습니다.'
      return
    }

    if (password.length < 8 || password.length > 128) {
      feedback.textContent =
        '비밀번호는 8~128자로 입력해 주세요.'
      return
    }

    submitButton.disabled = true
    submitButton.textContent = '가입 신청 중...'

    try {
      const registeredUser = await register({
        skala_id: skalaId,
        name,
        password,
      })

      renderRegistrationSuccess(registeredUser)

    } catch (error) {
      feedback.textContent = getErrorMessage(error)

    } finally {
      submitButton.disabled = false
      submitButton.textContent = '회원가입 신청'
    }
  })
}


// --------------------------------------------------
// 회원가입 성공 및 승인 대기 화면
// --------------------------------------------------

function renderRegistrationSuccess(
  user: RegisterResponse,
): void {
  app!.innerHTML = `
    <main class="auth-layout">
      <section class="auth-card">

        <header class="auth-header">
          <div class="brand-mark">SKCT</div>

          <h1>가입 신청 완료</h1>
          <p>회원가입 신청이 정상적으로 접수되었습니다.</p>
        </header>

        <div class="registration-success">

          <h2>관리자 승인 대기</h2>

          <p>
            관리자 승인 후 서비스를 이용할 수 있습니다.
          </p>

          <div class="registration-info">
            <span>신청 고유번호</span>
            <strong id="registered-skala-id"></strong>

            <span>계정 상태</span>
            <strong>PENDING</strong>
          </div>

        </div>

        <button
          id="registration-login-button"
          class="primary-button"
          type="button"
        >
          로그인 화면으로 돌아가기
        </button>

      </section>
    </main>
  `

  const registeredId = getElement<HTMLElement>(
    'registered-skala-id',
  )

  registeredId.textContent = user.skala_id

  const loginButton = getElement<HTMLButtonElement>(
    'registration-login-button',
  )

  loginButton.addEventListener('click', () => {
    renderLogin()
  })
}


// --------------------------------------------------
// 로그인 후 대시보드
// --------------------------------------------------

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

  const title = getElement<HTMLElement>('welcome-title')
  const accountId = getElement<HTMLElement>('account-id')
  const roleBadge = getElement<HTMLElement>('role-badge')
  const sectionTitle = getElement<HTMLElement>('section-title')
  const sectionDescription = getElement<HTMLElement>('section-description')

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

  const logoutButton = getElement<HTMLButtonElement>(
    'logout-button',
  )

  const feedback = getElement<HTMLElement>(
    'logout-feedback',
  )

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


// --------------------------------------------------
// 애플리케이션 초기화
// --------------------------------------------------

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