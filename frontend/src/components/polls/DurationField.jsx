import { Field } from '../ui.jsx'

export function DurationField({ value, onChange }) {
  return (
    <Field label="Time limit (minutes)" hint="Leave empty for no timer. The poll closes by itself when time runs out.">
      <input type="number" min="1" step="1" placeholder="No limit" value={value} onChange={(e) => onChange(e.target.value)} />
    </Field>
  )
}

