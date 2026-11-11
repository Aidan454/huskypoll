import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { api } from '../../api.js'
import QuestionEditor from '../../components/QuestionEditor.jsx'
import { AddTimeButton, PollCountdown } from '../../components/PollParts.jsx'
import { ErrorBox, Field, Loaded, Loading, Modal, SortSelect, StatusBadge } from '../../components/ui.jsx'
import { formatDate, formatTime, QUESTION_TYPE_SHORT, snippet } from '../../format.js'
import { useAction, useApi, useSortOrder } from '../../hooks.js'
import { connectCourse } from '../../live.js'



export default function InstructorPolls({ course }) {
  const navigate = useNavigate()
  const polls = useApi(`/courses/${course.id}/polls`)
  const sessions = useApi(`/courses/${course.id}/sessions`)
  const [modal, setModal] = useState(null) // 'bank' | 'quick'
  const [order, setOrder] = useSortOrder('polls')
  const { reload: reloadPolls } = polls
  const { reload: reloadSessions } = sessions

  useEffect(
    () =>
      connectCourse(course.id, (msg) => {
        if (msg.type === 'poll_opened' || msg.type === 'poll_closed') {
          reloadPolls()
          reloadSessions()
        }
        if (msg.type === 'poll_extended') reloadPolls()
      }),
    [course.id, reloadPolls, reloadSessions],
  )

  const [closePoll, , closeError] = useAction(async (poll) => {
    await api.post(`/polls/${poll.id}/close`)
    reloadPolls()
  })
  const [reopenPoll, , reopenError] = useAction(async (poll) => {
    await api.post(`/polls/${poll.id}/reopen`)
    navigate(`/polls/${poll.id}`)
  })
  const [extendPoll, extending, extendError] = useAction(async (pollId, seconds) => {
    await api.post(`/polls/${pollId}/extend`, { seconds })
    reloadPolls()
  })

  function opened(list) {
    setModal(null)
    navigate(list.length === 1 ? `/polls/${list[0].id}` : `/courses/${course.id}/live?session=${list[0].session_id}&from=${list[0].position}`)
  }

  if (polls.error || sessions.error) return <ErrorBox error={polls.error || sessions.error} />
  if (!polls.data || !sessions.data) return <Loading />

  // a lecture with queued questions is a poll in progress: link to its step-through screen
  const running = [...new Set(polls.data.filter((p) => p.status === 'draft').map((p) => p.session_id))]
  const live = polls.data.filter((p) => p.status === 'open' && !running.includes(p.session_id))
  const bySession = new Map(sessions.data.map((s) => [s.id, { session: s, polls: [] }]))
  for (const p of polls.data) bySession.get(p.session_id)?.polls.push(p)
  // sessions arrive newest lecture first; "oldest" flips both the lectures and the polls inside each
  const groups = [...bySession.values()].filter((g) => g.polls.length)
  if (order === 'oldest') groups.reverse()
  const byPosition = order === 'oldest' ? (a, b) => a.position - b.position : (a, b) => b.position - a.position

  return (
    <>
      <div className="card">
        <div className="card-head">
          <h2>Start a poll</h2>
          <div className="row">
            <button type="button" className="btn btn-primary" onClick={() => setModal('bank')} disabled={Boolean(course.archived_at)}>
              Open from question bank
            </button>
            <button type="button" className="btn" onClick={() => setModal('quick')} disabled={Boolean(course.archived_at)}>
              Quick poll
            </button>
          </div>
        </div>
        {course.archived_at && <p className="small muted">This course is archived. Unarchive it in Settings to run polls.</p>}
        <ActivePolls course={course} polls={polls.data} running={running} live={live} closePoll={closePoll} extendPoll={extendPoll} extending={extending} />

        <ErrorBox error={closeError || reopenError || extendError} />

      </div>

      <div className="card-head">
        <h2>All polls</h2>
        {groups.length > 0 && <SortSelect value={order} onChange={setOrder} />}
      </div>
      {groups.length === 0 && <div className="card empty">No polls yet.</div>}
      {groups.map(({ session, polls: list }) => (
        <div className="card" key={session.id}>
          <div className="card-head">
            <h3>
              {formatDate(session.session_date)}
              {session.title && <span className="muted"> · {session.title}</span>}
            </h3>
            <span className="small muted">{list.length} {list.length === 1 ? 'poll' : 'polls'}</span>
          </div>
          <ul className="list">
            {[...list].sort(byPosition).map((p) => (
              <li key={p.id}>
                <span className="muted small" style={{ width: 22 }}>
                  {p.position + 1}.
                </span>
                <span className="grow">
                  <Link to={`/polls/${p.id}`}>{snippet(p.question.body_md)}</Link>
                </span>
                <span className="badge">{QUESTION_TYPE_SHORT[p.question.type]}</span>
                <StatusBadge status={p.status} />
                {p.status === 'closed' && !course.archived_at && (
                  <button type="button" className="btn btn-sm" onClick={() => reopenPoll(p)} title="Let students answer again">
                    Reopen
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}

      <Modal open={modal === 'bank'} onClose={() => setModal(null)} title="Open a poll" wide>
        <OpenFromBank course={course} sessions={sessions.data} onOpened={opened} onCancel={() => setModal(null)} />
      </Modal>
      <Modal open={modal === 'quick'} onClose={() => setModal(null)} title="Quick poll" wide>
        <QuickPoll course={course} sessions={sessions.data} onOpened={opened} onCancel={() => setModal(null)} />
      </Modal>
    </>
  )
}
