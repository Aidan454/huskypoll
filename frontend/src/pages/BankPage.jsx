import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { api } from '../api.js'
import QuestionEditor from '../components/QuestionEditor.jsx'
import { ConfirmModal, ErrorBox, Field, Loaded, Modal } from '../components/ui.jsx'
import { isStaff } from '../format.js'
import { useAction, useApi, useAuth } from '../hooks.js'
import { BankForm } from './BanksPage.jsx'
import QuestionCard from '../components/QuestionBankCard.jsx'
import BankTransfer from '../components/BankTransfer.jsx'
import QuestionSearch from '../components/QuestionSearch.jsx'
import { matchesQuestion } from '../components/questionSearch.js'

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
  const [search, setSearch] = useState('')
  const [selectedTags, setSelectedTags] = useState([])
  const [type, setType] = useState('')
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
            <BankTransfer bankId={Number(bankId)} onImported={bank.reload} />
            {notice && <div className="alert alert-success">{notice}</div>}
            <ErrorBox error={copyQError} />
            <QuestionSearch questions={b.questions} search={search} setSearch={setSearch} selectedTags={selectedTags} setSelectedTags={setSelectedTags} type={type} setType={setType} />
            <p className="small muted">{b.questions.filter((q) => matchesQuestion(q, search, selectedTags, type)).length} of {b.questions.length} questions</p>
            {b.questions.length === 0 ? (
              <div className="card empty">No questions yet. Add one with “New question”.</div>
            ) : (
              b.questions.filter((q) => matchesQuestion(q, search, selectedTags, type)).map((q) => (
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
          showTags tagSuggestions={[...new Set((bank.data?.questions || []).flatMap((q) => q.tags || []))]}
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
