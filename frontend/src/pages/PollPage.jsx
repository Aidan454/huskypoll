// One poll. Instructors get the classroom view (code, QR, live results, close);
// students get the answer form, or their mark once it's closed.
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { api } from '../api.js'
import { AnswerForm, AnswerKey, Mark, QuestionBody, ResultsView } from '../components/PollParts.jsx'
import QuestionEditor from '../components/QuestionEditor.jsx'
import { ErrorBox, Loaded, Loading, Modal, StatusBadge } from '../components/ui.jsx'
import { answerText, formatDateTime, pct, QUESTION_TYPE_SHORT } from '../format.js'
import { useAction, useApi } from '../hooks.js'
import { connectCourse } from '../live.js'

function ResponsesTable({ poll }) {
  const rows = useApi(`/polls/${poll.id}/responses`)
  return (
    <Loaded state={rows}>
      {(list) =>
        list.length === 0 ? (
          <p className="muted">No answers yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Answer</th>
                  <th>Mark</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {list.map((r) => (
                  <tr key={r.user.id}>
                    <td>
                      {r.user.display_name} <span className="muted small">{r.user.net_id}</span>{' '}
                      {!r.on_roster && (
                        <span className="badge badge-amber" title="Joined with the code; not counted in grades">
                          Not on roster
                        </span>
                      )}
                    </td>
                    <td>{String(answerText(poll.question, r))}</td>
                    <td>{r.is_correct === null ? <span className="muted">—</span> : r.is_correct ? '✓' : '✗'}</td>
                    <td className="small">{formatDateTime(r.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      }
    </Loaded>
  )
}

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
        if (msg.type === 'poll_opened' && msg.poll.id === poll.id) reloadPoll()
      }),
    [poll.course_id, poll.id, setResults, reloadPoll],
  )

  const [toggleShare, sharing, shareError] = useAction(async () => {
    setPoll(await api.patch(`/polls/${poll.id}`, { show_results: !poll.show_results }))
  })
  const [close, closing, closeError] = useAction(async () => {
    setPoll(await api.post(`/polls/${poll.id}/close`))
    results.reload()
  })
  const [reopen, reopening, reopenError] = useAction(async () => {
    setPoll(await api.post(`/polls/${poll.id}/reopen`))
    setNotice(null)
    results.reload()
  })
  const [saveKey, savingKey, keyError] = useAction(async (body) => {
    const r = await api.patch(`/questions/${q.id}`, body)
    setEditingKey(false)
    setNotice(`Answer key saved. ${r.responses_regraded} answers re-marked.`)
    reloadPoll()
    results.reload()
  })

  const r = results.data
  const open = poll.status === 'open'
  const hasKey =
    q.options.some((o) => o.is_correct) ||
    (q.type === 'free_text' && Boolean(q.text_answer)) ||
    (q.type === 'numeric' && q.numeric_answer !== null && q.numeric_answer !== undefined)

  return (
    <>
      <div className="present">
        <div className="card">
          <div className="card-head">
            <div className="row">
              <StatusBadge status={poll.status} />
              <span className="badge">{QUESTION_TYPE_SHORT[q.type]}</span>
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
          <ErrorBox error={shareError || closeError || reopenError} />
          <QuestionBody question={q} />
          <h3 style={{ marginTop: 8 }}>Results</h3>
          {results.error ? <ErrorBox error={results.error} /> : <ResultsView question={q} results={r} />}
          {!open && (
            <div style={{ marginTop: 16 }}>
              {notice && <div className="alert alert-success">{notice}</div>}
              <AnswerKey question={q} />
              <button type="button" className="btn btn-sm" onClick={() => setEditingKey(true)}>
                Edit answer key / explanation
              </button>
            </div>
          )}
        </div>

        <div>
          {open && poll.access_code && (
            <div className="card code-box">
              <div className="stat-label">Go to {poll.join_url ? new URL(poll.join_url).host : 'HuskyPoll'} and enter</div>
              <div className="code-big">{poll.access_code}</div>
              <img className="qr" src={api.qrUrl(poll.id)} alt={`QR code for ${poll.join_url}`} />
              {poll.join_url && (
                <a className="small" href={poll.join_url} target="_blank" rel="noreferrer">
                  {poll.join_url}
                </a>
              )}
            </div>
          )}
          <div className="stats">
            <div className="card">
              <div className="stat">{r?.responses ?? '–'}</div>
              <div className="stat-label">Answers</div>
            </div>
            <div className="card">
              <div className="stat">{r && hasKey ? `${pct(r.correct, r.responses)}%` : '–'}</div>
              <div className="stat-label">{hasKey ? 'Correct' : 'No answer key'}</div>
            </div>
          </div>
          <p className="small muted" style={{ marginTop: 12 }}>
            Opened {formatDateTime(poll.opened_at)}
            {poll.closed_at && <> · closed {formatDateTime(poll.closed_at)}</>}
          </p>
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

  // The instructor may close or reopen this poll while the student is on the page.
  useEffect(
    () =>
      connectCourse(poll.course_id, (msg) => {
        if ((msg.type === 'poll_closed' && msg.poll_id === poll.id) || (msg.type === 'poll_opened' && msg.poll.id === poll.id))
          reloadPoll()
      }),
    [poll.course_id, poll.id, reloadPoll],
  )

  if (poll.status === 'open') {
    return (
      <div className="card page-narrow" style={{ margin: '0 auto' }}>
        <AnswerForm poll={poll} />
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
