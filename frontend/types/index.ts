export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface DocumentItem {
  id: number
  filename: string
  total_pages: number
  processed_pages: number
  status: DocumentStatus
  error_message: string | null
  created_at: string
  question_count: number
  progress: number
  pdf_url: string | null
}

export interface Question {
  id: number
  document_id: number
  document_filename: string
  question_number: number
  question_label: string
  page_number: number
  page_image_path: string
  page_image_url: string
  pdf_url: string | null
  subject: string
  topic: string
  statement: string
  options: string[]
  has_diagram: boolean
  exam: string
  exam_type: string
  exam_year: number | null
  answer: string
  answer_detail: string
  difficulty: number
  key_note: string
  has_solution: boolean
  figure_urls: string[]
  rank: number | null
}

export interface QuestionPage {
  items: Question[]
  total: number
  page: number
  limit: number
  pages: number
}

export interface SubjectCount {
  subject: string
  count: number
}

export interface TopicCount {
  topic: string
  count: number
}

export interface ExamCount {
  exam: string
  exam_type: string
  exam_year: number | null
  first_page: number
  last_page: number
  count: number
}

export interface FiltersResponse {
  total: number
  diagram_count: number
  answered_count: number
  page_min: number
  page_max: number
  subjects: SubjectCount[]
  topics: Record<string, TopicCount[]>
  exam_types: { exam_type: string; count: number }[]
  exams: ExamCount[]
  difficulties: { difficulty: number; count: number }[]
}

export interface SearchFilters {
  q: string
  subject: string
  topic: string
  documentId: number | null
  hasDiagram: boolean
  examType: string
  exam: string
  pageFrom: number | null
  pageTo: number | null
  difficulty: number | null
  hasAnswer: boolean
  page: number
  limit: number
}

export interface Solution {
  question_id: number
  status: 'none' | 'pending' | 'done' | 'failed'
  figure_data: string[]
  strategy: string
  steps: string[]
  shortcut: string
  common_mistake: string
  final_answer: string
  reaches_key: boolean | null
  confidence: string
  note: string
  error: string
  can_generate: boolean
}
