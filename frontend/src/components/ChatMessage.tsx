import ReactMarkdown from 'react-markdown'
import type { Message } from '../types/chat'
import SourceCard from './SourceCard'
import styles from './ChatMessage.module.css'

interface Props {
  message: Message
}

export default function ChatMessage({ message }: Props) {
  const isUser = message.role === 'user'
  const isError = message.isError === true

  return (
    <div className={`${styles.row} ${isUser ? styles.userRow : styles.assistantRow}`}>
      <div className={`${styles.bubble} ${isUser ? styles.userBubble : isError ? styles.errorBubble : styles.assistantBubble}`}>
        {message.loading ? (
          <div className={styles.typing}>
            <span /><span /><span />
          </div>
        ) : (
          <>
            {isUser ? (
              <p className={styles.text}>{message.content}</p>
            ) : isError ? (
              <div className={styles.errorContent}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{flexShrink: 0, marginTop: 2}}>
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span>{message.content}</span>
              </div>
            ) : (
              <div className={styles.markdown}>
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </div>
            )}
            {!isUser && !isError && message.sources && message.sources.length > 0 && (
              <SourceCard sources={message.sources} />
            )}
            <span className={styles.timestamp}>
              {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </>
        )}
      </div>
    </div>
  )
}
