import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { api } from '../api.js'
import { QuestionBody } from '../components/PollParts.jsx'
import QuestionEditor from '../components/QuestionEditor.jsx'
import { ConfirmModal, ErrorBox, Field, Loaded, Modal } from '../components/ui.jsx'
import { isStaff, QUESTION_TYPE_SHORT } from '../format.js'
import { useAction, useApi, useAuth } from '../hooks.js'
import { BankForm } from './BanksPage.jsx'
import Markdown from '../components/Markdown.jsx'

function QuestionCard({ q, onEdit, onCopy, onDelete }) {
  const [expanded, setExpanded] = useState(false)
  const answer =
    q.type.startsWith('mc')
      ? q.options.filter((o) => o.is_correct).map((o) => o.letter).join(', ')
      : q.type === 'numeric'
        ? q.numeric_answer ?? ''
        : q.text_answer ?? ''
  return (
    <div className="card">
      <div className="card-head">
        <div className="row">
          <span className="badge">{QUESTION_TYPE_SHORT[q.type]}</span>
          {q.is_locked && <span className="badge badge-amber" title="Already polled: wording is locked">🔒 Polled</span>}
          {answer !== '' ? <span className="badge badge-open">Answer: {String(answer)}</span> : <span className="badge">No answer key</span>}
        </div>
        <div className="row">
          <button type="button" className="btn btn-sm" onClick={() => setExpanded(!expanded)}>
            {expanded ? 'Less' : 'More'}
          </button>
          <button type="button" className="btn btn-sm" onClick={onEdit}>
            Edit
          </button>
          <button type="button" className="btn btn-sm" onClick={onCopy}>
            Copy
          </button>
          {!q.is_locked && (
            <button type="button" className="btn btn-sm btn-danger" onClick={onDelete}>
              Delete
            </button>
          )}
        </div>
      </div>
      <QuestionBody question={q} />
      {q.options.length > 0 && (
        <ul className="list small">
          {q.options.map((o) => (
            <li key={o.id} style={{ justifyContent: 'flex-start', padding: '6px 0' }}>
              <span className="letter" style={o.is_correct ? { background: 'var(--green)', color: '#fff' } : undefined}>
                {o.letter}
              </span>
              <span>
                <Markdown text={o.text_md} />
              </span>
            </li>
          ))}
        </ul>
      )}
      {expanded && (
        <div className="small muted" style={{ marginTop: 8 }}>
          {q.explanation_md ? <p>
              Explanation: <Markdown text={q.explanation_md} />
            </p> : <p>No explanation.</p>}
          {q.numeric_tolerance != null && <p>Tolerance: ±{q.numeric_tolerance}</p>}
          {q.copied_from_id && <p>Copied from question #{q.copied_from_id}</p>}
        </div>
      )}
    </div>
  )
}

export default function BankPage() {
  const { bankId } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const bank = useApi(`/banks/${bankId}`)
  const courses = useApi('/courses')
  const [editing, setEditing] = useState(null) // null | 'new' | question
  const [editingBank, setEditingBank] = useState(false)
  const [copyingBank, setCopyingBank] = useState(false)
  const [copyName, setCopyName] = useState('')
  const [copyCourse, setCopyCourse] = useState('')
  const [deletingBank, setDeletingBank] = useState(false)
  const [deletingQ, setDeletingQ] = useState(null)
  const [notice, setNotice] = useState(null)

  const [saveQuestion, savingQ, qError] = useAction(async (body) => {
    if (editing === 'new') await api.post('/questions', { ...body, bank_id: Number(bankId) })
    else {
      const r = await api.patch(`/questions/${editing.id}`, body)
      if (r.responses_regraded) setNotice(`${r.responses_regraded} answers were re-marked with the new answer key.`)
    }
    setEditing(null)
    bank.reload()
  })
  const [copyQuestion, , copyQError] = useAction(async (q) => {
    await api.post(`/questions/${q.id}/copy`)
    setNotice('Question copied. The copy is unlocked, so you can change its wording.')
    bank.reload()
  })
  const [deleteQuestion, deletingQBusy, deleteQError] = useAction(async () => {
    await api.delete(`/questions/${deletingQ.id}`)
    setDeletingQ(null)
    bank.reload()
  })
  const [saveBank, savingBank, bankError] = useAction(async (body) => {
    await api.patch(`/banks/${bankId}`, body)
    setEditingBank(false)
    bank.reload()
  })
  const [copyBank, copyingBusy, copyError] = useAction(async () => {
    const b = await api.post(`/banks/${bankId}/copy`, { name: copyName.trim(), course_id: copyCourse ? Number(copyCourse) : null })
    setCopyingBank(false)
    navigate(`/banks/${b.id}`)
  })
  const [deleteBank, deletingBankBusy, deleteBankError] = useAction(async () => {
    await api.delete(`/banks/${bankId}`)
    navigate('/banks')
  })

  return (
    <main className="page">
      <div className="crumbs">
        <Link to="/banks">Question banks</Link>
      </div>
      <Loaded state={bank}>
        {(b) => (
          <>
            <div className="page-head">
              <div>
                <h1>{b.name}</h1>
                {b.description && <p className="subtitle">{b.description}</p>}
              </div>
              <div className="row">
                <button type="button" className="btn btn-primary" onClick={() => setEditing('new')}>
                  + New question
                </button>
                <button type="button" className="btn" onClick={() => setEditingBank(true)}>
                  Edit bank
                </button>
                <button
                  type="button"
                  className="btn"
                  onClick={() => {
                    setCopyName(`${b.name} (copy)`)
                    setCopyingBank(true)
                  }}
                >
                  Copy bank
                </button>
                {(b.owner_id === user.id || user.is_admin) && (
                  <button type="button" className="btn btn-danger" onClick={() => setDeletingBank(true)}>
                    Delete bank
                  </button>
                )}
              </div>
            </div>
            {notice && <div className="alert alert-success">{notice}</div>}
            <ErrorBox error={copyQError} />
            {b.questions.length === 0 ? (
              <div className="card empty">No questions yet. Add one with “New question”.</div>
            ) : (
              b.questions.map((q) => (
                <QuestionCard
                  key={q.id}
                  q={q}
                  onEdit={() => setEditing(q)}
                  onCopy={() => copyQuestion(q)}
                  onDelete={() => setDeletingQ(q)}
                />
              ))
            )}

            <Modal open={editingBank} onClose={() => setEditingBank(false)} title="Edit bank">
              <BankForm initial={b} onSubmit={saveBank} busy={savingBank} error={bankError} submitLabel="Save" onCancel={() => setEditingBank(false)} />
            </Modal>
          </>
        )}
      </Loaded>

      <Modal open={editing !== null} onClose={() => setEditing(null)} title={editing === 'new' ? 'New question' : 'Edit question'} wide>
        <QuestionEditor
          key={editing === 'new' ? 'new' : editing?.id}
          question={editing === 'new' ? null : editing}
          onSubmit={saveQuestion}
          busy={savingQ}
          error={qError}
          submitLabel={editing === 'new' ? 'Add question' : 'Save'}
          onCancel={() => setEditing(null)}
        />
      </Modal>

      <Modal open={copyingBank} onClose={() => setCopyingBank(false)} title="Copy bank">
        <p className="muted small">Copies every question, unlocked, e.g. for next semester.</p>
        <Field label="Name of the copy">
          <input value={copyName} onChange={(e) => setCopyName(e.target.value)} />
        </Field>
        <Field label="Share with a course (optional)">
          <select value={copyCourse} onChange={(e) => setCopyCourse(e.target.value)}>
            <option value="">Just me</option>
            {(courses.data ?? []).filter(isStaff).map((c) => (
              <option key={c.id} value={c.id}>
                {c.code}
              </option>
            ))}
          </select>
        </Field>
        <ErrorBox error={copyError} />
        <div className="form-actions">
          <button type="button" className="btn" onClick={() => setCopyingBank(false)}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" disabled={copyingBusy || !copyName.trim()} onClick={() => copyBank()}>
            Copy
          </button>
        </div>
      </Modal>

      <ConfirmModal
        open={deletingBank}
        title="Delete this bank?"
        busy={deletingBankBusy}
        error={deleteBankError}
        onConfirm={deleteBank}
        onClose={() => setDeletingBank(false)}
      >
        <p>The bank is removed. Its questions are kept (and past polls are unaffected), but they are no longer in a bank.</p>
      </ConfirmModal>
      <ConfirmModal
        open={deletingQ !== null}
        title="Delete this question?"
        busy={deletingQBusy}
        error={deleteQError}
        onConfirm={deleteQuestion}
        onClose={() => setDeletingQ(null)}
      >
        <p>This question has never been polled, so it can be deleted.</p>
      </ConfirmModal>
    </main>
  )
}
