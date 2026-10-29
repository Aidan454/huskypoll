import { useState } from 'react'
import { useNavigate } from 'react-router'
import { api } from '../../api.js'
import { DEV_LOGIN } from '../../config.js'
import { ErrorBox, Field } from '../ui.jsx'
import { useAction, useAuth } from '../../hooks.js'
import styles from './LoginCard.module.css'

const DEMO_ACCOUNTS = [
  { label: 'Instructor', net_id: 'prf00001' },
  { label: 'TA', net_id: 'tas00001' },
  { label: 'Admin', net_id: 'adm00001' },
  { label: 'Student', net_id: 'ccb23028' },
]

export default function LoginCard2({ next = '/courses' }) {
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const [netId, setNetId] = useState('')
  const [role, setRole] = useState('')

  const [devLogin, busy, error] = useAction(async (id, asRole) => {
    const net_id = id.trim().toLowerCase()
    const me = await api.devLogin({ email: `${net_id}@uconn.edu`, net_id, role: asRole || undefined })
    setUser(me)
    navigate(next, { replace: true })
  })

  return (
    <div className={styles.card}>
      <div className={styles.titleWrap}>
        <h1 className={styles.title}>
          Husky<span style={{ color: 'var(--blue)' }}>Poll</span>
        </h1>
        <p className={styles.subtitle}>Live polls for UConn classes</p>
      </div>

      {/* No href yet */}
      <a className="btn btn-primary btn-lg btn-block">
        Log in with UConn email
      </a>

      <a className="btn btn-primary btn-lg btn-block" href={api.loginUrl(next)}>
        Log in with UConn NetID
      </a>

      {DEV_LOGIN && (
        <>
          <div className={styles.divider}>Developer login</div>
          <ErrorBox error={error?.status === 404 ? new Error('Developer login is turned off on this server.') : error} />
          <div className={styles.presetGrid}>
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
  )
}
