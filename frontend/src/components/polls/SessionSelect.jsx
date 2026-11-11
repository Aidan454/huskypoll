import { Field } from '../ui.jsx'
import { formatDate } from '../../format.js'

export default function SessionSelect({ sessions, value, onChange }) {
  return (
    <Field label="Lecture" hint="Leave on “Today” to use today's lecture (created if needed).">
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Today</option>
        {sessions.map((s) => (
          <option key={s.id} value={s.id}>
            {formatDate(s.session_date)} {s.title ? `· ${s.title}` : ''}
          </option>
        ))}
      </select>
    </Field>
  )
}
