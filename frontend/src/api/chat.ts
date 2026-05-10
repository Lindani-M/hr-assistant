import type { ChatResponse } from '../types/chat'

export async function sendChat(
  question: string,
  topK = 5,
  maxTokens = 1500
): Promise<ChatResponse> {
  const res = await fetch('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, top_k: topK, max_tokens: maxTokens }),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`API error ${res.status}: ${err}`)
  }
  return res.json()
}
