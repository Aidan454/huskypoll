import { useState } from 'react'
import { api } from '../../api.js'
import QuestionEditor from '../QuestionEditor.jsx'
import { useAction } from '../../hooks.js'
import SessionSelect from './SessionSelect.jsx'

/** Write a question on the spot and open it right away. */
export default function QuickPoll({ course, sessions, onOpened, onCancel, initialSessionId = '' }) {
  const [sessionId, setSessionId] = useState(String(initialSessionId))
  const [showResults, setShowResults] = useState(false)
  const [open, busy, error] = useAction(async (body) => {
    const poll = await api.post(`/courses/${course.id}/polls/quick`, {
      ...body,
      session_id: sessionId ? Number(sessionId) : null,
      show_results: showResults,
    })
    onOpened([poll])
  })
  return (
    <QuestionEditor
      onSubmit={open}
      busy={busy}
      error={error}
      submitLabel="Open poll"
      onCancel={onCancel}
      extra={
        <>
          <SessionSelect sessions={sessions} value={sessionId} onChange={setSessionId} />
          <label className="check" style={{ marginBottom: 8 }}>
            <input type="checkbox" checked={showResults} onChange={(e) => setShowResults(e.target.checked)} />
            Show live results to students
          </label>
        </>
      }
    />
  )
}
