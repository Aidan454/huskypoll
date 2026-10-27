import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api } from '../api.js'
import { ErrorBox, Field, Loaded, Modal, RoleBadge } from '../components/ui.jsx'
import { canTeach, isStaff } from '../format.js'
import { useAction, useApi, useAuth } from '../hooks.js'

function CourseCard({ course }) {
  return (
    <Link to={`/courses/${course.id}`} className="course-card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <span className="course-code">
          {course.subject} {course.catalog}
          {course.section ? `-${course.section}` : ''}
        </span>
        <RoleBadge role={course.my_role} />
      </div>
      <p className="course-title">{course.title}</p>
      <div className="row small muted">
        <span>{course.term}</span>
        {course.archived_at && <span className="badge">Archived</span>}
      </div>
    </Link>
  )
}

function guessTerm() {
  const d = new Date()
  const y = d.getFullYear()
  return d.getMonth() >= 6 ? `Fall ${y}` : `Spring ${y}`
}

export function CourseForm({ initial, onSubmit, busy, error, submitLabel, onCancel, isEdit = false }) {
  const [form, setForm] = useState(
    initial ?? {
      term: guessTerm(),
      subject: '',
      catalog: '',
      section: '',
      title: '',
      points_correct: 0,
    },
  )
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  function submit(e) {
    e.preventDefault()
    const body = {
      ...form,
      subject: form.subject.trim().toUpperCase(),
      section: form.section?.trim() || null,
      points_correct: Number(form.points_correct),
    }
    onSubmit(body)
  }

  return (
    <form onSubmit={submit}>
      {!isEdit && (
        <div className="form-row">
          <Field label="Term">
            <input value={form.term} onChange={set('term')} required placeholder="Spring 2027" />
          </Field>
          <Field label="Subject">
            <input value={form.subject} onChange={set('subject')} required placeholder="CSE" maxLength={16} />
          </Field>
          <Field label="Catalog #">
            <input value={form.catalog} onChange={set('catalog')} required placeholder="2050" maxLength={16} />
          </Field>
        </div>
      )}
      <div className="form-row">
        <Field label="Section" hint="Optional">
          <input value={form.section ?? ''} onChange={set('section')} placeholder="001" maxLength={16} />
        </Field>
      </div>
      <Field label="Course title">
        <input value={form.title} onChange={set('title')} required placeholder="Data Structures" maxLength={200} />
      </Field>
      <Field label="Extra points if correct" hint="Only polls with an answer key">
        <input type="number" min="0" step="0.5" value={form.points_correct} onChange={set('points_correct')} />
      </Field>
      <ErrorBox error={error} />
      <div className="form-actions">
        {onCancel && (
          <button type="button" className="btn" onClick={onCancel}>
            Cancel
          </button>
        )}
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Saving…' : submitLabel}
        </button>
      </div>
    </form>
  )
}

export default function CoursesPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [showArchived, setShowArchived] = useState(false)
  const courses = useApi(`/courses${showArchived ? '?include_archived=true' : ''}`)
  const [creating, setCreating] = useState(false)

  const [create, busy, error] = useAction(async (body) => {
    const course = await api.post('/courses', body)
    navigate(`/courses/${course.id}`)
  })

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Courses</h1>
          <p className="subtitle">Hi {user.first_name || user.display_name}. Pick a course to get started.</p>
        </div>
        <div className="row">
          <label className="check small">
            <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
            Show archived
          </label>
          {canTeach(user) && (
            <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
              + New course
            </button>
          )}
        </div>
      </div>

      <Loaded state={courses}>
        {(list) => {
          const teaching = list.filter(isStaff)
          const enrolled = list.filter((c) => !isStaff(c))
          if (!list.length) {
            return (
              <div className="card empty">
                <p>You aren&apos;t in any courses yet.</p>
                <p className="small">
                  {canTeach(user)
                    ? 'Create one with “New course”.'
                    : 'Your instructor adds you from the class roster. If you have a poll code, use “Join a poll”.'}
                </p>
              </div>
            )
          }
          return (
            <>
              {teaching.length > 0 && (
                <section style={{ marginBottom: 28 }}>
                  {enrolled.length > 0 && <h2>Teaching</h2>}
                  <div className="grid">
                    {teaching.map((c) => (
                      <CourseCard key={c.id} course={c} />
                    ))}
                  </div>
                </section>
              )}
              {enrolled.length > 0 && (
                <section>
                  {teaching.length > 0 && <h2>Enrolled</h2>}
                  <div className="grid">
                    {enrolled.map((c) => (
                      <CourseCard key={c.id} course={c} />
                    ))}
                  </div>
                </section>
              )}
            </>
          )
        }}
      </Loaded>

      <Modal open={creating} onClose={() => setCreating(false)} title="New course">
        <CourseForm onSubmit={create} busy={busy} error={error} submitLabel="Create course" onCancel={() => setCreating(false)} />
      </Modal>
    </main>
  )
}
