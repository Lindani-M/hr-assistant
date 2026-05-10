import { useMsal } from '@azure/msal-react'
import { loginRequest } from '../auth/msalConfig'
import logo from '../assets/image.png'
import styles from './LoginPage.module.css'

export default function LoginPage() {
  const { instance } = useMsal()

  const handleLogin = () => {
    instance.loginRedirect(loginRequest)
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        {/* Logo */}
        <div className={styles.logoWrap}>
          <img src={logo} alt="Allan & Gill Gray Foundation" className={styles.logo} />
        </div>

        {/* Title */}
        <div className={styles.titleBlock}>
          <h1 className={styles.title}>TalentGPT</h1>
        </div>

        {/* Divider */}
        <div className={styles.divider} />

        {/* Body copy */}
        <p className={styles.body}>
          Sign in with your AGGPA account.
        </p>

        {/* Sign-in button */}
        <button className={styles.btn} onClick={handleLogin}>
          <MicrosoftIcon />
          Sign in with Microsoft
        </button>

        {/* Footer */}
      </div>

      {/* Background pattern */}
      <div className={styles.pattern} aria-hidden />
    </div>
  )
}

function MicrosoftIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 21 21" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="1" y="1" width="9" height="9" fill="#F25022" />
      <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
      <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
      <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
    </svg>
  )
}
