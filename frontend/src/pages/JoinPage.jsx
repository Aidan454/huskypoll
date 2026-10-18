// Students reach a poll by typing its code or scanning the QR code (which opens /join/CODE).
// When an instructor opens several questions together, any of their codes shows all of
// that lecture's open questions on one page.
import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router'
import { AnswerForm } from '../components/PollParts.jsx'
import { ErrorBox, Loading } from '../components/ui.jsx'
import { useApi } from '../hooks.js'
import { connectCourse } from '../live.js'

function CodeForm({ initial = '' }) {
  const navigate = useNavigate()
  const [code, setCode] = useState(initial)
  return (
    <form
      className="card"
      onSubmit={(e) => {
        e.preventDefault()
        if (code.trim()) navigate(`/join/${code.trim().toUpperCase()}`)
      }}
    >
      <h1>Join a poll</h1>
      <p className="muted">Enter the code on your instructor&apos;s screen.</p>
      <input
        className="code-input"
        value={code}
        onChange={(e) => setCode(e.target.value)}
        placeholder="CODE"
        autoFocus
        autoComplete="off"
        maxLength={16}
        aria-label="Poll code"
      />
      <button type="submit" className="btn btn-primary btn-lg btn-block" style={{ marginTop: 12 }} disabled={!code.trim()}>
        Join
      </button>
    </form>
  )
}

/** Every open question in the same lecture as `poll`, kept up to date live. */
function LectureQuestions({ poll }) {
  const open = useApi(`/courses/${poll.course_id}/polls?status=open`)
  const [saved, setSaved] = useState({}) // poll_id -> true once answered on this page
  const { reload } = open

  useEffect(
    () =>
      connectCourse(poll.course_id, (msg) => {
        if (msg.type === 'poll_opened' || msg.type === 'poll_closed') reload()
      }),
    [poll.course_id, reload],
  )

  if (open.error) return <ErrorBox error={open.error} />
  if (!open.data) return <Loading />
  const questions = open.data
    .filter((p) => p.session_id === poll.session_id)
    .sort((a, b) => a.position - b.position)

  if (!questions.length) {
    return (
      <div className="card empty">
        <h2>{Object.keys(saved).length ? 'Thanks, the poll has closed' : 'This poll has closed'}</h2>
        <p>
          Your answers and marks are in your <Link to={`/courses/${poll.course_id}`}>course history</Link>.
        </p>
      </div>
    )
  }
  const answered = questions.filter((p) => p.my_response || saved[p.id]).length
  return (
    <>
      {questions.length > 1 && (
        <div className="alert alert-info">
          {questions.length} questions · {answered} answered. You can change answers until each question closes.
        </div>
      )}
      {questions.map((p, i) => (
        <div className="card" key={p.id}>
          <div className="card-head">
            <h2>{questions.length > 1 ? `Question ${i + 1}` : `Poll ${p.access_code}`}</h2>
            <span className="badge badge-open">● Open</span>
          </div>
          <AnswerForm poll={p} onSaved={() => setSaved((s) => ({ ...s, [p.id]: true }))} />
        </div>
      ))}
    </>
  )
}

function JoinedPoll({ code }) {
  const found = useApi(`/polls/by-code/${encodeURIComponent(code)}`)
  const poll = found.data

  if (found.error) {
    const message =
      found.error.status === 404
        ? `There's no open poll with the code ${code}. Check the code, or the poll may have closed.`
        : found.error.message
    return (
      <>
        <ErrorBox error={new Error(message)} />
        <CodeForm initial={code} />
      </>
    )
  }
  if (!poll) return <Loading />
  if (poll.question.answer_revealed && poll.status === 'open') {
    // instructors and TAs get the classroom view
    return <Navigate to={`/courses/${poll.course_id}/live`} replace />
  }
  return <LectureQuestions poll={poll} />
}

export default function JoinPage() {
  const { code } = useParams()
  return <main className="page page-narrow">{code ? <JoinedPoll key={code} code={code} /> : <CodeForm />}</main>
}
