import { Field } from '../ui.jsx'

export function DurationField({ value, onChange }) {
  return (
    <Field
      label="Time limit (minutes)"
      hint="Defaults to 1 minute. Clear it for no timer; the poll closes by itself when time runs out."
    >
      <input type="number" min="1" step="1" placeholder="No limit" value={value} onChange={(e) => onChange(e.target.value)} />
    </Field>
  )
}

