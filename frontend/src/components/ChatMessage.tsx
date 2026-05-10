import ReactMarkdown from 'react-markdown'
import type { Message } from '../types/chat'
import SourceCard from './SourceCard'
import styles from './ChatMessage.module.css'

interface Props {
  message: Message
}

export default function ChatMessage({ message }: Props) {
  const isUser = message.role === 'user'

  return (
    <div className={`${styles.row} ${isUser ? styles.userRow : styles.assistantRow}`}>
      {!isUser && (
        <div className={styles.avatar}>
          <span>HR</span>
        </div>
      )}

      <div className={`${styles.bubble} ${isUser ? styles.userBubble : styles.assistantBubble}`}>
        {message.loading ? (
          <div className={styles.typing}>
            <span /><span /><span />
          </div>
        ) : (
          <>
            {isUser ? (
              <p className={styles.text}>{message.content}</p>
            ) : (
              <div className={styles.markdown}>
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </div>
            )}
            {!isUser && message.sources && message.sources.length > 0 && (
              <SourceCard sources={message.sources} />
            )}
            <span className={styles.timestamp}>
              {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </>
        )}
      </div>

      {isUser && (
        <div className={`${styles.avatar} ${styles.userAvatar}`}>
          <span>You</span>
        </div>
      )}
    </div>
  )
}
