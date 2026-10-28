export const STORAGE_KEY = 'huskypoll-theme'

export function initializeTheme() {
  let theme
  try { theme = localStorage.getItem(STORAGE_KEY) } catch { /* Storage may be disabled. */ }
  if (theme !== 'light' && theme !== 'dark') {
    theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  document.documentElement.dataset.theme = theme
  return theme
}

