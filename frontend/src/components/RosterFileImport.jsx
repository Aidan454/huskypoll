import { useRef, useState } from 'react'
import { api } from '../api.js'
import { ErrorBox } from './ui.jsx'
import './RosterFileImport.css'

const labels = { added: 'New student', reactivated: 'Restore enrollment', unchanged: 'Already enrolled', invalid: 'Invalid — skipped', duplicate: 'Duplicate — skipped' }

export default function RosterFileImport({ course, onDone, onImported }) {
  const input = useRef(null)
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)

  async function choose(files) {
    if (busy) return
    setPreview(null)
    setResult(null)
    onImported(null)
    setError(null)
    setFile(null)
    if (!files?.length) return
    const selected = files[0]
    if (files.length !== 1 || !/\.(csv|xlsx)$/i.test(selected.name)) {
      setError(new Error('Choose one CSV or XLSX roster file.'))
      return
    }
    if (selected.size > 5 * 1024 * 1024) {
      setError(new Error('Roster file is too large (5 MB max).'))
      return
    }
    setFile(selected)
    setBusy(true)
    try {
      setPreview(await api.upload(`/courses/${course.id}/roster/import`, selected, { preview: true }))
    } catch (err) { setError(err) }
    finally { setBusy(false) }
  }

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      const imported = await api.upload(`/courses/${course.id}/roster/import`, file)
      setResult(imported)
      onImported(imported)
      setPreview(null)
      onDone()
    } catch (err) { setError(err) }
    finally { setBusy(false) }
  }

  const count = preview?.counts
  const changes = count ? count.added + count.reactivated : 0
  return (
    <section aria-label="Roster file import" className="roster-import">
      <p>Upload the full class list for <strong>{course.subject} {course.catalog}</strong>. Review it before changing the roster.</p>
      <div className={`roster-upload ${dragging ? 'is-dragging' : ''}`}
        onDragOver={(e) => { e.preventDefault(); if (!busy) setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); choose(e.dataTransfer.files) }}>
        <strong>Drag your roster file here</strong>
        <span className="small muted">CSV or XLSX · up to 5 MB</span>
        <button type="button" className="btn" disabled={busy} onClick={() => input.current.click()}>Choose a file</button>
        <input ref={input} type="file" tabIndex={-1} accept=".csv,.xlsx" aria-label="Choose roster file" disabled={busy}
          onChange={(e) => { choose(e.target.files); e.target.value = '' }} />
      </div>
      <ErrorBox error={error} />
      <div role="status" aria-live="polite">
        {busy && <p>Processing roster…</p>}
        {file && <p className="small">File: <strong>{file.name}</strong></p>}
        {result && <div className="alert alert-success"><strong>Import complete.</strong> {result.summary} No students were removed.</div>}
      </div>
      {result?.skipped?.length > 0 && <details open>
        <summary>{result.skipped.length} rows skipped</summary>
        <ul>{result.skipped.map((row, i) => <li key={i}>Row {row.row}: {row.reason}</li>)}</ul>
      </details>}
      {preview && <>
        <h3>Review before importing</h3>
        <p className="small">{count.added} new · {count.reactivated} to restore · {count.unchanged} already enrolled · {count.duplicate} duplicates · {count.invalid} need correction</p>
        {count.invalid > 0 && <div className="alert alert-info">Invalid rows will be skipped. You can import the valid students now, or correct the file and upload it again. Nothing has been imported yet.</div>}
        {preview.rows.length > 0 && !changes && !count.invalid && !preview.missing.length && <p>All students in this file are already enrolled. No import is needed.</p>}
        {preview.rows.length === 0 && <p>No student rows found. Confirm only if this is the complete class list and you want to review missing students.</p>}
        <div className="table-wrap roster-preview"><table>
          <thead><tr><th>Row</th><th>Name</th><th>NetID / Email / ID</th><th>Status</th></tr></thead>
          <tbody>{preview.rows.map((row) => <tr key={row.row}>
            <td>{row.row}</td><td>{row.name || '—'}</td>
            <td>{row.net_id || row.email || row.student_id || '—'}</td>
            <td><strong>{labels[row.status]}</strong>{row.reason && <div className="small muted">{row.reason}</div>}</td>
          </tr>)}</tbody>
        </table></div>
        {preview.missing.length > 0 && <details className="roster-missing">
          <summary>{preview.missing.length} current students are missing from this file — they will stay enrolled</summary>
          <ul>{preview.missing.map((u) => <li key={u.id}>{u.display_name} {u.net_id?.toUpperCase()}</li>)}</ul>
        </details>}
        <p className="small muted">No changes are saved until you confirm. Missing students are never removed by this upload.</p>
        <div className="form-actions">
          <button type="button" className="btn" disabled={busy} onClick={() => { setPreview(null); setFile(null); setError(null) }}>Cancel</button>
          <button type="button" className="btn btn-primary" disabled={busy || (!changes && !preview.missing.length)} onClick={confirm}>
            {busy ? 'Importing…' : changes ? `Confirm import (${changes} students)` : 'Confirm import and review missing students'}
          </button>
        </div>
      </>}
    </section>
  )
}
