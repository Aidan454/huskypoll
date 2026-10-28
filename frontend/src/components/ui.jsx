// Small shared building blocks: loading/error states, dialogs, badges.
import { useEffect, useRef } from 'react'

export function Loading({ label = 'Loading…' }) {
  return <p className="muted">{label}</p>
}

export function ErrorBox({ error }) {
  if (!error) return null
  return <div className="alert alert-error">{error.message || String(error)}</div>
}

/** Render children once `state` (from useApi) has data; show loading or error otherwise. */
export function Loaded({ state, children }) {
  if (state.error) return <ErrorBox error={state.error} />
  if (state.loading || state.data === undefined) return <Loading />
  return children(state.data)
}

/** A modal dialog. Open while `open` is true; onClose runs on Esc or backdrop click. */
export function Modal({ open, onClose, title, wide = false, children }) {
  const ref = useRef(null)
  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])
  return (
    <dialog
      ref={ref}
      className={wide ? 'modal modal-wide' : 'modal'}
      onCancel={(e) => {
        e.preventDefault()
        onClose()
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose()
      }}
    >
      {open && (
        <div className="modal-body">
          {title && <h2>{title}</h2>}
          {children}
        </div>
      )}
    </dialog>
  )
}

/** Ask "are you sure?" before a destructive action. */
export function ConfirmModal({ open, title, children, confirmLabel = 'Delete', busy, error, onConfirm, onClose }) {
  return (
    <Modal open={open} onClose={onClose} title={title}>
      <div className="stack">{children}</div>
      <ErrorBox error={error} />
      <div className="form-actions">
        <button type="button" className="btn" onClick={onClose}>
          Cancel
        </button>
        <button type="button" className="btn btn-solid-danger" onClick={onConfirm} disabled={busy}>
          {busy ? 'Working…' : confirmLabel}
        </button>
      </div>
    </Modal>
  )
}

export function StatusBadge({ status }) {
  const cls = status === 'open' ? 'badge badge-open' : status === 'closed' ? 'badge badge-closed' : 'badge'
  const label = status === 'open' ? '● Live' : status === 'draft' ? 'Up next' : status
  return <span className={cls}>{label}</span>
}

export function RoleBadge({ role }) {
  if (!role) return null
  const cls =
    role === 'student'
      ? 'badge badge-role-student'
      : role === 'ta'
        ? 'badge badge-role-ta'
        : 'badge badge-role-instructor'
  return <span className={cls}>{role === 'ta' ? 'TA' : role}</span>
}

export function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  )
}
