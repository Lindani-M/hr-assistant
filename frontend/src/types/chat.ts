export interface Source {
  title: string
  url: string
  chunk_index: number
  relevance_score: number
}

export interface ChatResponse {
  question: string
  answer: string
  response_type: 'rag' | 'chitchat' | 'off_topic'
  sources: Source[]
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  response_type?: 'rag' | 'chitchat' | 'off_topic'
  sources?: Source[]
  timestamp: Date
  loading?: boolean
  isError?: boolean
}

export type ApiErrorCode =
  | 'network'
  | 'rate_limit'
  | 'too_long'
  | 'validation'
  | 'service_unavailable'
  | 'server_error'
  | 'unknown'

export interface ApiError {
  code: ApiErrorCode
  userMessage: string
}
