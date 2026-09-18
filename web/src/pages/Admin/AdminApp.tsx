import { useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AdminLayout, AdminLogin } from './AdminLayout'
import { LiveView } from './LiveView'
import { SessionDetail } from './SessionDetail'
import { SessionViewer } from './SessionViewer'
import { SessionsList } from './SessionsList'
import { SignalDistributions } from './SignalDistributions'

type AuthState = 'checking' | 'authenticated' | 'unauthenticated'

/**
 * The entire admin console, mounted at /admin/* independently of the
 * storefront's own SessionProvider/consent gate (see web/src/main.tsx)
 * -- an admin is staff, not a visitor, and none of the consent/telemetry
 * machinery the storefront wraps everything in applies here.
 */
export function AdminApp() {
  const [auth, setAuth] = useState<AuthState>('checking')

  useEffect(() => {
    fetch('/api/admin/whoami')
      .then((r) => r.json())
      .then((d) => setAuth(d.authenticated ? 'authenticated' : 'unauthenticated'))
      .catch(() => setAuth('unauthenticated'))
  }, [])

  if (auth === 'checking') return null
  if (auth === 'unauthenticated') return <AdminLogin onLoggedIn={() => setAuth('authenticated')} />

  return (
    <AdminLayout onLogout={() => setAuth('unauthenticated')}>
      <Routes>
        <Route index element={<Navigate to="sessions" replace />} />
        <Route path="sessions" element={<SessionsList />} />
        <Route path="sessions/:sessionId" element={<SessionDetail />} />
        <Route path="live/:sessionId" element={<LiveView />} />
        <Route path="session" element={<SessionViewer />} />
        <Route path="event-log" element={<SessionViewer />} />
        <Route path="distributions" element={<SignalDistributions />} />
      </Routes>
    </AdminLayout>
  )
}
