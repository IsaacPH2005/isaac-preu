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
  page_number: number
  page_image_path: string
  page_image_url: string
  pdf_url: string | null
  subject: string
  topic: string
  statement: string
  options: string[]
  has_diagram: boolean
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

export interface FiltersResponse {
  total: number
  diagram_count: number
  subjects: SubjectCount[]
  topics: Record<string, TopicCount[]>
}

export interface SearchFilters {
  q: string
  subject: string
  topic: string
  documentId: number | null
  hasDiagram: boolean
  page: number
  limit: number
}
