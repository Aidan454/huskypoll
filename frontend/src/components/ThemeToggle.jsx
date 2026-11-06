import { useSyncExternalStore } from 'react'
import { getThemeSnapshot, setThemeMode, subscribeTheme } from '../theme.js'

export default function ThemeToggle() {
  const [mode, theme] = useSyncExternalStore(subscribeTheme, getThemeSnapshot).split(':')
  return (
    <label className="theme-preference">
      <span className="theme-preference-label">
        <span className={`theme-icon theme-icon-${theme === 'dark' ? 'moon' : 'sun'}`} aria-hidden="true" />
        Appearance
      </span>
      <select aria-label="Appearance" value={mode} onChange={(event) => setThemeMode(event.target.value)}>
        <option value="auto">Automatic (time of day)</option>
        <option value="light">Light</option>
        <option value="dark">Dark</option>
      </select>
      <small>Automatic: light 7 a.m.–7 p.m., dark overnight. Uses your local time.</small>
    </label>
  )
}
