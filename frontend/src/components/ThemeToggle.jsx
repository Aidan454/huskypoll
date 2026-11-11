import { useSyncExternalStore } from 'react'
import { getThemeSnapshot, setThemeMode, subscribeTheme } from '../theme.js'

export default function ThemeToggle() {
  const [mode] = useSyncExternalStore(subscribeTheme, getThemeSnapshot).split(':')
  return <button type="button" className="theme-toggle" role="switch" aria-checked={mode === 'dark'}
    aria-label="Dark mode" onClick={() => setThemeMode(mode === 'dark' ? 'light' : 'dark')}>
    <span className={`theme-icon theme-icon-${mode === 'dark' ? 'moon' : 'sun'}`} aria-hidden="true" />
    {mode === 'dark' ? 'Dark mode' : 'Light mode'}
    <span className="theme-track" aria-hidden="true"><span /></span>
  </button>
}
