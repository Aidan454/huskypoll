import { useId, useRef, useState } from 'react'
import { api } from '../api.js'
import { ErrorBox } from './ui.jsx'

const IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
const MAX_BYTES = 10 * 1024 * 1024

export default function ImagePicker({ label, url, onUploaded, onRemove, disabled, onBusyChange }) {
  const id = useId()
  const input = useRef(null)
  const uploading = useRef(false)
  const dragDepth = useRef(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)

  async function upload(files) {
    if (disabled || uploading.current) return
    setError(null)
    if (files.length !== 1) {
      setError(new Error('Choose one picture at a time.'))
      return
    }
    const file = files[0]
    if (!IMAGE_TYPES.includes(file.type)) {
      setError(new Error('Use a PNG, JPEG, GIF, or WebP picture.'))
      return
    }
    if (file.size > MAX_BYTES) {
      setError(new Error('Pictures must be 10 MB or smaller.'))
      return
    }
    uploading.current = true
    setBusy(true)
    onBusyChange?.(true)
    try {
      const media = await api.upload('/media', file)
      onUploaded(media)
    } catch (err) {
      setError(err)
    } finally {
      uploading.current = false
      setBusy(false)
      onBusyChange?.(false)
    }
  }

  function paste(event) {
    const files = Array.from(event.clipboardData.items)
      .filter((item) => item.kind === 'file')
      .map((item) => item.getAsFile()).filter(Boolean)
    if (!files.length) return // Leave ordinary text pasting alone.
    event.preventDefault()
    upload(files)
  }

  return (
    <div className="field">
      <span id={`${id}-label`}>{label}</span>
      {url && <img src={url} alt={`${label} preview`} className="question-img" />}
      {!disabled && (
        <>
          <div
            className={`image-dropzone${dragging ? ' is-dragging' : ''}`}
            role="group"
            tabIndex={0}
            aria-labelledby={`${id}-label`}
            aria-describedby={`${id}-help`}
            aria-busy={busy}
            onPaste={paste}
            onDragEnter={(event) => {
              event.preventDefault()
              dragDepth.current += 1
              if (!uploading.current) setDragging(true)
            }}
            onDragOver={(event) => {
              event.preventDefault()
              event.dataTransfer.dropEffect = busy ? 'none' : 'copy'
            }}
            onDragLeave={(event) => {
              event.preventDefault()
              dragDepth.current = Math.max(0, dragDepth.current - 1)
              if (!dragDepth.current) setDragging(false)
            }}
            onDrop={(event) => {
              event.preventDefault()
              dragDepth.current = 0
              setDragging(false)
              upload(Array.from(event.dataTransfer.files))
            }}
          >
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <rect x="3" y="3" width="18" height="18" rx="3" />
              <circle cx="8" cy="8" r="1.5" />
              <path d="m3 17 5-5 4 4 3-3 6 6" />
            </svg>
            <strong>{busy ? 'Uploading picture…' : 'Drag a picture here'}</strong>
            <span>or <button type="button" className="linkbtn" disabled={busy} onClick={() => input.current.click()}>upload a file</button></span>
            <small id={`${id}-help`}>Click this area and press Command+V (Mac) or Ctrl+V to paste a picture.<br />PNG, JPEG, GIF, WebP · Up to 10 MB · One picture</small>
            <input ref={input} type="file" hidden accept={IMAGE_TYPES.join(',')} disabled={busy}
              aria-label={`Upload ${label}`}
              onChange={(event) => {
                const files = Array.from(event.target.files)
                if (files.length) upload(files)
                event.target.value = ''
              }} />
          </div>
          {url && <button type="button" className="btn btn-sm btn-danger" disabled={busy} onClick={onRemove}>Remove picture</button>}
        </>
      )}
      <div role="status" aria-live="polite">{busy && <small>Uploading…</small>}</div>
      <ErrorBox error={error} />
    </div>
  )
}
