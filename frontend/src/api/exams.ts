import { ApiError } from './auth'

export interface ExamSectionSummary {
  section_number: number
  section_type: string
  question_count: number
  duration_seconds: number
}

export interface ExamCatalogItem {
  code: string
  title: string
  book_title: string
  publisher: string | null
  total_questions: number
  total_duration_seconds: number
  sections: ExamSectionSummary[]
}

export async function getPublishedExams(): Promise<ExamCatalogItem[]> {
  const response = await fetch('/api/exams', {
    method: 'GET',
    credentials: 'same-origin',
    cache: 'no-store',
  })

  if (!response.ok) {
    if (response.status === 401) {
      throw new ApiError(
        '로그인이 필요합니다. 다시 로그인해 주세요.',
        401,
      )
    }

    throw new ApiError(
      `시험 목록을 불러오지 못했습니다. (HTTP ${response.status})`,
      response.status,
    )
  }

  return (await response.json()) as ExamCatalogItem[]
}
