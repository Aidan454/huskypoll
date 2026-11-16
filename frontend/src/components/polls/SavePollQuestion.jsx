import { useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api.js'
import { useAction, useApi } from '../../hooks.js'
import { ErrorBox, Modal } from '../ui.jsx'
import { TagEditor } from '../QuestionSearch.jsx'
import { parseTags } from '../questionSearch.js'

export default function SavePollQuestion({ poll }) {
  const [open, setOpen] = useState(false)
  const [tags, setTags] = useState((poll.question.tags || []).join(', '))
  const [saved, setSaved] = useState(false)
  const library = useApi(open ? '/library' : null)
  const [save, busy, error] = useAction(async () => {
    await api.post(`/polls/${poll.id}/save-to-bank`, { tags: parseTags(tags) })
    setSaved(true)
    setOpen(false)
  })
  return <>
    <button type="button" className="btn btn-sm" onClick={() => setOpen(true)} disabled={saved}>{saved ? 'Saved to question bank' : 'Save to question bank'}</button>
    {saved && <span className="small" role="status"> <Link to="/banks">View question bank</Link></span>}
    <Modal open={open} onClose={() => !busy && setOpen(false)} title="Save question to bank">
      <p>Save an editable copy with its choices, answer, explanation, and images. This poll and student answers stay unchanged.</p>
      <TagEditor value={tags} onChange={setTags} suggestions={library.data?.tags || []} />
      <ErrorBox error={error || library.error} />
      <div className="form-actions">
        <button type="button" className="btn" disabled={busy} onClick={() => setOpen(false)}>Cancel</button>
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => save()}>{busy ? 'Saving…' : 'Save copy'}</button>
      </div>
    </Modal>
  </>
}
