// Form for writing or editing a question (used by question banks and quick polls).
// Once a question has been polled it is locked: only the answer key and explanation
// can change, and the form shows just those.
import { useState } from 'react'
import { api } from '../api.js'
import { QUESTION_TYPES } from '../format.js'
import { useAction } from '../hooks.js'
import { ErrorBox, Field } from './ui.jsx'

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

function emptyForm() {
  return {
    type: 'mc_single',
    body_md: '',
    options: [
      { text_md: '', is_correct: false },
      { text_md: '', is_correct: false },
      { text_md: '', is_correct: false },
      { text_md: '', is_correct: false },
    ],
    explanation_md: '',
    text_answer: '',
    numeric_answer: '',
    numeric_tolerance: '',
  }
}

function formFromQuestion(q) {
  return {
    type: q.type,
    body_md: q.body_md,
    options: q.options.map((o) => ({ id: o.id, text_md: o.text_md, is_correct: Boolean(o.is_correct) })),
    explanation_md: q.explanation_md ?? '',
    text_answer: q.text_answer ?? '',
    numeric_answer: q.numeric_answer ?? '',
    numeric_tolerance: q.numeric_tolerance ?? '',
  }
}

function ImagePicker({ label, url, onUploaded, onRemove, disabled }) {
  const [upload, busy, error] = useAction(async (file) => {
    const media = await api.upload('/media', file)
    onUploaded(media)
  })
  return (
    <div className="field">
      <span>{label}</span>
      {url && <img src={url} alt="" className="question-img" style={{ display: 'block' }} />}
      {!disabled && (
        <div className="row">
          <input
            type="file"
            accept="image/*"
            disabled={busy}
            onChange={(e) => e.target.files[0] && upload(e.target.files[0])}
          />
          {url && (
            <button type="button" className="btn btn-sm btn-danger" onClick={onRemove}>
              Remove picture
            </button>
          )}
        </div>
      )}
      {busy && <small>Uploading…</small>}
      <ErrorBox error={error} />
    </div>
  )
}

/**
 * Props:
 *   question   existing question to edit (omit to write a new one)
 *   onSubmit(body)  receives the request body for POST /questions or PATCH /questions/{id}
 *   submitLabel, busy, error, onCancel
 *   extra      more form controls shown above the buttons (e.g. "show results" for quick polls)
 */
export default function QuestionEditor({ question, onSubmit, submitLabel = 'Save', busy, error, onCancel, extra }) {
  const locked = Boolean(question?.is_locked)
  const [form, setForm] = useState(() => (question ? formFromQuestion(question) : emptyForm()))
  // undefined = unchanged, null = removed, number = new upload
  const [bodyMedia, setBodyMedia] = useState({ id: undefined, url: question?.body_media_url ?? null })
  const [explMedia, setExplMedia] = useState({ id: undefined, url: question?.explanation_media_url ?? null })
  const [formError, setFormError] = useState(null)

  const isMc = form.type === 'mc_single' || form.type === 'mc_multi'
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  function setOption(i, patch) {
    setForm((f) => {
      let options = f.options.map((o, j) => (j === i ? { ...o, ...patch } : o))
      // single answer: ticking one option clears the others
      if (patch.is_correct && f.type === 'mc_single') {
        options = options.map((o, j) => (j === i ? o : { ...o, is_correct: false }))
      }
      return { ...f, options }
    })
  }

  function changeType(e) {
    const type = e.target.value
    setForm((f) => {
      let options = f.options
      if (type === 'mc_single') {
        const first = options.findIndex((o) => o.is_correct)
        options = options.map((o, j) => ({ ...o, is_correct: j === first }))
      }
      return { ...f, type, options }
    })
  }

  function submit(e) {
    e.preventDefault()
    setFormError(null)
    const body = {}
    if (!locked) {
      const options = isMc ? form.options.filter((o) => o.text_md.trim()) : []
      if (isMc && options.length < 2) {
        setFormError(new Error('Multiple-choice questions need at least two choices.'))
        return
      }
      if (!form.body_md.trim() && !bodyMedia.url) {
        setFormError(new Error('Write the question or add a picture.'))
        return
      }
      body.type = form.type
      body.body_md = form.body_md.trim()
      if (bodyMedia.id !== undefined) body.body_media_id = bodyMedia.id
      if (isMc) body.options = options.map((o) => ({ text_md: o.text_md.trim(), is_correct: o.is_correct }))
      else if (question) body.options = []
    } else if (isMc) {
      body.correct_option_ids = form.options.filter((o) => o.is_correct).map((o) => o.id)
    }
    body.explanation_md = form.explanation_md.trim() || null
    if (explMedia.id !== undefined) body.explanation_media_id = explMedia.id
    if (form.type === 'free_text') body.text_answer = form.text_answer.trim() || null
    if (form.type === 'numeric') {
      body.numeric_answer = form.numeric_answer === '' ? null : Number(form.numeric_answer)
      body.numeric_tolerance = form.numeric_tolerance === '' ? null : Number(form.numeric_tolerance)
    }
    onSubmit(body)
  }

  return (
    <form onSubmit={submit}>
      {locked && (
        <div className="alert alert-info small">
          This question has been polled, so its wording and choices are locked. You can still set the answer key
          and explanation (answers are re-marked). To change the wording, copy the question.
        </div>
      )}
      <Field label="Question type">
        <select value={form.type} onChange={changeType} disabled={locked}>
          {Object.entries(QUESTION_TYPES).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Question">
        <textarea value={form.body_md} onChange={set('body_md')} disabled={locked} placeholder="What is the time complexity of binary search?" />
      </Field>
      <ImagePicker
        label="Picture (optional)"
        url={bodyMedia.url}
        disabled={locked}
        onUploaded={(m) => setBodyMedia({ id: m.id, url: m.url })}
        onRemove={() => setBodyMedia({ id: null, url: null })}
      />

      {isMc && (
        <div className="field">
          <span>Choices — tick the correct {form.type === 'mc_single' ? 'answer' : 'answers'} (optional)</span>
          {form.options.map((o, i) => (
            <div className="option-edit" key={o.id ?? `new-${i}`}>
              <span className="letter">{LETTERS[i] ?? i + 1}</span>
              <input
                value={o.text_md}
                onChange={(e) => setOption(i, { text_md: e.target.value })}
                disabled={locked}
                placeholder={`Choice ${LETTERS[i] ?? i + 1}`}
              />
              <label className="check small">
                <input
                  type={form.type === 'mc_single' ? 'radio' : 'checkbox'}
                  name="correct"
                  checked={o.is_correct}
                  onChange={(e) => setOption(i, { is_correct: e.target.checked })}
                  onClick={(e) => {
                    // let a ticked radio be unticked (no answer key)
                    if (form.type === 'mc_single' && o.is_correct) {
                      e.preventDefault()
                      setOption(i, { is_correct: false })
                    }
                  }}
                />
                Correct
              </label>
              {!locked ? (
                <button
                  type="button"
                  className="btn btn-sm"
                  aria-label={`Remove choice ${LETTERS[i]}`}
                  onClick={() => setForm((f) => ({ ...f, options: f.options.filter((_, j) => j !== i) }))}
                  disabled={form.options.length <= 2}
                >
                  ✕
                </button>
              ) : (
                <span />
              )}
            </div>
          ))}
          {!locked && form.options.length < 26 && (
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => setForm((f) => ({ ...f, options: [...f.options, { text_md: '', is_correct: false }] }))}
            >
              + Add choice
            </button>
          )}
        </div>
      )}

      {form.type === 'free_text' && (
        <Field label="Correct answer (optional)" hint="Marked correct when a student's answer matches, ignoring case.">
          <input value={form.text_answer} onChange={set('text_answer')} />
        </Field>
      )}
      {form.type === 'numeric' && (
        <div className="form-row">
          <Field label="Correct answer (optional)">
            <input type="number" step="any" value={form.numeric_answer} onChange={set('numeric_answer')} />
          </Field>
          <Field label="Tolerance (±)" hint="Optional">
            <input type="number" step="any" min="0" value={form.numeric_tolerance} onChange={set('numeric_tolerance')} />
          </Field>
        </div>
      )}

      <Field label="Explanation (optional)" hint="Students see it after the poll closes.">
        <textarea value={form.explanation_md} onChange={set('explanation_md')} />
      </Field>
      <ImagePicker
        label="Explanation picture (optional)"
        url={explMedia.url}
        onUploaded={(m) => setExplMedia({ id: m.id, url: m.url })}
        onRemove={() => setExplMedia({ id: null, url: null })}
      />

      {extra}
      <ErrorBox error={formError || error} />
      <div className="form-actions">
        {onCancel && (
          <button type="button" className="btn" onClick={onCancel}>
            Cancel
          </button>
        )}
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Saving…' : submitLabel}
        </button>
      </div>
    </form>
  )
}
