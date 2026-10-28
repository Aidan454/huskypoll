import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api } from '../api.js'
import { ErrorBox, Field, Loaded, Modal } from '../components/ui.jsx'
import { isStaff } from '../format.js'
import { useAction, useApi, useAuth } from '../hooks.js'

/** Name, description and (optional) course for a bank. Shared with the bank page. */
export function BankForm({ initial, onSubmit, busy, error, submitLabel, onCancel }) {
  const courses = useApi('/courses')
  const [name, setName] = useState(initial?.name ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [courseId, setCourseId] = useState(initial?.course_id ?? '')
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit({ name: name.trim(), description: description.trim() || null, course_id: courseId ? Number(courseId) : null })
      }}
    >
      <Field label="Name">
        <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Week 3: Recursion" maxLength={200} />
      </Field>
      <Field label="Description (optional)">
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
      </Field>
      <Field label="Share with a course (optional)" hint="Everyone teaching the course can use the bank's questions.">
        <select value={courseId} onChange={(e) => setCourseId(e.target.value)}>
          <option value="">Just me</option>
          {(courses.data ?? []).filter(isStaff).map((c) => (
            <option key={c.id} value={c.id}>
              {c.code}
            </option>
          ))}
        </select>
      </Field>
      <ErrorBox error={error} />
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

export default function BanksPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const banks = useApi('/banks')
  const courses = useApi('/courses?include_archived=true')
  const [creating, setCreating] = useState(false)
  const courseName = Object.fromEntries((courses.data ?? []).map((c) => [c.id, `${c.subject} ${c.catalog}`]))

  const [create, busy, error] = useAction(async (body) => {
    const bank = await api.post('/banks', body)
    navigate(`/banks/${bank.id}`)
  })

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Question banks</h1>
          <p className="subtitle">Write questions ahead of class, then open them as polls in any of your courses.</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
          + New bank
        </button>
      </div>
      <Loaded state={banks}>
        {(list) =>
          list.length === 0 ? (
            <div className="card empty">No question banks yet.</div>
          ) : (
            <div className="grid">
              {list.map((b) => (
                <Link key={b.id} to={`/banks/${b.id}`} className="course-card">
                  <div className="course-code">{b.name}</div>
                  <p className="course-title">{b.description || ' '}</p>
                  <div className="row small muted">
                    <span>{b.question_count} questions</span>
                    {b.course_id && <span className="badge badge-blue">{courseName[b.course_id] ?? 'Course'}</span>}
                    {b.owner_id !== user.id && <span className="badge">Shared with you</span>}
                  </div>
                </Link>
              ))}
            </div>
          )
        }
      </Loaded>
      <Modal open={creating} onClose={() => setCreating(false)} title="New question bank">
        <BankForm onSubmit={create} busy={busy} error={error} submitLabel="Create bank" onCancel={() => setCreating(false)} />
      </Modal>
    </main>
  )
}
