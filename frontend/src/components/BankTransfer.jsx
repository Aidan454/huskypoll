import { useState } from 'react'
import { api } from '../api.js'
import { ErrorBox, Modal } from './ui.jsx'
import { useAction } from '../hooks.js'

export default function BankTransfer({ bankId, onImported }) {
  const [importing, setImporting] = useState(false)
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [notice, setNotice] = useState('')
  const [download, downloading, downloadError] = useAction(async () => {
    const blob = await api.download(bankId ? `/banks/${bankId}/export` : '/library/export')
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'huskypoll-questions.zip'
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  })
  const [review, reviewing, reviewError] = useAction(async () => {
    setPreview(null)
    setPreview(await api.upload('/library/import', file, { bank_id: bankId, preview: true }))
  })
  const [confirm, saving, saveError] = useAction(async () => {
    const result = await api.upload('/library/import', file, { bank_id: bankId })
    setNotice(`${result.imported} questions imported. ${result.skipped || 0} exact duplicates skipped.`)
    setImporting(false)
    setFile(null)
    setPreview(null)
    onImported()
  })
  return <>
    <div className="row">
      <button type="button" className="btn" onClick={() => download()} disabled={downloading}>{downloading ? 'Exporting…' : 'Export ZIP'}</button>
      <button type="button" className="btn" onClick={() => { setImporting(true); setPreview(null); setFile(null) }}>Import ZIP</button>
    </div>
    <ErrorBox error={downloadError} />
    {notice && <div className="alert alert-success" role="status">{notice}</div>}
    <Modal open={importing} onClose={() => !saving && setImporting(false)} title="Import question bank">
      <p>Choose a HuskyPoll ZIP containing questions, tags, answer keys, and images. Existing questions and polls are preserved.</p>
      <label className="field">Question bank ZIP (up to 50 MB)
        <input type="file" accept=".zip,application/zip" disabled={reviewing || saving} onChange={(e) => { setFile(e.target.files[0] || null); setPreview(null) }} />
      </label>
      <ErrorBox error={reviewError || saveError} />
      {preview && <div className="alert alert-info"><strong>{preview.questions} questions</strong> and {preview.images} images found.
        {preview.tags.length > 0 && <p>Tags: {preview.tags.join(', ')}</p>}
        <p>Import adds editable questions. Exact duplicates in this collection are skipped; nothing is overwritten.</p>
      </div>}
      <div className="form-actions">
        <button type="button" className="btn" disabled={saving || reviewing} onClick={() => setImporting(false)}>Cancel</button>
        {preview ? <button type="button" className="btn btn-primary" disabled={saving} onClick={() => confirm()}>{saving ? 'Importing…' : 'Confirm import'}</button>
          : <button type="button" className="btn btn-primary" disabled={!file || reviewing} onClick={() => review()}>{reviewing ? 'Checking…' : 'Review file'}</button>}
      </div>
    </Modal>
  </>
}
