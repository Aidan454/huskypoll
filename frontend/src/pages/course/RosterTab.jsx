import { useState } from 'react'
import { useOutletContext } from 'react-router'
import { api } from '../../api.js'
import { ConfirmModal, ErrorBox, Field, Loaded, Modal } from '../../components/ui.jsx'
import { useAction, useApi } from '../../hooks.js'

function ImportSummary({ result }) {
  if (!result) return null
  return (
    <div className="alert alert-success">
      <p style={{ margin: 0 }}>{result.summary}</p>
      {result.skipped?.length > 0 && (
        <details style={{ marginTop: 6 }}>
          <summary>{result.skipped.length} rows skipped</summary>
          <ul className="small">
            {result.skipped.map((s, i) => (
              <li key={i}>{Object.values(s).join(' · ')}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

function StudentName({ user }) {
  const netId = user.net_id?.toUpperCase()
  if (!netId || user.display_name === user.net_id) return <span className="netid">{netId ?? user.display_name}</span>
  return (
    <>
      {user.display_name} <span className="muted netid">{netId}</span>
    </>
  )
}

function StudentList({ students }) {
  return (
    <ul className="small roster-diff-list">
      {students.map((u) => (
        <li key={u.id}>
          <StudentName user={u} />
        </li>
      ))}
    </ul>
  )
}

/** After a StudentAdmin import: who joined, and who is on the roster but not in the file. */
function RosterChanges({ course, result, onDone }) {
  const [unchecked, setUnchecked] = useState(() => new Set())
  const [dropped, setDropped] = useState(null)
  const missing = result.missing ?? []
  const chosen = missing.filter((u) => !unchecked.has(u.id))

  const [drop, busy, error] = useAction(async () => {
    const r = await api.post(`/courses/${course.id}/roster/drop`, { user_ids: chosen.map((u) => u.id) })
    setDropped(r.dropped)
    onDone()
  })

  function toggle(id) {
    setUnchecked((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="roster-diff">
      {result.added?.length > 0 && (
        <section>
          <h3>Joined the course ({result.added.length})</h3>
          <p className="small muted">These students were added to the roster.</p>
          <StudentList students={result.added} />
        </section>
      )}
      {missing.length > 0 && dropped === null && (
        <section>
          <h3>Not in this roster file ({missing.length})</h3>
          <p className="small muted">
            These students are on the course roster but not in the file you imported, which usually means they dropped the
            course. Nobody is dropped until you choose to. Their past answers are kept either way.
          </p>
          <div className="row" style={{ marginBottom: 8 }}>
            <button type="button" className="linkbtn" onClick={() => setUnchecked(new Set())}>
              Select all
            </button>
            <button type="button" className="linkbtn" onClick={() => setUnchecked(new Set(missing.map((u) => u.id)))}>
              Deselect all
            </button>
          </div>
          <div className="stack roster-diff-list">
            {missing.map((u) => (
              <label key={u.id} className="check">
                <input type="checkbox" checked={!unchecked.has(u.id)} onChange={() => toggle(u.id)} />
                <span>
                  <StudentName user={u} />
                </span>
              </label>
            ))}
          </div>
          <ErrorBox error={error} />
          <div className="form-actions">
            <button type="button" className="btn btn-danger" onClick={drop} disabled={busy || chosen.length === 0}>
              {busy ? 'Dropping…' : `Drop ${chosen.length} ${chosen.length === 1 ? 'student' : 'students'} not in the new roster`}
            </button>
          </div>
        </section>
      )}
      {dropped !== null && (
        <div className="alert alert-info">
          Dropped {dropped} {dropped === 1 ? 'student' : 'students'}. Turn on “Show dropped” to see them.
        </div>
      )}
    </div>
  )
}

function AddStudents({ course, onDone }) {
  const [mode, setMode] = useState('paste')
  const [text, setText] = useState('')
  const [one, setOne] = useState({ identifier: '', first_name: '', last_name: '', section: '' })
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)

  const [submit, busy, error] = useAction(async () => {
    let r
    if (mode === 'paste') r = await api.post(`/courses/${course.id}/roster/paste`, { text })
    else if (mode === 'one') {
      const body = Object.fromEntries(Object.entries(one).map(([k, v]) => [k, v.trim() || null]))
      r = await api.post(`/courses/${course.id}/roster`, body)
    } else r = await api.upload(`/courses/${course.id}/roster/import`, file)
    setResult(r)
    onDone()
  })

  return (
    <>
      <div className="tabs" style={{ marginBottom: 16 }}>
        {[
          ['paste', 'Paste a list'],
          ['import', 'StudentAdmin file'],
          ['one', 'One student'],
        ].map(([k, label]) => (
          <a
            key={k}
            href="#"
            className={mode === k ? 'active' : ''}
            onClick={(e) => {
              e.preventDefault()
              setMode(k)
              setResult(null)
            }}
          >
            {label}
          </a>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        {mode === 'paste' && (
          <Field label="NetIDs, emails or student IDs" hint="One per line, or separated by commas.">
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8} placeholder={'abc12345\njane.doe@uconn.edu'} required />
          </Field>
        )}
        {mode === 'one' && (
          <>
            <Field label="NetID, email or 7-digit student ID">
              <input value={one.identifier} onChange={(e) => setOne({ ...one, identifier: e.target.value })} required />
            </Field>
            <div className="form-row">
              <Field label="First name">
                <input value={one.first_name} onChange={(e) => setOne({ ...one, first_name: e.target.value })} />
              </Field>
              <Field label="Last name">
                <input value={one.last_name} onChange={(e) => setOne({ ...one, last_name: e.target.value })} />
              </Field>
              <Field label="Section">
                <input value={one.section} onChange={(e) => setOne({ ...one, section: e.target.value })} />
              </Field>
            </div>
          </>
        )}
        {mode === 'import' && (
          <Field
            label="Class roster from StudentAdmin (.xlsx or .csv)"
            hint="Import the full, current class list. New students are added, and you can then review anyone who is no longer on it."
          >
            <input
              type="file"
              accept=".xlsx,.csv,text/csv"
              onChange={(e) => {
                setFile(e.target.files[0] ?? null)
                setResult(null)
              }}
              required
            />
          </Field>
        )}
        <ErrorBox error={error} />
        <ImportSummary result={result} />
        {result && mode === 'import' && <RosterChanges key={result.summary} course={course} result={result} onDone={onDone} />}
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? 'Adding…' : 'Add to roster'}
          </button>
        </div>
      </form>
    </>
  )
}

export default function RosterTab() {
  const { course } = useOutletContext()
  const [showDropped, setShowDropped] = useState(false)
  const [filter, setFilter] = useState('')
  const roster = useApi(`/courses/${course.id}/roster${showDropped ? '?include_dropped=true' : ''}`)
  const [adding, setAdding] = useState(false)
  const [dropping, setDropping] = useState(null)

  const [drop, dropBusy, dropError] = useAction(async () => {
    await api.delete(`/courses/${course.id}/roster/${dropping.user.id}`)
    setDropping(null)
    roster.reload()
  })

  const f = filter.trim().toLowerCase()
  return (
    <div className="card">
      <div className="card-head">
        <h2>Roster</h2>
        <div className="row">
          <input type="search" className="inline-input" placeholder="Search" value={filter} onChange={(e) => setFilter(e.target.value)} />
          <label className="check small">
            <input type="checkbox" checked={showDropped} onChange={(e) => setShowDropped(e.target.checked)} />
            Show dropped
          </label>
          <button type="button" className="btn btn-primary" onClick={() => setAdding(true)}>
            + Add students
          </button>
        </div>
      </div>
      <Loaded state={roster}>
        {(rows) => {
          const shown = rows.filter(
            (r) =>
              !f ||
              [r.user.display_name, r.user.net_id, r.user.email, r.user.student_id].some((v) => v?.toLowerCase().includes(f)),
          )
          return rows.length === 0 ? (
            <p className="empty">No students yet. Add them from a StudentAdmin roster or a list of NetIDs.</p>
          ) : (
            <>
              <p className="small muted">
                {rows.filter((r) => r.status === 'active').length} active students
              </p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>NetID</th>
                      <th>Email</th>
                      <th>Student ID</th>
                      <th>Section</th>
                      <th>Status</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {shown.map((r) => (
                      <tr key={r.user.id}>
                        <td>{r.user.display_name}</td>
                        <td className="netid">{r.user.net_id?.toUpperCase() ?? <span className="muted">—</span>}</td>
                        <td className="small">{r.user.email}</td>
                        <td>{r.user.student_id}</td>
                        <td>{r.section}</td>
                        <td>
                          <span className={r.status === 'active' ? 'badge badge-open' : 'badge'}>{r.status}</span>
                        </td>
                        <td>
                          {r.status === 'active' && (
                            <button type="button" className="btn btn-sm btn-danger" onClick={() => setDropping(r)}>
                              Drop
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )
        }}
      </Loaded>
      <Modal open={adding} onClose={() => setAdding(false)} title="Add students" wide>
        <AddStudents course={course} onDone={roster.reload} />
      </Modal>
      <ConfirmModal
        open={dropping !== null}
        title="Drop student?"
        confirmLabel="Drop"
        busy={dropBusy}
        error={dropError}
        onConfirm={drop}
        onClose={() => setDropping(null)}
      >
        <p>
          {dropping?.user.display_name} will no longer see this course. Their past answers are kept, and adding them again
          restores them.
        </p>
      </ConfirmModal>
    </div>
  )
}
