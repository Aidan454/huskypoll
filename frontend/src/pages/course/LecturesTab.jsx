import { useState } from 'react'
import { useOutletContext } from 'react-router'
import { api } from '../../api.js'
import { ErrorBox, Field, Loaded, Modal } from '../../components/ui.jsx'
import { formatDate, todayIso } from '../../format.js'
import { useAction, useApi } from '../../hooks.js'

function SessionForm({ initial, onSubmit, busy, error, onCancel, submitLabel }) {
  const [title, setTitle] = useState(initial?.title ?? '')
  const [date, setDate] = useState(initial?.session_date ?? todayIso())
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit({ title: title.trim(), session_date: date })
      }}
    >
      <Field label="Title">
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Lecture 5: Linked lists" required />
      </Field>
      <Field label="Date">
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
      </Field>
      <ErrorBox error={error} />
      <div className="form-actions">
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Saving…' : submitLabel}
        </button>
      </div>
    </form>
  )
}

export default function LecturesTab() {
  const { course } = useOutletContext()
  const sessions = useApi(`/courses/${course.id}/sessions`)
  const [editing, setEditing] = useState(null) // null | 'new' | session

  const [save, busy, error] = useAction(async (body) => {
    if (editing === 'new') await api.post(`/courses/${course.id}/sessions`, body)
    else await api.patch(`/sessions/${editing.id}`, body)
    setEditing(null)
    sessions.reload()
  })
  const [remove, , removeError] = useAction(async (s) => {
    await api.delete(`/sessions/${s.id}`)
    sessions.reload()
  })

  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h2>Lectures</h2>
          <p className="small muted" style={{ margin: 0 }}>
            Polls are grouped by lecture. Opening a poll without choosing one uses today&apos;s lecture.
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setEditing('new')}>
          + Add lecture
        </button>
      </div>
      <ErrorBox error={removeError} />
      <Loaded state={sessions}>
        {(list) =>
          list.length === 0 ? (
            <p className="empty">No lectures yet.</p>
          ) : (
            <ul className="list">
              {list.map((s) => (
                <li key={s.id}>
                  <span className="grow">
                    <strong>{formatDate(s.session_date)}</strong>
                    <span className="muted"> · {s.title || 'Untitled'}</span>
                    {s.is_auto && <span className="badge" style={{ marginLeft: 8 }}>Automatic</span>}
                  </span>
                  <span className="small muted">{s.poll_count} {s.poll_count === 1 ? 'poll' : 'polls'}</span>
                  <button type="button" className="btn btn-sm" onClick={() => setEditing(s)}>
                    Edit
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm btn-danger"
                    disabled={s.poll_count > 0}
                    title={s.poll_count > 0 ? 'Only lectures without polls can be deleted' : undefined}
                    onClick={() => remove(s)}
                  >
                    Delete
                  </button>
                </li>
              ))}
            </ul>
          )
        }
      </Loaded>
      <Modal open={editing !== null} onClose={() => setEditing(null)} title={editing === 'new' ? 'Add lecture' : 'Edit lecture'}>
        <SessionForm
          key={editing === 'new' ? 'new' : editing?.id}
          initial={editing === 'new' ? null : editing}
          onSubmit={save}
          busy={busy}
          error={error}
          onCancel={() => setEditing(null)}
          submitLabel={editing === 'new' ? 'Add lecture' : 'Save'}
        />
      </Modal>
    </div>
  )
}
