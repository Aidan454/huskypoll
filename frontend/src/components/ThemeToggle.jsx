import { useState } from 'react'

import { STORAGE_KEY } from '../theme.js'

export default function ThemeToggle() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'light')

  function toggle() {
    const next = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.dataset.theme = next
    setTheme(next)
    try { localStorage.setItem(STORAGE_KEY, next) } catch { /* The toggle still works without storage. */ }
  }

  return (
    <button
      type="button"
      className="theme-toggle"
      role="switch"
      aria-checked={theme === 'dark'}
      aria-label="Dark mode"
      onClick={toggle}
    >
      <span className="theme-icon" aria-hidden="true">{theme === 'dark' ? '☾' : '☀'}</span>
      {theme === 'dark' ? 'Dark mode' : 'Light mode'}
      <span className="theme-track" aria-hidden="true"><span /></span>
    </button>
  )
}
