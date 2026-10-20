import {
  getPublishedExams,
  type ExamCatalogItem,
} from '../api/exams'

import { ApiError } from '../api/auth'


function formatDuration(seconds: number): string {
  return `${Math.floor(seconds / 60)}분`
}


function createExamCard(exam: ExamCatalogItem): HTMLElement {
  const card = document.createElement('article')
  card.className = 'exam-catalog-card'

  const title = document.createElement('h3')
  title.textContent = exam.title

  const book = document.createElement('p')
  book.className = 'exam-catalog-book'
  book.textContent = exam.book_title

  const publisher = document.createElement('p')
  publisher.className = 'exam-catalog-publisher'
  publisher.textContent = exam.publisher ?? '출판사 미기재'

  const summary = document.createElement('p')
  summary.className = 'exam-catalog-summary'
  summary.textContent =
    `총 ${exam.total_questions}문항 · ${formatDuration(exam.total_duration_seconds)}`

  const sections = document.createElement('ul')
  sections.className = 'exam-catalog-sections'

  for (const section of exam.sections) {
    const item = document.createElement('li')

    item.textContent =
      `${section.section_type} · ` +
      `${section.question_count}문항 · ` +
      formatDuration(section.duration_seconds)

    sections.append(item)
  }

  const notice = document.createElement('p')
  notice.className = 'exam-catalog-notice'
  notice.textContent = '시험 응시 기능은 준비 중입니다.'

  card.append(
    title,
    book,
    publisher,
    summary,
    sections,
    notice,
  )

  return card
}


export function mountExamCatalog(root: HTMLElement): void {
  root.innerHTML = `
    <div class="exam-catalog-header">
      <div>
        <h2>공식 모의고사</h2>
        <p>현재 공개된 SKCT 시험 목록입니다.</p>
      </div>

      <button
        id="refresh-exam-catalog"
        class="secondary-button"
        type="button"
      >
        새로고침
      </button>
    </div>

    <p
      id="exam-catalog-feedback"
      class="feedback"
      role="status"
      aria-live="polite"
    ></p>

    <div
      id="exam-catalog-list"
      class="exam-catalog-list"
    ></div>
  `

  const refreshButton = root.querySelector<HTMLButtonElement>(
    '#refresh-exam-catalog',
  )!

  const feedback = root.querySelector<HTMLElement>(
    '#exam-catalog-feedback',
  )!

  const list = root.querySelector<HTMLElement>(
    '#exam-catalog-list',
  )!

  let loading = false

  async function loadExams(): Promise<void> {
    if (loading) return

    loading = true
    refreshButton.disabled = true

    feedback.textContent = ''
    list.textContent = '시험 목록을 불러오는 중...'

    try {
      const exams = await getPublishedExams()

      if (!root.isConnected) return

      list.replaceChildren()

      if (exams.length === 0) {
        const empty = document.createElement('p')
        empty.className = 'exam-catalog-empty'
        empty.textContent =
          '현재 공개된 공식 모의고사가 없습니다.'

        list.append(empty)
        return
      }

      for (const exam of exams) {
        list.append(createExamCard(exam))
      }

    } catch (error) {
      if (!root.isConnected) return

      list.replaceChildren()

      feedback.textContent =
        error instanceof ApiError
          ? error.message
          : '서버에 연결할 수 없습니다.'

    } finally {
      loading = false

      if (root.isConnected) {
        refreshButton.disabled = false
      }
    }
  }

  refreshButton.addEventListener('click', () => {
    void loadExams()
  })

  void loadExams()
}
