export const STORAGE_KEY = 'huskypoll-theme'
const CHANGE_EVENT = 'huskypoll-theme-change'
let mode = 'auto'
let theme = 'light'
let initialized = false
let loginPage = false

export function normalizeThemeMode(value) {
  return value === 'light' || value === 'dark' ? value : 'auto'
}

/** Use the device's local clock, without needing location permissions. */
export function resolveTheme(preference, now = new Date()) {
  if (preference === 'light' || preference === 'dark') return preference
  return now.getHours() >= 7 && now.getHours() < 19 ? 'light' : 'dark'
}

function refreshTheme() {
  const next = loginPage ? 'light' : resolveTheme(mode)
  const changed = next !== theme
  theme = next
  document.documentElement.dataset.theme = theme
  if (changed) window.dispatchEvent(new Event(CHANGE_EVENT))
}

function readPreference() {
  try { mode = normalizeThemeMode(localStorage.getItem(STORAGE_KEY)) } catch { /* Keep the in-memory choice if storage is disabled. */ }
}

export function setThemeMode(value) {
  mode = normalizeThemeMode(value)
  try { localStorage.setItem(STORAGE_KEY, mode) } catch { /* Still works for this visit. */ }
  refreshTheme()
  window.dispatchEvent(new Event(CHANGE_EVENT))
}

export function getThemeSnapshot() {
  return `${mode}:${theme}`
}

export function subscribeTheme(listener) {
  window.addEventListener(CHANGE_EVENT, listener)
  return () => window.removeEventListener(CHANGE_EVENT, listener)
}

export function setLoginPage(active) {
  loginPage = active
  refreshTheme()
}

export function initializeTheme({ loginPage: initialLoginPage = false } = {}) {
  loginPage = initialLoginPage
  readPreference()
  refreshTheme()
  if (!initialized) {
    initialized = true
    // Check boundaries while open, plus waking from sleep/background and cross-tab choices.
    window.setInterval(refreshTheme, 30_000)
    window.addEventListener('focus', refreshTheme)
    document.addEventListener('visibilitychange', refreshTheme)
    window.addEventListener('storage', (event) => {
      if (event.key === STORAGE_KEY || event.key === null) {
        readPreference()
        refreshTheme()
        window.dispatchEvent(new Event(CHANGE_EVENT))
      }
    })
  }
  return theme
}
