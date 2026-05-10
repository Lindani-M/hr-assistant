import { useState, useRef, useEffect, useCallback } from 'react'
import { useIsAuthenticated, useMsal } from '@azure/msal-react'
import { InteractionStatus, InteractionRequiredAuthError } from '@azure/msal-browser'
import Sidebar from './components/Sidebar'
import ChatMessage from './components/ChatMessage'
import ChatInput from './components/ChatInput'
import LoginPage from './components/LoginPage'
import type { Message, ApiError } from './types/chat'
import { sendChat } from './api/chat'
import styles from './App.module.css'

const SUGGESTED = [
  'Why should we use RMSE over MAE?',
  'What models were used for candidate ranking?',
  'What is the Coresignal API used for?',
  'How does TF-IDF work in the manuscript?',
  'What does Shapash do in the pipeline?',
  'Who wrote the manuscript and what is it about?',
]

const WELCOME: Message = {
  id: 'welcome',
  role: 'assistant',
  content:
    "👋 Welcome! I'm TalentGPT, your MSc Research Assistant.\n\n" +
    'I have access to the MSc Documents SharePoint knowledge base and can help you with:\n\n' +
    '- The manuscript on recruitment headhunting and explainable ML\n' +
    '- Candidate ranking models (TF-IDF, Ridge Regression, Gradient Boosting, Random Forest)\n' +
    '- Explainability with Shapash\n' +
    '- Job recommendation systems using APIs and web crawling\n' +
    '- Error metrics: RMSE vs MAE\n\n' +
    'What would you like to know?',
  timestamp: new Date(),
}

export default function App() {
  const isAuthenticated = useIsAuthenticated()
  const { inProgress, instance, accounts } = useMsal()
  const account = accounts[0]
  const displayName = account?.name ?? account?.username ?? ''
  const email = account?.username ?? ''

  const handleLogout = async () => {
    // Local-only logout: clears tokens from sessionStorage without touching the Microsoft session
    await instance.clearCache()
    window.location.reload()
  }

  const [messages, setMessages] = useState<Message[]>([WELCOME])
  const [suggestionsVisible, setSuggestionsVisible] = useState(true)
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // All hooks must be declared before any conditional return
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = useCallback(async (question: string) => {
    // Acquire a fresh access token before every request.
    // Only redirect to login if the error is InteractionRequiredAuthError
    // (e.g. MFA required, consent needed). All other errors let the request
    // proceed — the backend skips auth when its env vars are not configured.
    let accessToken = ''
    try {
      const result = await instance.acquireTokenSilent({
        scopes: ['openid', 'profile', 'User.Read'],
        account,
      })
      accessToken = result.accessToken
    } catch (err) {
      if (err instanceof InteractionRequiredAuthError) {
        await instance.acquireTokenRedirect({ scopes: ['openid', 'profile', 'User.Read'] })
        return
      }
      // Non-fatal: proceed without a token (backend will reject with 401 if auth is enforced)
    }

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: question,
      timestamp: new Date(),
    }

    const loadingMsg: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      loading: true,
    }

    setSuggestionsVisible(false)
    setMessages((prev) => [...prev, userMsg, loadingMsg])
    setLoading(true)

    try {
      const data = await sendChat(question, accessToken)
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? {
                ...m,
                content: data.answer,
                response_type: data.response_type,
                sources: data.sources,
                loading: false,
              }
            : m
        )
      )
    } catch (err) {
      const apiErr = err as ApiError
      const userMessage = apiErr?.userMessage
        ?? 'Something went wrong. Please try again.'
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? { ...m, content: userMessage, loading: false, isError: true }
            : m
        )
      )
    } finally {
      setLoading(false)
    }
  }, [])

  // Show login page when not authenticated and MSAL is idle
  if (!isAuthenticated && inProgress === InteractionStatus.None) {
    return <LoginPage />
  }

  // Show nothing (blank) while MSAL is processing a redirect/login — prevents flash of chat UI
  if (!isAuthenticated || inProgress !== InteractionStatus.None) {
    return null
  }

  return (
    <div className={styles.layout}>
      {/* Header — full width */}
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <div className={styles.headerLeft}>
            <div>
              <h1 className={styles.headerTitle}>TalentGPT</h1>
              <p className={styles.headerSub}>MSc Research Assistant</p>
            </div>
          </div>
          <div className={styles.headerActions}>
            {/* User info chip */}
            <div className={styles.userChip}>
              <div className={styles.userAvatar}>
                {displayName ? displayName[0].toUpperCase() : '?'}
              </div>
              <div className={styles.userInfo}>
                <span className={styles.userName}>{displayName || email}</span>
                {displayName && <span className={styles.userEmail}>{email}</span>}
              </div>
            </div>
            {/* Logout button */}
            <button className={styles.logoutBtn} onClick={handleLogout} title="Sign out">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              Sign out
            </button>
          </div>
        </div>
      </header>

      {/* Body — sidebar + chat side by side */}
      <div className={styles.body}>
        <Sidebar />

        <div className={styles.main}>
          {/* Messages */}
          <div className={styles.messages}>
            <div className={styles.messagesInner}>
              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}
              {suggestionsVisible && (
                <div className={styles.suggestions}>
                  <p className={styles.suggestionsLabel}>Suggested questions</p>
                  <div className={styles.suggestionsGrid}>
                    {SUGGESTED.map((q) => (
                      <button
                        key={q}
                        className={styles.suggestionChip}
                        onClick={() => handleSend(q)}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </div>

          {/* Input */}
          <ChatInput onSend={handleSend} disabled={loading} />
          <p className={styles.disclaimer}>
            AI responses may occasionally be inaccurate. Please verify important information.
          </p>
        </div>
      </div>
    </div>
  )
}
