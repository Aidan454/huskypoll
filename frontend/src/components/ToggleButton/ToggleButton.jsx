import styles from './ToggleButton.module.css'
import { useState } from 'react'

export default function ToggleButton({id, on, off, active, onChange, label, disabled = false}){
    const [state, setState] = useState(false)
    const isOn = active ?? state
    function toggle() {
        if (active === undefined) setState((s) => !s)
        else onChange?.(!active)
    }
    return (
        <>
        <button
            type="button"
            id={isOn ? `${id}-on` : `${id}-off`}
            className={styles.toggleBtn}
            aria-pressed={isOn}
            aria-label={label}
            title={label}
            disabled={disabled}
            onClick={toggle}>
            <img id={`${id}-img`} src={isOn ? on : off } width='16px' alt=''/>
        </button>
        </>
    )
}