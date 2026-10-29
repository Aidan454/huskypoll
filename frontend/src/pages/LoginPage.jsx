import { Navigate, useSearchParams } from 'react-router'
import LoginCard2 from '../components/LoginCard/LoginCard.jsx'
import { useAuth } from '../hooks.js'

function safeNext(next) {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : '/courses'
}

export default function LoginPage() {
  const { user } = useAuth()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))

  if (user) return <Navigate to={next} replace />

  return (
    <main className="login-wrap">
      <LoginCard2 next={next} />
    </main>
  )
}
