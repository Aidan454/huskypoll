import test from 'node:test'
import assert from 'node:assert/strict'
import { matchesQuestion, parseTags } from './questionSearch.js'

const question = { type: 'mc_single', body_md: 'Explain binary search', explanation_md: 'Divide the interval',
  text_answer: null, tags: ['Lect 2.3', 'Algorithms'], options: [{ text_md: 'Logarithmic time' }] }

test('search combines words across question, choices, explanation and lecture tags', () => {
  assert.equal(matchesQuestion(question, 'lect 2.3 logarithmic', []), true)
  assert.equal(matchesQuestion(question, 'binary interval', []), true)
  assert.equal(matchesQuestion(question, 'lect 2.4', []), false)
})

test('tag filters are exact, case insensitive and combine with text and type filters', () => {
  assert.equal(matchesQuestion(question, 'search', ['lect 2.3', 'algorithms'], 'mc_single'), true)
  assert.equal(matchesQuestion(question, '', ['Lect 2']), false)
  assert.equal(matchesQuestion(question, '', ['Lect 2.3', 'Missing']), false)
  assert.equal(matchesQuestion(question, '', [], 'numeric'), false)
})

test('tag entry preserves lecture punctuation, normalizes spaces and removes duplicates', () => {
  assert.deepEqual(parseTags(' Lect  2.3, Algorithms, lect 2.3, , Trees '), ['Lect 2.3', 'Algorithms', 'Trees'])
})
