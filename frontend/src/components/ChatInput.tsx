import { useState, useRef, type KeyboardEvent } from 'react'
import styles from './ChatInput.module.css'

const MAX_CHARS = 2000

interface Props {
  onSend: (question: string) => void
  disabled?: boolean
}

export default function ChatInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const overLimit = value.length > MAX_CHARS
  const nearLimit = !overLimit && value.length >= MAX_CHARS - 200
  const canSend = !disabled && value.trim().length > 0 && !overLimit

  const submit = () => {
    const q = value.trim()
    if (!q || disabled || overLimit) return
    onSend(q)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const handleInput = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }

  return (
    <div className={styles.wrapper}>
      <div className={`${styles.bar} ${overLimit ? styles.barError : ''}`}>
        <textarea
          ref={textareaRef}
          className={styles.input}
          placeholder="Ask about the manuscript, models, error metrics, Coresignal API…"
          value={value}
          rows={1}
          disabled={disabled}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
        />
        {overLimit && (
          <div className={styles.warnIcon} title="Message exceeds 2000 character limit">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
        )}
        <button
          className={styles.send}
          onClick={submit}
          disabled={!canSend}
          aria-label="Send"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>
      <div className={styles.footer}>
        {overLimit ? (
          <span className={styles.counterError}>
            Message too long — {value.length - MAX_CHARS} character{value.length - MAX_CHARS !== 1 ? 's' : ''} over the {MAX_CHARS} limit
          </span>
        ) : (
          <span className={`${styles.counter} ${nearLimit ? styles.counterWarn : ''}`}>
            {value.length > 0 ? `${value.length} / ${MAX_CHARS}` : ''}
          </span>
        )}
      </div>
    </div>
  )
}
