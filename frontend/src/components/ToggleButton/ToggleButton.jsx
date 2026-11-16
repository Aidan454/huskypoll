import styles from './ToggleButton.module.css'
import { useState } from 'react'

/**
 * Round icon toggle. Controlled with `active` + `onChange`; without them it
 * keeps its own state (used by the still-unwired lock button).
 */
export default function ToggleButton({ id, on, off, active, onChange, label, disabled = false }) {
  const [local, setLocal] = useState(false)
  const controlled = onChange !== undefined && active !== undefined
  const isOn = controlled ? active : local

  function handleClick() {
    if (disabled) return
    if (controlled) onChange(!isOn)
    else setLocal((value) => !value)
  }

  return (
    <button
      type="button"
      id={`${id}-${isOn ? 'on' : 'off'}`}
      className={styles.toggleBtn}
      onClick={handleClick}
      aria-pressed={isOn}
      aria-label={label}
      title={label}
      disabled={disabled}
    >
      <img id={`${id}-img`} src={isOn ? on : off} width="16px" alt="" />
    </button>
  )
}
