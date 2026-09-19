import { useState, type FormEvent, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import styles from './AdminLayout.module.css'

/**
 * §6.7: "Route /admin, behind authentication in every environment
 * including local." This shell owns that gate -- nothing under
 * AdminApp's routes renders until whoami confirms a valid session, and
 * a failed check always falls back to the login form, never to the
 * console.
 */
export function AdminLogin({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      })
      if (!res.ok) throw new Error('Incorrect password')
      onLoggedIn()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.loginWrap}>
      <form className={styles.loginCard} onSubmit={submit}>
        <h1 className={styles.loginTitle}>PRISM admin</h1>
        <p className={styles.loginSub}>Not linked from the storefront. Password only, no accounts.</p>
        {error ? <p className={styles.loginError}>{error}</p> : null}
        <input
          type="password"
          className={styles.loginInput}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          autoFocus
        />
        <button type="submit" className={styles.loginBtn} disabled={loading || !password}>
          {loading ? 'Checking...' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}

const NAV_ITEMS = [
  { to: '/admin/sessions', label: 'Sessions' },
  { to: '/admin/event-log', label: 'Event log' },
  { to: '/admin/distributions', label: 'Signal distributions' },
  { to: '/admin/season', label: 'Season' },
]

export function AdminLayout({ children, onLogout }: { children: ReactNode; onLogout: () => void }) {
  const [creatingProfile, setCreatingProfile] = useState(false)

  async function newProfile() {
    setCreatingProfile(true)
    try {
      await fetch('/api/admin/new-profile', { method: 'POST' })
      localStorage.removeItem('prism_session_id')
      localStorage.removeItem('prism_session_code')
      window.open('/', '_blank', 'noopener')
    } finally {
      setCreatingProfile(false)
    }
  }

  async function logout() {
    await fetch('/api/admin/logout', { method: 'POST' })
    onLogout()
  }

  return (
    <div className={styles.shell}>
      <div className={styles.topbar}>
        <span className={styles.brand}>PRISM ADMIN</span>
        <nav className={styles.nav}>
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => [styles.navLink, isActive ? styles.active : ''].join(' ')}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className={styles.actions}>
          <button className={styles.newProfileBtn} onClick={newProfile} disabled={creatingProfile}>
            {creatingProfile ? 'Opening...' : '+ New profile'}
          </button>
          <button className={styles.logoutBtn} onClick={logout}>
            Sign out
          </button>
        </div>
      </div>
      <div className={styles.content}>{children}</div>
    </div>
  )
}
