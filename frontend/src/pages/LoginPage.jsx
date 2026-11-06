import { useLayoutEffect } from 'react'
import { Navigate, useSearchParams } from 'react-router'
import LoginCard2 from '../components/LoginCard/LoginCard.jsx'
import { useAuth } from '../hooks.js'
import { setLoginPage } from '../theme.js'
import classroomPhoto from '../assets/login-classroom.png'

function safeNext(next) {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : '/courses'
}

export default function LoginPage() {
  const { user } = useAuth()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))

  useLayoutEffect(() => {
    setLoginPage(true)
    return () => setLoginPage(false)
  }, [])

  if (user) return <Navigate to={next} replace />

  return (
    <main className="login-shell">
      <div className="login-split">
      <section className="login-photo-panel" aria-label="Classroom community">
        <img className="login-classroom-photo" src={classroomPhoto} alt="Students working together in a university classroom." />
        <div className="login-photo-overlay" />
        <div className="login-photo-brand">UCONN <span>HuskyPoll</span></div>
        <div className="login-photo-caption">
          <p className="login-photo-eyebrow">LEARN TOGETHER</p>
          <h2>Every voice counts.</h2>
          <p>Ask questions. Share ideas. Bring your classroom to life.</p>
        </div>
      </section>
      <section className="login-form-panel" aria-label="Sign in to HuskyPoll">
        <LoginCard2 next={next} />
        <p className="login-form-footer">Built for the UConn classroom.</p>
      </section>
      </div>
    </main>
  )
}
