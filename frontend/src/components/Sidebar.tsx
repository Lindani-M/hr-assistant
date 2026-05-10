import logo from '../assets/image.png'
import styles from './Sidebar.module.css'

export default function Sidebar() {
  return (
    <aside className={styles.sidebar}>

      {/* Logo card */}
      <div className={styles.logoCard}>
        <img src={logo} alt="Allan Gray Philanthropy" className={styles.logoImg} />
      </div>

      {/* App identity */}
      <div className={styles.identity}>
        <span className={styles.appName}>TalentGPT</span>
        <span className={styles.appTag}>MSc Research Assistant</span>
      </div>

      <div className={styles.rule} />

      {/* About */}
      <div className={styles.section}>
        <p className={styles.sectionLabel}>About</p>
        <p className={styles.sectionDesc}>
          Search the manuscript, supporting literature, and supplementary slides
          from the MSc Documents SharePoint knowledge base.
        </p>
      </div>

      {/* Topic pills */}
      <div className={styles.section}>
        <p className={styles.sectionLabel}>Topics covered</p>
        <div className={styles.pills}>
          {[
            'Recruitment Headhunting',
            'Explainable ML',
            'Coresignal API',
            'TF-IDF',
            'Shapash',
            'RMSE / MAE',
            'Candidate Ranking',
            'Ridge Regression',
          ].map((t) => (
            <span key={t} className={styles.pill}>{t}</span>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className={styles.footer}>
        <div className={styles.statusRow}>
        </div>
        <p className={styles.powered}>Powered by Claude</p>
      </div>

    </aside>
  )
}
