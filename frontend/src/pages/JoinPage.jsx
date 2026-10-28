// Students reach a poll by typing its code or scanning the QR code (which opens /join/CODE).
// A poll can have several questions: students keep the page open and each question
// appears in turn as the instructor opens it.
import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router'
import { AnswerForm, AnswerKey, Mark, QuestionBody, ResultsView } from '../components/PollParts.jsx'
import { answerText } from '../format.js'
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

/** Results the instructor shared for a closed question. */
function SharedResults({ poll, liveResults }) {
  const fetched = useApi(poll.show_results && !liveResults ? `/polls/${poll.id}/results` : null)
  const results = liveResults ?? fetched.data
  if (!results) return null
  return (
    <div style={{ marginTop: 16 }}>
      <h3>Class results</h3>
      <ResultsView question={poll.question} results={results} />
    </div>
  )
}

/**
 * Follows the poll live: shows the open question, then (after the instructor closes it)
 * the student's mark and any shared results, then the next question when it opens.
 * The instructor's poll can have several questions; students see one at a time.
 */
function LectureQuestions({ poll }) {
  const asked = useApi(`/courses/${poll.course_id}/polls?session_id=${poll.session_id}`)
  // people who joined with the code but aren't on the roster can't open the course
  const course = useApi(`/courses/${poll.course_id}`)
  const onRoster = Boolean(course.data)
  const [shared, setShared] = useState({}) // poll_id -> results the instructor showed
  const { reload } = asked

  useEffect(
    () =>
      connectCourse(poll.course_id, (msg) => {
        if (msg.type === 'poll_opened' || msg.type === 'poll_closed') reload()
        if (msg.type === 'results') setShared((r) => ({ ...r, [msg.results.poll_id]: msg.results }))
      }),
    [poll.course_id, reload],
  )

  if (asked.error) return <ErrorBox error={asked.error} />
  if (!asked.data) return <Loading />
  // this poll's questions so far (students never see the ones still to come)
  const questions = asked.data.filter((p) => p.position >= poll.position).sort((a, b) => a.position - b.position)
  const current = questions.find((p) => p.status === 'open')
  const last = [...questions].reverse().find((p) => p.status === 'closed')
  const number = (p) => questions.indexOf(p) + 1

  if (current) {
    return (
      <div className="card" key={current.id}>
        <div className="card-head">
          <h2>Question {number(current)}</h2>
          <span className="badge badge-open">● Open</span>
        </div>
        <AnswerForm key={current.id} poll={current} />
      </div>
    )
  }
  if (!last) return <Loading />
  return (
    <>
      <div className="card">
        <div className="card-head">
          <h2>Question {number(last)} has closed</h2>
          <Mark response={last.my_response} />
        </div>
        <QuestionBody question={last.question} />
        {last.my_response && (
          <p>
            Your answer: <strong>{String(answerText(last.question, last.my_response))}</strong>
          </p>
        )}
        {(last.show_results || shared[last.id]) && (
          <>
            <SharedResults poll={last} liveResults={shared[last.id]} />
            <div style={{ marginTop: 12 }}>
              <AnswerKey question={last.question} />
            </div>
          </>
        )}
      </div>
      <div className="alert alert-info">
        Waiting for your instructor. If there&apos;s another question it will appear here. Your answers are saved
        {onRoster ? (
          <>
            , and you can find them later in your <Link to={`/courses/${poll.course_id}`}>course history</Link>.
          </>
        ) : (
          '.'
        )}
      </div>
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
    return <Navigate to={`/polls/${poll.id}`} replace />
  }
  return <LectureQuestions poll={poll} />
}

export default function JoinPage() {
  const { code } = useParams()
  return <main className="page page-narrow">{code ? <JoinedPoll key={code} code={code} /> : <CodeForm />}</main>
}
