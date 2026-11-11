export const STORAGE_KEY = 'huskypoll-theme'
const CHANGE_EVENT = 'huskypoll-theme-change'
let mode = 'light'
let theme = 'light'
let initialized = false
let loginPage = false

export function normalizeThemeMode(value) {
  return value === 'dark' ? 'dark' : 'light'
}

function refreshTheme() {
  const next = loginPage ? 'light' : mode
  const changed = next !== theme
  theme = next
  document.documentElement.dataset.theme = theme
  if (changed) window.dispatchEvent(new Event(CHANGE_EVENT))
}

function readPreference() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    mode = stored === 'light' || stored === 'dark' ? stored
      : window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  } catch { /* Keep the in-memory choice if storage is disabled. */ }
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
