import type { ChatResponse, ApiError } from '../types/chat'

function classifyError(status: number, detail: string): ApiError {
  if (status === 401) {
    return {
      code: 'network',
      userMessage: 'Your session has expired. Please refresh the page and sign in again.',
    }
  }
  if (status === 429) {
    return {
      code: 'rate_limit',
      userMessage: "You're sending messages too quickly. Please wait a moment and try again.",
    }
  }
  if (status === 422) {
    // Pydantic validation — e.g. message too long past the server limit
    const isLength = detail.toLowerCase().includes('max_length') || detail.toLowerCase().includes('too long')
    return {
      code: isLength ? 'too_long' : 'validation',
      userMessage: isLength
        ? 'Your message exceeds the maximum allowed length. Please shorten it and try again.'
        : `Your request couldn\'t be processed: ${detail}`,
    }
  }
  if (status === 502 || status === 503) {
    if (detail.toLowerCase().includes('embedding')) {
      return { code: 'service_unavailable', userMessage: 'The AI embedding service is temporarily unavailable. Please try again shortly.' }
    }
    if (detail.toLowerCase().includes('search') || detail.toLowerCase().includes('knowledge base')) {
      return { code: 'service_unavailable', userMessage: 'The knowledge base search service is temporarily unavailable. Please try again shortly.' }
    }
    if (detail.toLowerCase().includes('ai answer') || detail.toLowerCase().includes('llm') || detail.toLowerCase().includes('claude')) {
      return { code: 'service_unavailable', userMessage: 'The AI answer service is temporarily unavailable. Please try again shortly.' }
    }
    if (detail.toLowerCase().includes('topic')) {
      return { code: 'service_unavailable', userMessage: 'A background service is temporarily unavailable. Please try again shortly.' }
    }
    return { code: 'service_unavailable', userMessage: detail || 'A backend service is temporarily unavailable. Please try again shortly.' }
  }
  if (status >= 500) {
    return { code: 'server_error', userMessage: 'An unexpected server error occurred. Please try again shortly.' }
  }
  return { code: 'unknown', userMessage: 'An unexpected error occurred. Please try again.' }
}

export async function sendChat(
  question: string,
  accessToken: string,
  topK = 5,
  maxTokens = 1500
): Promise<ChatResponse> {
  let res: Response
  try {
    res = await fetch('/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ question, top_k: topK, max_tokens: maxTokens }),
    })
  } catch {
    const err: ApiError = {
      code: 'network',
      userMessage: 'Unable to reach the server. Please check your connection and try again.',
    }
    throw err
  }

  if (!res.ok) {
    let detail = ''
    try {
      const body = await res.json()
      detail = body?.detail ?? ''
    } catch {
      detail = await res.text().catch(() => '')
    }
    throw classifyError(res.status, detail)
  }

  return res.json()
}
