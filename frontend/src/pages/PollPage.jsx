// One poll. Instructors get the classroom view (code, QR, live results, close);
// students get the answer form, or their mark once it's closed.
import { createContext, useContext, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link, useParams } from 'react-router'
import { api } from '../api.js'
import PollControls from '../components/PollControls/PollControls.jsx'
import { AddTimeButton, AnswerForm, AnswerKey, Mark, PollCountdown, QuestionBody, ResultsView } from '../components/PollParts.jsx'
import QuestionEditor from '../components/QuestionEditor.jsx'
import { ErrorBox, Loaded, Loading, Modal, StatusBadge } from '../components/ui.jsx'
import { answerText, formatDateTime, pct, QUESTION_TYPE_SHORT } from '../format.js'
import { useAction, useApi } from '../hooks.js'
import { connectCourse } from '../live.js'

// The instructor's sidebar content lives in InstructorPoll (it needs the live
// results and actions), so it portals into the rail rendered by PollFrame.
const PollSidebar = createContext(null)

// Fixed navy rail on wide screens; hidden below 900px so phones keep the
// centered poll card and the top bar's drawer. `nav` (the course breadcrumb)
// sits at the top of the rail and falls back to the top of the page on phones.
function PollFrame({ nav, children }) {
  const [sidebarSlot, setSidebarSlot] = useState(null)
  return (
    <PollSidebar.Provider value={sidebarSlot}>
      <div className="poll-shell">
        <div className="poll-sidebar">
          {nav}
          <div className="poll-sidebar-slot" ref={setSidebarSlot} />
        </div>
        <main className="page">
          {nav && <div className="poll-mobile-nav">{nav}</div>}
          {children}
        </main>
      </div>
    </PollSidebar.Provider>
  )
}

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
  const sidebarEl = useContext(PollSidebar)
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
  const [addTime, addingTime, addTimeError] = useAction(async (seconds) => {
    setPoll(await api.post(`/polls/${poll.id}/extend`, { seconds }))
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

  // Timer, join code/QR and the live answer count; PollControls sit at the bottom.
  const sidebar = (
    <>
      <div className="poll-sidebar-info">
        {(poll.seconds_remaining !== null || poll.duration_seconds !== null) && (
          <div className="poll-sidebar-timer">
            <PollCountdown seconds={poll.seconds_remaining} />
            {poll.duration_seconds !== null && (
              <AddTimeButton
                onClick={() => addTime(30)}
                busy={addingTime}
                title={poll.status === 'closed' ? 'Reopen with 30 more seconds' : 'Add 30 seconds'}
              />
            )}
          </div>
        )}
        {open && poll.access_code && (
          <div className="poll-sidebar-code">
            <img className="qr" src={api.qrUrl(poll.id)} alt={`QR code for ${poll.join_url}`} />
            <div className="code-big">{poll.access_code}</div>
          </div>
        )}
        <div>
          <div className="stat">{r?.responses ?? '–'}</div>
          <div className="stat-label">Answers</div>
        </div>
      </div>
      <div className="poll-sidebar-controls">
        <PollControls
          isOpen={open}
          onToggleOpen={() => (open ? close() : reopen())}
          busy={sharing || closing || reopening}
        />
      </div>
    </>
  )

  return (
    <>
      {sidebarEl && createPortal(sidebar, sidebarEl)}
      <div className="present">
        <div>
          <div className="card-head">
            <div className="row">
              <StatusBadge status={poll.status} />
              <span className="badge">{QUESTION_TYPE_SHORT[q.type]}</span>
            </div>
            <div className="row">
              <button type="button" className="btn btn-sm" onClick={() => toggleShare()} disabled={sharing}>
                {poll.show_results ? 'Hide results from students' : 'Show results to students'}
              </button>
            </div>
          </div>
          <ErrorBox error={shareError || closeError || reopenError || addTimeError} />
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
          <div className="stats">
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
      <div className="page-narrow" style={{ margin: '0 auto' }}>
        <div className="card-head">
          <StatusBadge status={poll.status} />
          <PollCountdown seconds={poll.seconds_remaining} onExpire={() => setExpired(true)} />
        </div>
        <AnswerForm poll={poll} expired={expired} />
      </div>
    )
  }
  return (
    <div className="page-narrow" style={{ margin: '0 auto' }}>
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
      <PollFrame>
        <ErrorBox error={poll.error} />
      </PollFrame>
    )
  }
  if (!poll.data || !course.data) {
    return (
      <PollFrame>
        <ErrorBox error={course.error} />
        {!course.error && <Loading />}
      </PollFrame>
    )
  }
  const c = course.data
  const staff = ['owner', 'instructor', 'ta'].includes(c.my_role)
  const nav = (
    <nav className="crumbs poll-nav" aria-label="Breadcrumb">
      <Link to="/courses">Courses</Link> / <Link to={`/courses/${c.id}`}>{`${c.subject} ${c.catalog}`}</Link> / Poll
    </nav>
  )
  return (
    <PollFrame nav={nav}>
      {staff ? (
        <InstructorPoll poll={poll.data} setPoll={poll.setData} reloadPoll={poll.reload} />
      ) : (
        <StudentPoll poll={poll.data} reloadPoll={poll.reload} />
      )}
    </PollFrame>
  )
}
