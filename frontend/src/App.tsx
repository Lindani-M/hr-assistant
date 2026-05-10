import { useState, useRef, useEffect, useCallback } from 'react'
import { useIsAuthenticated, useMsal } from '@azure/msal-react'
import { InteractionStatus } from '@azure/msal-browser'
import Sidebar from './components/Sidebar'
import ChatMessage from './components/ChatMessage'
import ChatInput from './components/ChatInput'
import LoginPage from './components/LoginPage'
import type { Message } from './types/chat'
import { sendChat } from './api/chat'
import logo from './assets/image.png'
import styles from './App.module.css'

const SUGGESTED = [
  'What are the leave policies?',
  "Who are the 2025 President's Scholars?",
  'What employee benefits are available?',
  "What is the President's Scholarship?",
  'How do I submit a performance review?',
  'What wellness programmes are offered?',
]

const WELCOME: Message = {
  id: 'welcome',
  role: 'assistant',
  content:
    "👋 Welcome! I'm your Allan & Gill Gray Foundation HR Assistant.\n\n" +
    'I have access to your company SharePoint knowledge base and can help you with:\n\n' +
    '- HR policies and procedures\n' +
    '- Employee benefits and well-being\n' +
    '- Scholarships and awards\n' +
    '- People and profiles\n' +
    '- Company programmes and initiatives\n\n' +
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
      const data = await sendChat(question)
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
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? {
                ...m,
                content: '⚠️ Sorry, something went wrong. Please try again.',
                loading: false,
              }
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
            <img src={logo} alt="Allan & Gill Gray" className={styles.headerLogo} />
            <div>
              <h1 className={styles.headerTitle}>HR Assistant</h1>
              <p className={styles.headerSub}>Company-wide knowledge</p>
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
