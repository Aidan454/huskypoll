// Pieces shared by the instructor's live view, the student's answer page and history.
import { useState } from 'react'
import { api } from '../api.js'
import { answerText, formatTime, pct } from '../format.js'
import { useAction } from '../hooks.js'
import { ErrorBox } from './ui.jsx'
import Markdown from './Markdown.jsx'

export function QuestionBody({ question }) {
  return (
    <>
      {question.body_md && (
        <div className="question-body">
          <Markdown text={question.body_md} />
        </div>
      )}
      {question.body_media_url && <img src={question.body_media_url} alt="Question" className="question-img" />}
    </>
  )
}

/** Vote counts as horizontal bars (multiple choice) or a list of answers (text/number). */
export function ResultsView({ question, results, revealCorrect = true }) {
  if (!results) return <p className="muted">No results yet.</p>
  const total = results.responses
  if (results.options) {
    const byId = Object.fromEntries(results.options.map((o) => [o.option_id, o.votes]))
    return (
      <div className="bars">
        {question.options.map((o) => {
          const votes = byId[o.id] ?? 0
          const correct = revealCorrect && o.is_correct
          return (
            <div key={o.id}>
              <div className="bar-label">
                <Markdown text={o.text_md} />
              </div>
              <div className="bar-row">
                <span className="letter" style={correct ? { background: 'var(--green)', color: 'var(--on-accent)' } : undefined}>
                  {o.letter}
                </span>
                <div className="bar-track">
                  <div className={correct ? 'bar-fill correct' : 'bar-fill'} style={{ width: `${pct(votes, total)}%` }} />
                </div>
                <span className="bar-count">
                  {votes} · {pct(votes, total)}%
                </span>
              </div>
            </div>
          )
        })}
      </div>
    )
  }
  if (!results.answers?.length) return <p className="muted">No answers yet.</p>
  return (
    <table>
      <thead>
        <tr>
          <th>Answer</th>
          <th className="num">Students</th>
        </tr>
      </thead>
      <tbody>
        {results.answers.map((a) => (
          <tr key={String(a.answer)}>
            <td>{a.answer === null ? <span className="muted">(blank)</span> : String(a.answer)}</td>
            <td className="num">{a.count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** The answer key, for closed polls (students) or instructors. */
export function AnswerKey({ question }) {
  let key = null
  if (question.type === 'mc_single' || question.type === 'mc_multi') {
    const right = question.options.filter((o) => o.is_correct).map((o) => o.letter)
    if (right.length) key = right.join(', ')
  } else if (question.type === 'free_text' && question.text_answer) {
    key = question.text_answer
  } else if (question.type === 'numeric' && question.numeric_answer !== null && question.numeric_answer !== undefined) {
    key = `${question.numeric_answer}${question.numeric_tolerance ? ` ± ${question.numeric_tolerance}` : ''}`
  }
  if (!key && !question.explanation_md && !question.explanation_media_url) return null
  return (
    <div className="alert alert-info">
      {key && (
        <p>
          <strong>Answer:</strong> {key}
        </p>
      )}
      {question.explanation_md && (
        <p style={{ margin: 0 }}>
          <Markdown text={question.explanation_md} />
        </p>
      )}
      {question.explanation_media_url && (
        <img src={question.explanation_media_url} alt="Explanation" className="question-img" style={{ marginTop: 8 }} />
      )}
    </div>
  )
}

/** Mark for a student's answer once the poll is closed. */
export function Mark({ response }) {
  if (!response) return <span className="badge badge-red">Not answered</span>
  if (response.is_correct === true) return <span className="badge badge-open">✓ Correct</span>
  if (response.is_correct === false) return <span className="badge badge-red">✗ Incorrect</span>
  return <span className="badge badge-blue">Answered</span>
}

/**
 * A student answers an open poll. Re-submitting while the poll is open changes the answer.
 * `poll` is a PollOut (with my_response); onSaved(myResponse) after each save.
 */
export function AnswerForm({ poll, onSaved }) {
  const q = poll.question
  const mine = poll.my_response
  const [optionIds, setOptionIds] = useState(mine?.option_ids ?? [])
  const [text, setText] = useState(mine?.text_answer ?? '')
  const [num, setNum] = useState(mine?.numeric_answer ?? '')
  const [saved, setSaved] = useState(mine ?? null)

  const [submit, busy, error] = useAction(async () => {
    const body = { option_ids: [] }
    if (q.type === 'mc_single' || q.type === 'mc_multi') body.option_ids = optionIds
    if (q.type === 'free_text') body.text_answer = text
    if (q.type === 'numeric') body.numeric_answer = num === '' ? null : Number(num)
    const r = await api.post(`/polls/${poll.id}/responses`, body)
    setSaved(r)
    onSaved?.(r)
  })

  function toggle(id) {
    if (q.type === 'mc_single') setOptionIds([id])
    else setOptionIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]))
  }

  const empty =
    (q.type.startsWith('mc') && optionIds.length === 0) ||
    (q.type === 'free_text' && !text.trim()) ||
    (q.type === 'numeric' && (num === '' || Number.isNaN(Number(num))))

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
    >
      <QuestionBody question={q} />
      {q.type === 'mc_multi' && <p className="small muted">Choose all that apply.</p>}
      {q.type.startsWith('mc') &&
        q.options.map((o) => (
          <label key={o.id} className={optionIds.includes(o.id) ? 'choice selected' : 'choice'}>
            <input
              type={q.type === 'mc_single' ? 'radio' : 'checkbox'}
              name="choice"
              checked={optionIds.includes(o.id)}
              onChange={() => toggle(o.id)}
            />
            <span className="letter">{o.letter}</span>
            <span className="grow">
              <Markdown text={o.text_md} />
              {o.media_url && <img src={o.media_url} alt="" className="question-img" style={{ display: 'block', marginTop: 6 }} />}
            </span>
          </label>
        ))}
      {q.type === 'free_text' && (
        <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} placeholder="Your answer" />
      )}
      {q.type === 'numeric' && (
        <input type="number" step="any" value={num} onChange={(e) => setNum(e.target.value)} placeholder="Your answer" />
      )}
      <ErrorBox error={error} />
      {saved && !error && (
        <div className="alert alert-success" style={{ marginTop: 12 }}>
          ✓ Answer received at {formatTime(saved.updated_at)}
          {answerText(q, saved) !== '' && <> ({String(answerText(q, saved))})</>}. You can change it until the poll closes.
        </div>
      )}
      <button type="submit" className="btn btn-primary btn-lg btn-block" disabled={busy || empty} style={{ marginTop: 12 }}>
        {busy ? 'Sending…' : saved ? 'Update answer' : 'Submit answer'}
      </button>
    </form>
  )
}
