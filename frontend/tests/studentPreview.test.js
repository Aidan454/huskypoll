import test from 'node:test'
import assert from 'node:assert/strict'
import { studentPreviewQuestion } from '../src/components/polls/studentPreview.js'

const form = {
  type: 'mc_single', body_md: '  **Question?**  ',
  options: [{ id: 45, text_md: ' A ', is_correct: true }, { text_md: ' ' }, { text_md: 'B', is_correct: false }],
  text_answer: 'secret', numeric_answer: 42, numeric_tolerance: 1,
  explanation_md: 'secret explanation', explanation_media_url: '/private-explanation.png',
}
test('preview whitelists student-visible fields and removes all answer-key information', () => {
  const preview = studentPreviewQuestion(form, '/question.png')
  assert.deepEqual(preview, {
    type: 'mc_single', body_md: '**Question?**', body_media_url: '/question.png',
    options: [{ id: 1, letter: 'A', text_md: 'A' }, { id: 2, letter: 'B', text_md: 'B' }],
  })
  assert.equal(form.options[0].is_correct, true)
  assert.equal(form.options.length, 3)
})
test('both multiple-choice types retain only nonempty choices', () => {
  assert.equal(studentPreviewQuestion({ ...form, type: 'mc_multi' }).options.length, 2)
})
test('text and numeric previews contain no leftover choices, solutions or explanations', () => {
  for (const type of ['free_text', 'numeric']) {
    assert.deepEqual(studentPreviewQuestion({ ...form, type }, null), {
      type, body_md: '**Question?**', body_media_url: null, options: [],
    })
  }
})
