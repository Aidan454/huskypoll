import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeThemeMode, resolveTheme } from '../src/theme.js'

const at = (hour, minute = 0) => new Date(2026, 10, 5, hour, minute)

test('automatic mode switches at local 7 a.m. and 7 p.m. boundaries', () => {
  for (const [hour, minute, expected] of [[0, 0, 'dark'], [6, 59, 'dark'], [7, 0, 'light'],
    [12, 0, 'light'], [18, 59, 'light'], [19, 0, 'dark'], [23, 59, 'dark']]) {
    assert.equal(resolveTheme('auto', at(hour, minute)), expected)
  }
})

test('manual light and dark choices override time of day', () => {
  assert.equal(resolveTheme('light', at(23)), 'light')
  assert.equal(resolveTheme('dark', at(12)), 'dark')
})

test('missing or invalid stored preferences default to automatic', () => {
  for (const value of [null, undefined, '', 'system', 'auto', 'invalid']) {
    assert.equal(normalizeThemeMode(value), 'auto')
  }
  assert.equal(normalizeThemeMode('dark'), 'dark')
  assert.equal(normalizeThemeMode('light'), 'light')
})

test('open pages refresh after time changes and synchronize saved choices', async () => {
  const OriginalDate = globalThis.Date
  let currentHour = 18
  globalThis.Date = class extends OriginalDate {
    constructor(...args) { super(...(args.length ? args : [2026, 10, 5, currentHour, 0])) }
  }
  const page = new EventTarget()
  page.documentElement = { dataset: {} }
  const browser = new EventTarget()
  let tick
  browser.setInterval = (fn) => { tick = fn }
  const storage = new Map()
  const originals = Object.fromEntries(['window', 'document', 'localStorage'].map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  Object.defineProperties(globalThis, {
    window: { configurable: true, value: browser }, document: { configurable: true, value: page },
    localStorage: { configurable: true, value: { getItem: (key) => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) } },
  })
  try {
    const controller = await import('../src/theme.js?controller-test')
    assert.equal(controller.initializeTheme(), 'light')
    currentHour = 19
    tick()
    assert.equal(page.documentElement.dataset.theme, 'dark')
    controller.setThemeMode('light')
    tick()
    assert.equal(page.documentElement.dataset.theme, 'light')
    assert.equal(storage.get(controller.STORAGE_KEY), 'light')
    controller.setThemeMode('auto')
    assert.equal(page.documentElement.dataset.theme, 'dark')
    currentHour = 7
    page.dispatchEvent(new Event('visibilitychange'))
    assert.equal(page.documentElement.dataset.theme, 'light')
    storage.set(controller.STORAGE_KEY, 'dark')
    const event = new Event('storage')
    Object.defineProperty(event, 'key', { value: controller.STORAGE_KEY })
    browser.dispatchEvent(event)
    assert.equal(controller.getThemeSnapshot(), 'dark:dark')
    controller.setLoginPage(true)
    assert.equal(page.documentElement.dataset.theme, 'light')
    tick()
    assert.equal(page.documentElement.dataset.theme, 'light')
    assert.equal(storage.get(controller.STORAGE_KEY), 'dark')
    controller.setLoginPage(false)
    assert.equal(page.documentElement.dataset.theme, 'dark')
    controller.setThemeMode('auto')
    currentHour = 23
    controller.setLoginPage(true)
    tick()
    assert.equal(page.documentElement.dataset.theme, 'light')
    controller.setLoginPage(false)
    assert.equal(page.documentElement.dataset.theme, 'dark')
    assert.equal(controller.initializeTheme({ loginPage: true }), 'light')
  } finally {
    globalThis.Date = OriginalDate
    for (const [key, descriptor] of Object.entries(originals)) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor)
      else delete globalThis[key]
    }
  }
})
