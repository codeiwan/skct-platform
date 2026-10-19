import './style.css'

interface HealthResponse {
  status: string
  service: string
  version: string
}

const app = document.querySelector<HTMLDivElement>('#app')

if (!app) {
  throw new Error('Application root element not found')
}

app.innerHTML = `
  <main class="container">
    <header>
      <h1>SKCT Platform</h1>
      <p>Online Examination & Analytics</p>
    </header>

    <section class="card">
      <h2>System Status</h2>

      <div class="status">
        <span class="status-label">Backend Connection</span>
        <span id="backend-status">확인 중...</span>
      </div>

      <button id="refresh-button" type="button">
        연결 다시 확인
      </button>
    </section>
  </main>
`

const statusElement = document.querySelector<HTMLElement>(
  '#backend-status',
)

const refreshButton = document.querySelector<HTMLButtonElement>(
  '#refresh-button',
)

async function checkBackendHealth(): Promise<void> {
  if (!statusElement) return

  statusElement.textContent = '연결 확인 중...'

  try {
    const response = await fetch('/api/health', {
      cache: 'no-store',
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data: HealthResponse = await response.json()

    if (data.status !== 'ok' || data.service !== 'skct-platform') {
      throw new Error('Invalid backend response')
    }

    statusElement.textContent =
      `정상 연결 (${data.service} v${data.version})`

    statusElement.className = 'connected'

  } catch (error) {
    console.error('Backend health check failed:', error)

    statusElement.textContent = '서버 연결 실패'
    statusElement.className = 'disconnected'
  }
}

refreshButton?.addEventListener('click', () => {
  void checkBackendHealth()
})

void checkBackendHealth()
