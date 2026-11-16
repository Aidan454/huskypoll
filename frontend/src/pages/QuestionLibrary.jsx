import { useState } from 'react'
import { api } from '../api.js'
import { useAction, useApi } from '../hooks.js'
import { ConfirmModal, ErrorBox, Loaded, Modal } from '../components/ui.jsx'
import QuestionEditor from '../components/QuestionEditor.jsx'
import QuestionSearch from '../components/QuestionSearch.jsx'
import { matchesQuestion } from '../components/questionSearch.js'
import BankTransfer from '../components/BankTransfer.jsx'
import QuestionCard from '../components/QuestionBankCard.jsx'

export default function QuestionLibrary({ collections }) {
  const library = useApi('/library')
  const [search, setSearch] = useState('')
  const [tags, setTags] = useState([])
  const [type, setType] = useState('')
  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [notice, setNotice] = useState('')
  const [save, busy, error] = useAction(async (body) => {
    if (editing === 'new') await api.post('/library/questions', body)
    else await api.patch(`/questions/${editing.id}`, body)
    setEditing(null)
    library.reload()
  })
  const [copy, , copyError] = useAction(async (q) => {
    await api.post(`/questions/${q.id}/copy`)
    setNotice('Editable copy created. Past polls are unchanged.')
    library.reload()
  })
  const [remove, removing, removeError] = useAction(async () => {
    await api.delete(`/questions/${deleting.id}`)
    setDeleting(null)
    library.reload()
  })
  return <main className="page">
    <div className="page-head">
      <div><h1>Question bank</h1><p className="subtitle">Your reusable questions, organized by tags. Find a lecture, topic, or specific question.</p></div>
      <button type="button" className="btn btn-primary" onClick={() => setEditing('new')}>+ New question</button>
    </div>
    <BankTransfer onImported={library.reload} />
    {notice && <div className="alert alert-success" role="status">{notice}</div>}
    <ErrorBox error={copyError} />
    <Loaded state={library}>{(data) => {
      const shown = data.questions.filter((q) => matchesQuestion(q, search, tags, type))
      return <>
        <QuestionSearch questions={data.questions} search={search} setSearch={setSearch} selectedTags={tags} setSelectedTags={setTags} type={type} setType={setType} />
        <div className="bank-results"><span className="small muted">{shown.length} of {data.questions.length} questions</span></div>
        {!shown.length && <div className="card empty">{data.questions.length ? 'No questions match these filters. Try another keyword or clear the filters.' : 'No saved questions yet. Create a question here, import a bank, or save a question from a poll.'}</div>}
        {shown.map((q) => <QuestionCard key={q.id} q={q} onEdit={() => setEditing(q)} onCopy={() => copy(q)} onDelete={() => setDeleting(q)} />)}
      </>
    }}</Loaded>
    <details className="bank-collection-details"><summary>Manage existing collections and course sharing</summary>{collections}</details>
    <Modal open={editing !== null} onClose={() => setEditing(null)} title={editing === 'new' ? 'New question' : 'Edit question'} wide>
      <QuestionEditor key={editing === 'new' ? 'new' : editing?.id} question={editing === 'new' ? null : editing}
        showTags tagSuggestions={library.data?.tags || []} busy={busy} error={error} onSubmit={save} onCancel={() => setEditing(null)} />
    </Modal>
    <ConfirmModal open={!!deleting} title="Delete this question?" busy={removing} error={removeError} onConfirm={remove} onClose={() => setDeleting(null)}>
      <p>This question has never been polled. Past polls and student answers are unaffected.</p>
    </ConfirmModal>
  </main>
}
