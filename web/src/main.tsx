import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import App from './App.tsx'
import { AdminApp } from './pages/Admin/AdminApp'
import { SessionProvider } from './state/SessionContext'
import './styles/tokens.css'
import './styles/base.css'

// /admin/* is a separate surface, deliberately outside SessionProvider's
// consent gate -- an admin is staff, not a visitor, and none of the
// storefront's own telemetry-consent machinery applies to it (§6.7:
// "never linked from the public site").
function Root() {
  return (
    <Routes>
      <Route path="/admin/*" element={<AdminApp />} />
      <Route
        path="*"
        element={
          <SessionProvider>
            <App />
          </SessionProvider>
        }
      />
    </Routes>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Root />
    </BrowserRouter>
  </StrictMode>,
)
