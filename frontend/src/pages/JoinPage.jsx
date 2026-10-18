// Students reach a poll by typing its code or scanning the QR code (which opens /join/CODE).
import { useEffect, useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router'
import { api } from '../api.js'
import { AnswerForm, AnswerKey, Mark, QuestionBody } from '../components/PollParts.jsx'
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

function JoinedPoll({ code }) {
  const found = useApi(`/polls/by-code/${encodeURIComponent(code)}`)
  const [closed, setClosed] = useState(null) // the poll after it closes
  const poll = found.data

  useEffect(() => {
    if (!poll) return undefined
    return connectCourse(poll.course_id, (msg) => {
      if (msg.type === 'poll_closed' && msg.poll_id === poll.id) {
        api.get(`/polls/${poll.id}`).then(setClosed, () => {})
      }
    })
  }, [poll])

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
    return <Navigate to={`/polls/${poll.id}`} replace />
  }
  if (closed) {
    return (
      <div className="card">
        <div className="card-head">
          <h2>This poll has closed</h2>
          <Mark response={closed.my_response} />
        </div>
        <QuestionBody question={closed.question} />
        <AnswerKey question={closed.question} />
      </div>
    )
  }
  return (
    <div className="card">
      <div className="card-head">
        <h2>Poll {poll.access_code}</h2>
        <span className="badge badge-open">● Open</span>
      </div>
      <AnswerForm poll={poll} />
    </div>
  )
}

export default function JoinPage() {
  const { code } = useParams()
  return <main className="page page-narrow">{code ? <JoinedPoll key={code} code={code} /> : <CodeForm />}</main>
}
