import { useCallback, useEffect, useMemo, useState } from 'react'
import { Navigate, useLocation } from 'react-router'
import { api } from '../api.js'
import { AuthContext, useAuth } from '../hooks.js'
import { Loading } from './ui.jsx'

/** Loads GET /me once and shares the logged-in user with every page. */
export function AuthProvider({ children }) {
  // user: undefined = still checking, null = nobody logged in
  const [user, setUser] = useState(undefined)
  const [error, setError] = useState(null)

  const refresh = useCallback(async () => {
    try {
      setUser(await api.me())
      setError(null)
    } catch (err) {
      setUser(null)
      if (err.status !== 401) setError(err)
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loads once on start
    refresh()
  }, [refresh])

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } finally {
      setUser(null)
    }
  }, [])

  const value = useMemo(() => ({ user, setUser, refresh, logout, error }), [user, refresh, logout, error])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

/** Pages inside this need a login; others are sent to the login page and come back afterwards. */
export function RequireLogin({ children }) {
  const { user } = useAuth()
  const location = useLocation()
  if (user === undefined) {
    return (
      <main className="page">
        <Loading />
      </main>
    )
  }
  if (user === null) {
    const next = location.pathname + location.search
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }
  return children
}
