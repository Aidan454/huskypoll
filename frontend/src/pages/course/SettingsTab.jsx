import { useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router'
import { api } from '../../api.js'
import { ConfirmModal, ErrorBox, Field } from '../../components/ui.jsx'
import { useAction, useAuth } from '../../hooks.js'
import { CourseForm } from '../CoursesPage.jsx'

export default function SettingsTab() {
  const { course, setCourse } = useOutletContext()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [saved, setSaved] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [confirmText, setConfirmText] = useState('')
  const [deleteLogs, setDeleteLogs] = useState(false)
  const canDelete = course.my_role === 'owner' || user.is_admin
  const shortCode = `${course.subject} ${course.catalog}`

  const [save, saving, saveError] = useAction(async (body) => {
    const updated = await api.patch(`/courses/${course.id}`, {
      title: body.title,
      section: body.section,
      points_correct: body.points_correct,
    })
    setCourse(updated)
    setSaved(true)
  })
  const [toggleArchive, archiving, archiveError] = useAction(async () => {
    const updated = await api.post(`/courses/${course.id}/${course.archived_at ? 'unarchive' : 'archive'}`)
    setCourse(updated)
  })
  const [remove, removing, removeError] = useAction(async () => {
    await api.delete(`/courses/${course.id}`, { delete_logs: deleteLogs })
    navigate('/courses')
  })

  return (
    <>
      <div className="card">
        <h2>Course details</h2>
        {saved && <div className="alert alert-success">Saved.</div>}
        <CourseForm
          key={course.id}
          isEdit
          initial={{
            ...course,
            section: course.section ?? '',
          }}
          onSubmit={(b) => {
            setSaved(false)
            save(b)
          }}
          busy={saving}
          error={saveError}
          submitLabel="Save changes"
        />
      </div>

      <div className="card">
        <h2>{course.archived_at ? 'Unarchive course' : 'Archive course'}</h2>
        <p className="muted">
          {course.archived_at
            ? 'This course is hidden from course lists. Unarchive it to run polls again.'
            : 'At the end of the semester, archive the course to hide it. Everything is kept and you can undo this.'}
        </p>
        <ErrorBox error={archiveError} />
        <button type="button" className="btn" onClick={() => toggleArchive()} disabled={archiving}>
          {course.archived_at ? 'Unarchive' : 'Archive'}
        </button>
      </div>

      {canDelete && (
        <div className="card" style={{ borderColor: '#f0c8c4' }}>
          <h2 style={{ color: 'var(--red)' }}>Delete course</h2>
          <p className="muted">
            Permanently removes the roster, lectures, polls and every answer. Question banks are kept. Download the
            participation grades first; this cannot be undone.
          </p>
          <button type="button" className="btn btn-danger" onClick={() => setDeleting(true)}>
            Delete course…
          </button>
        </div>
      )}

      <ConfirmModal
        open={deleting}
        title="Delete this course?"
        confirmLabel="Delete forever"
        busy={removing || confirmText.trim().toUpperCase() !== shortCode.toUpperCase()}
        error={removeError}
        onConfirm={remove}
        onClose={() => setDeleting(false)}
      >
        <p>
          All students&apos; answers in <strong>{course.code}</strong> will be deleted.
        </p>
        <Field label={`Type ${shortCode} to confirm`}>
          <input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} />
        </Field>
        <label className="check small">
          <input type="checkbox" checked={deleteLogs} onChange={(e) => setDeleteLogs(e.target.checked)} />
          Also delete this course&apos;s activity log
        </label>
      </ConfirmModal>
    </>
  )
}
