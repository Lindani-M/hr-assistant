import type { Source } from '../types/chat'
import styles from './SourceCard.module.css'

interface Props {
  sources: Source[]
}

export default function SourceCard({ sources }: Props) {
  if (!sources.length) return null

  return (
    <div className={styles.wrapper}>
      <p className={styles.heading}>
        <span className={styles.icon}>📚</span> Sources
      </p>

      <div className={styles.grid}>
        {sources.map((s, i) => (
          <a
            key={i}
            href={s.url}
            target="_blank"
            rel="noreferrer"
            className={styles.row}
            title={`Open: ${s.url}`}
          >
            <span className={styles.rowIndex}>[{i + 1}]</span>
            <div className={styles.body}>
              <div className={styles.titleRow}>
                <p className={styles.title}>{s.title}</p>
                <svg className={styles.externalIcon} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                  <polyline points="15 3 21 3 21 9" />
                  <line x1="10" y1="14" x2="21" y2="3" />
                </svg>
              </div>
              <div className={styles.barRow}>
                <span className={styles.relevanceLabel}>Relevance</span>
                <div className={styles.bar}>
                  <div
                    className={styles.fill}
                    style={{ width: `${s.relevance_score}%` }}
                  />
                </div>
                <span className={styles.score}>
                  {s.relevance_score.toFixed(1)}%
                </span>
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  )
}
