import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api } from './api.js'

/** Who is logged in: { user, setUser, refresh, logout }. Provided by <AuthProvider>. */
export const AuthContext = createContext(null)

export function useAuth() {
  return useContext(AuthContext)
}

/**
 * Load `path` from the API (pass null to skip).
 * Returns { data, error, loading, reload, setData }.
 */
export function useApi(path) {
  const [state, setState] = useState({ path: null, data: undefined, error: null })
  const [version, setVersion] = useState(0)

  useEffect(() => {
    if (!path) return
    let cancelled = false
    api.get(path).then(
      (data) => !cancelled && setState({ path, data, error: null }),
      (error) => !cancelled && setState((s) => ({ ...s, path, error })),
    )
    return () => {
      cancelled = true
    }
  }, [path, version])

  const reload = useCallback(() => setVersion((v) => v + 1), [])
  const setData = useCallback(
    (update) => setState((s) => ({ ...s, data: typeof update === 'function' ? update(s.data) : update })),
    [],
  )
  const loading = Boolean(path) && state.path !== path
  return { data: loading ? undefined : state.data, error: loading ? null : state.error, loading, reload, setData }
}

/**
 * Wrap an async action (a button click, a form submit) with busy/error state.
 *   const [save, saving, saveError] = useAction(async () => { ... })
 */
export function useAction(fn) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const run = useCallback(
    async (...args) => {
      setBusy(true)
      setError(null)
      try {
        return await fn(...args)
      } catch (err) {
        setError(err)
        return undefined
      } finally {
        setBusy(false)
      }
    },
    [fn],
  )
  return [run, busy, error, setError]
}
