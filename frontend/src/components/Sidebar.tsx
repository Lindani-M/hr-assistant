import styles from './Sidebar.module.css'

interface Props {
  // kept for future use
}

export default function Sidebar(_props: Props) {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.section}>
        <p className={styles.sectionLabel}>HR Assistant</p>
        <p className={styles.sectionDesc}>
          Your company-wide resource for HR policies, benefits, scholarships,
          people, and more — powered by our SharePoint knowledge base.
        </p>
      </div>

      <div className={styles.footer}>
        <div className={styles.badge}>
          <span className={styles.dot} />
          <span>Connected to SharePoint</span>
        </div>
        <p className={styles.powered}>Powered by Claude</p>
      </div>
    </aside>
  )
}
