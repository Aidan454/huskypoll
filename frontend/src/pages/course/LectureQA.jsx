import { useEffect, useState } from 'react'
import './LectureQA.css'
import { Link, useOutletContext, useParams } from 'react-router'
import { api } from '../../api.js'
import { ErrorBox, Loaded } from '../../components/ui.jsx'
import { useAction, useApi } from '../../hooks.js'
import { connectCourse } from '../../live.js'

function MessageMeta({ message }) {
  return <p className="qa-meta"><strong>{message.author_name}</strong>
    <time dateTime={message.created_at}>{new Date(message.created_at).toLocaleString()}</time>
  </p>
}

function MessageForm({ label, buttonLabel, path, onPosted }) {
  const [body, setBody] = useState('')
  const [post, busy, error] = useAction(async () => {
    await api.post(path, { body: body.trim() })
    setBody('')
    onPosted()
  })
  return <form className="stack" onSubmit={(e) => { e.preventDefault(); post() }}>
    <label className="field"><span>{label}</span>
      <textarea rows={3} value={body} onChange={(e) => setBody(e.target.value)}
        maxLength={2000} required disabled={busy} placeholder="Share with everyone in this lecture…" />
    </label>
    <div className="qa-form-actions">
      <small className="muted">Posted with your name · {body.length}/2,000</small>
      <button className="btn btn-primary" disabled={busy || !body.trim()}>{busy ? 'Posting…' : buttonLabel}</button>
    </div>
    <ErrorBox error={error} />
  </form>
}

function Replies({ path, version, archived, onPosted }) {
  const replies = useApi(`${path}/replies`)
  const { reload } = replies
  useEffect(() => { reload() }, [version, reload])
  return <div className="qa-replies">
    <h3>Answers & comments</h3>
    <Loaded state={replies}>{(items) => <>
      {!items.length && <p className="muted">No replies yet. Start the conversation.</p>}
      {items.map((reply) => <div className="qa-reply" key={reply.id}>
        <MessageMeta message={reply} /><p className="qa-body">{reply.body}</p>
      </div>)}
    </>}</Loaded>
    {!archived && <MessageForm label="Your answer or comment" buttonLabel="Post reply" path={`${path}/replies`}
      onPosted={() => { reload(); onPosted() }} />}
  </div>
}

function LectureDiscussion({ course, session }) {
  const path = `/sessions/${session.id}/qa`
  const [beforeId, setBeforeId] = useState(null)
  const [expanded, setExpanded] = useState(null)
  const [version, setVersion] = useState(0)
  const questions = useApi(`${path}${beforeId ? `?before_id=${beforeId}` : ''}`)
  const { reload } = questions
  const archived = Boolean(course.archived_at)

  useEffect(() => connectCourse(course.id, (message) => {
    if (message.type === 'qa_changed' && message.session_id === session.id) {
      reload()
      setVersion((v) => v + 1)
    }
  }, (status) => {
    if (status === 'connected') {
      reload()
      setVersion((v) => v + 1)
    }
  }), [course.id, session.id, reload])

  return <section className="stack qa-page" aria-label="Lecture questions and answers">
    <div><Link to={`/courses/${course.id}/lectures`}>← Back to lectures</Link>
      <h2 style={{ marginTop: 16 }}>{session.title || 'Lecture'} · Q&A</h2>
      <p className="muted">{session.session_date}</p>
      <p className="muted">Questions and replies belong to this lecture. Students and instructors can ask or answer, even when no poll is running.</p>
    </div>
    {archived ? <p className="alert">This course is archived. You can still read its questions and replies.</p>
      : <div className="card"><MessageForm label="Ask the class a question" buttonLabel="Post question" path={path}
        onPosted={() => { setBeforeId(null); reload() }} /></div>}
    <div className="qa-form-actions"><h3>{beforeId ? 'Older questions' : 'Latest questions'}</h3>
      <button className="btn" onClick={reload}>Refresh</button>
    </div>
    <Loaded state={questions}>{(items) => <>
      {!items.length && <p className="muted">{beforeId ? 'No more questions.' : 'No questions yet. Be the first to ask!'}</p>}
      {items.map((question) => <article className="card qa-question" key={question.id}>
        <MessageMeta message={question} /><p className="qa-body">{question.body}</p>
        <button className="btn" aria-expanded={expanded === question.id} aria-controls={`qa-replies-${question.id}`}
          onClick={() => setExpanded(expanded === question.id ? null : question.id)}>
          {expanded === question.id ? 'Hide discussion' : `Answers & comments (${question.reply_count})`}
        </button>
        {expanded === question.id && <div id={`qa-replies-${question.id}`}><Replies path={`${path}/${question.id}`}
          version={version} archived={archived} onPosted={reload} /></div>}
      </article>)}
      <div className="qa-form-actions">
        {beforeId && <button className="btn" onClick={() => { setBeforeId(null); setExpanded(null) }}>Back to latest</button>}
        {items.length === 30 && <button className="btn" onClick={() => { setBeforeId(items.at(-1).id); setExpanded(null) }}>Older questions</button>}
      </div>
    </>}</Loaded>
  </section>
}

export default function LectureQA() {
  const { course } = useOutletContext()
  const { sessionId } = useParams()
  const session = useApi(`/sessions/${sessionId}`)
  return <Loaded state={session}>{(lecture) => lecture.course_id === course.id
    ? <LectureDiscussion key={lecture.id} course={course} session={lecture} />
    : <ErrorBox error="This lecture does not belong to this course." />}</Loaded>
}
