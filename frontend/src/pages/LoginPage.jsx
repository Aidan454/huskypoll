import { useState } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router'
import { api } from '../api.js'
import { DEV_LOGIN } from '../config.js'
import { ErrorBox, Field } from '../components/ui.jsx'
import { useAction, useAuth } from '../hooks.js'

// Accounts created by `python -m huskypoll_db seed-demo`, for one-click testing.
const DEMO_ACCOUNTS = [
  { label: 'Instructor', net_id: 'prf00001' },
  { label: 'TA', net_id: 'tas00001' },
  { label: 'Admin', net_id: 'adm00001' },
  { label: 'Student', net_id: 'ccb23028' },
]

function safeNext(next) {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : '/courses'
}

export default function LoginPage() {
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))
  const [netId, setNetId] = useState('')
  const [role, setRole] = useState('')

  const [devLogin, busy, error] = useAction(async (id, asRole) => {
    const net_id = id.trim().toLowerCase()
    const me = await api.devLogin({ email: `${net_id}@uconn.edu`, net_id, role: asRole || undefined })
    setUser(me)
    navigate(next, { replace: true })
  })

  if (user) return <Navigate to={next} replace />

  return (
    <main className="login-wrap">
      <div className="login-card">
        <h1>
          Husky<span style={{ color: 'var(--blue)' }}>Poll</span>
        </h1>
        <p className="subtitle">Live polls for UConn classes</p>

        <a className="btn btn-primary btn-lg btn-block" href={api.loginUrl(next)}>
          Log in with UConn NetID
        </a>

        {DEV_LOGIN && (
          <>
            <div className="divider">Developer login</div>
            <p className="small muted">
              Works only when the backend runs with <code>HUSKYPOLL_DEV_LOGIN=1</code>. The buttons use the demo
              accounts from <code>seed-demo</code>.
            </p>
            <ErrorBox error={error?.status === 404 ? new Error('Developer login is turned off on this server.') : error} />
            <div className="preset-grid">
              {DEMO_ACCOUNTS.map((a) => (
                <button key={a.net_id} type="button" className="btn" disabled={busy} onClick={() => devLogin(a.net_id)}>
                  {a.label}
                </button>
              ))}
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                devLogin(netId, role)
              }}
            >
              <div className="form-row">
                <Field label="NetID">
                  <input value={netId} onChange={(e) => setNetId(e.target.value)} placeholder="abc12345" required />
                </Field>
                <Field label="Role">
                  <select value={role} onChange={(e) => setRole(e.target.value)}>
                    <option value="">Keep current</option>
                    <option value="admin">Admin</option>
                    <option value="instructor">Instructor</option>
                    <option value="ta">TA</option>
                    <option value="student">Student</option>
                    <option value="guest">Guest</option>
                  </select>
                </Field>
              </div>
              <button type="submit" className="btn btn-block" disabled={busy}>
                {busy ? 'Logging in…' : 'Log in as this NetID'}
              </button>
            </form>
          </>
        )}
      </div>
    </main>
  )
}
