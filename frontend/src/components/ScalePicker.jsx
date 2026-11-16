import { useSyncExternalStore } from 'react'
import { SCALE_OPTIONS, getScaleSnapshot, setScale, subscribeScale } from '../uiScale.js'

/** Three preset page sizes for readability, shown in the account menu. */
export default function ScalePicker() {
  const scale = useSyncExternalStore(subscribeScale, getScaleSnapshot)
  return <div className="scale-picker">
    <span className="scale-picker-label" id="scale-picker-label">
      <span className="scale-icon" aria-hidden="true">A</span>
      Text size
    </span>
    <div className="scale-options" role="radiogroup" aria-labelledby="scale-picker-label">
      {SCALE_OPTIONS.map((option) => (
        <button key={option.value} type="button" role="radio" aria-checked={scale === option.value}
          aria-label={`${option.name} (${option.label})`} title={option.name}
          className={scale === option.value ? 'active' : ''} onClick={() => setScale(option.value)}>
          {option.label}
        </button>
      ))}
    </div>
  </div>
}
