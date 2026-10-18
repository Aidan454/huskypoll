import styles from './ToggleButton.module.css'
import { useState } from 'react'

export default function ToggleButton({id, on, off}){
    const [state, setState] = useState(false)
    return (
        <>
        <button 
            id={state ? `${id}-on` : `${id}-off`} 
            className={styles.toggleBtn} 
            onClick={() => setState((!state))}>
            <img id={`${id}-img`} src={state ? on : off } width='16px'/>
        </button>
        </>
    )
}