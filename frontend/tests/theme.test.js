import test from 'node:test'
import assert from 'node:assert/strict'

test('manual toggle persists, login stays light, and no automatic timer is registered', async () => {
  const browser = new EventTarget()
  browser.matchMedia = () => ({ matches: false })
  browser.setInterval = () => assert.fail('Manual appearance must not schedule time-based changes')
  const page = new EventTarget()
  page.documentElement = { dataset: {} }
  const storage = new Map([['huskypoll-theme', 'auto']])
  const originals = Object.fromEntries(['window', 'document', 'localStorage'].map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  Object.defineProperties(globalThis, {
    window: { configurable: true, value: browser }, document: { configurable: true, value: page },
    localStorage: { configurable: true, value: { getItem: (key) => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) } },
  })
  try {
    const theme = await import('../src/theme.js')
    assert.equal(theme.initializeTheme(), 'light')
    theme.setThemeMode('dark')
    assert.equal(page.documentElement.dataset.theme, 'dark')
    assert.equal(storage.get(theme.STORAGE_KEY), 'dark')
    theme.setLoginPage(true)
    assert.equal(page.documentElement.dataset.theme, 'light')
    browser.dispatchEvent(new Event('focus'))
    assert.equal(page.documentElement.dataset.theme, 'light')
    theme.setLoginPage(false)
    assert.equal(page.documentElement.dataset.theme, 'dark')
    theme.setThemeMode('light')
    assert.equal(theme.getThemeSnapshot(), 'light:light')
    storage.set(theme.STORAGE_KEY, 'dark')
    const event = new Event('storage')
    Object.defineProperty(event, 'key', { value: theme.STORAGE_KEY })
    browser.dispatchEvent(event)
    assert.equal(theme.getThemeSnapshot(), 'dark:dark')
    assert.equal(theme.initializeTheme({ loginPage: true }), 'light')
    theme.setLoginPage(false)
    assert.equal(page.documentElement.dataset.theme, 'dark')
  } finally {
    for (const [key, descriptor] of Object.entries(originals)) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor)
      else delete globalThis[key]
    }
  }
})
