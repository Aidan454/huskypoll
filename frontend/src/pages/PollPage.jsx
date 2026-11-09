// One poll. Instructors get the classroom view (code, QR, live results, close);
// students get the answer form, or their mark once it's closed.
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { api } from '../api.js'
import { AddTimeButton, AnswerForm, AnswerKey, Mark, PollCountdown, QuestionBody, ResultsView } from '../components/PollParts.jsx'
import QuestionEditor from '../components/QuestionEditor.jsx'
import { ErrorBox, Loaded, Loading, Modal, StatusBadge } from '../components/ui.jsx'
import { answerText, formatDateTime, pct, QUESTION_TYPE_SHORT } from '../format.js'
import { useAction, useApi } from '../hooks.js'
import { connectCourse } from '../live.js'
import PollControls from '../components/PollControls/PollControls.jsx'

function InstructorPoll({ poll, setPoll, reloadPoll }) {
  const results = useApi(`/polls/${poll.id}/results`)
  const { setData: setResults } = results
  const [showResponses, setShowResponses] = useState(false)
  const [editingKey, setEditingKey] = useState(false)
  const [notice, setNotice] = useState(null)
  const q = poll.question

  useEffect(
    () =>
      connectCourse(poll.course_id, (msg) => {
        if (msg.type === 'results' && msg.results.poll_id === poll.id) setResults(msg.results)
        if (msg.type === 'poll_closed' && msg.poll_id === poll.id) reloadPoll()
        if (msg.type === 'poll_extended' && msg.poll_id === poll.id) reloadPoll()
        if (msg.type === 'poll_opened' && msg.poll.id === poll.id) reloadPoll()
      }),
    [poll.course_id, poll.id, setResults, reloadPoll],
  )

  const [close, , closeError] = useAction(async () => {
    setPoll(await api.post(`/polls/${poll.id}/close`))
    results.reload()
  })
  const [toggleOpen, togglingOpen, toggleOpenError] = useAction(async () => {
    let action = 'reopen'
    if (poll.status === 'open') action = 'close'
    else if (poll.status === 'draft') action = 'open'
    setPoll(await api.post(`/polls/${poll.id}/${action}`))
    results.reload()
  })
  const [addTime, addingTime, addTimeError] = useAction(async (seconds) => {
    setPoll(await api.post(`/polls/${poll.id}/extend`, { seconds }))
    results.reload()
  })

  const r = results.data
  const open = poll.status === 'open'

  return (
    <>
      <div className="present">
        <div className="card">
          <div className="card-head">
            <div className="row">
              <StatusBadge status={poll.status} />
              <span className="badge">{QUESTION_TYPE_SHORT[q.type]}</span>
              <PollCountdown seconds={poll.seconds_remaining} />
              {poll.duration_seconds !== null && (
                <AddTimeButton
                  onClick={() => addTime(30)}
                  busy={addingTime}
                  title={poll.status === 'closed' ? 'Reopen with 30 more seconds' : 'Add 30 seconds'}
                />
              )}
            </div>
            <div className="row">
              <button type="button" className="btn btn-sm" onClick={() => toggleShare()} disabled={sharing}>
                {poll.show_results ? 'Hide results from students' : 'Show results to students'}
              </button>
              {open && (
                <button type="button" className="btn btn-sm btn-solid-danger" onClick={() => close()} disabled={closing}>
                  {closing ? 'Closing…' : 'Close poll'}
                </button>
              )}
              {poll.status === 'closed' && (
                <button
                  type="button"
                  className="btn btn-sm btn-primary"
                  onClick={() => reopen()}
                  disabled={reopening}
                  title="Let students answer again. Earlier answers are kept and can be changed."
                >
                  {reopening ? 'Reopening…' : 'Reopen poll'}
                </button>
              )}
            </div>
          </div>
          <ErrorBox error={closeError || toggleOpenError || addTimeError} />
          {showResults && (
            <>
              <h3 style={{ marginTop: 8 }}>Results</h3>
              {results.error ? <ErrorBox error={results.error} /> : <ResultsView question={q} results={r} />}
            </>
          )}
          {!open && (
            <div style={{ marginTop: 16 }}>
              <AnswerKey question={q} />
            </div>
          )}
        </div>

        <div className="card code-box">
          {open && poll.access_code && (
            <>
              <PollCountdown seconds={poll.seconds_remaining} onExpire={() => setTimeUp(true)} />
              <img className="qr" src={api.qrUrl(poll.id)} alt={`QR code for ${poll.join_url}`} />
              <div className="stat-label">Join Code</div>
              <div className="code-big">{poll.access_code}</div>
              <div className="stat">{r?.responses ?? '–'}</div>
              <div className="stat-label">Answers</div>
            </>
          )}
          <PollControls
            showResults={showResults}
            onToggleResults={() => setShowResults((shown) => !shown)}
            isOpen={open}
            onToggleOpen={() => toggleOpen()}
            busy={togglingOpen}
          />
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h2>Individual answers</h2>
          <button type="button" className="btn btn-sm" onClick={() => setShowResponses(!showResponses)}>
            {showResponses ? 'Hide' : 'Show'}
          </button>
        </div>
        {showResponses && <ResponsesTable key={`${r?.responses}-${poll.status}`} poll={poll} />}
      </div>

      <Modal open={editingKey} onClose={() => setEditingKey(false)} title="Answer key" wide>
        <QuestionEditor
          question={q}
          onSubmit={saveKey}
          busy={savingKey}
          error={keyError}
          submitLabel="Save and re-mark"
          onCancel={() => setEditingKey(false)}
        />
      </Modal>
    </>
  )
}

function StudentPoll({ poll, reloadPoll }) {
  const q = poll.question
  const [expired, setExpired] = useState(false)

  // The instructor may close, reopen or extend this poll while the student is here.
  useEffect(
    () =>
      connectCourse(poll.course_id, (msg) => {
        if (msg.type === 'poll_extended' && msg.poll_id === poll.id) {
          setExpired(false)
          reloadPoll()
        }
        if (msg.type === 'poll_closed' && msg.poll_id === poll.id) {
          if (msg.reason === 'timeout') setExpired(true)
          reloadPoll()
        }
        if (msg.type === 'poll_opened' && msg.poll.id === poll.id) reloadPoll()
      }),
    [poll.course_id, poll.id, reloadPoll],
  )

  if (poll.status === 'open') {
    return (
      <div className="card page-narrow" style={{ margin: '0 auto' }}>
        <div className="card-head">
          <StatusBadge status={poll.status} />
          <PollCountdown seconds={poll.seconds_remaining} onExpire={() => setExpired(true)} />
        </div>
        <AnswerForm poll={poll} expired={expired} />
      </div>
    )
  }
  return (
    <div className="card page-narrow" style={{ margin: '0 auto' }}>
      <div className="card-head">
        <StatusBadge status={poll.status} />
        <Mark response={poll.my_response} />
      </div>
      <QuestionBody question={q} />
      {poll.my_response && (
        <p>
          Your answer: <strong>{String(answerText(q, poll.my_response))}</strong>
        </p>
      )}
      <AnswerKey question={q} />
    </div>
  )
}

export default function PollPage() {
  const { pollId } = useParams()
  const poll = useApi(`/polls/${pollId}`)
  const course = useApi(poll.data ? `/courses/${poll.data.course_id}` : null)

  if (poll.error) {
    return (
      <main className="page">
        <ErrorBox error={poll.error} />
      </main>
    )
  }
  if (!poll.data || !course.data) {
    return (
      <main className="page">
        <ErrorBox error={course.error} />
        {!course.error && <Loading />}
      </main>
    )
  }
  const c = course.data
  const staff = ['owner', 'instructor', 'ta'].includes(c.my_role)
  return (
    <main className="page">
      <div className="crumbs">
        <Link to="/courses">Courses</Link> / <Link to={`/courses/${c.id}`}>{`${c.subject} ${c.catalog}`}</Link> / Poll
      </div>
      {staff ? (
        <InstructorPoll poll={poll.data} setPoll={poll.setData} reloadPoll={poll.reload} />
      ) : (
        <StudentPoll poll={poll.data} reloadPoll={poll.reload} />
      )}
    </main>
  )
}
