import './ToggleButton.css'
import { useState } from 'react'

export default function ToggleButton({id, on, off}){
    const [state, setState] = useState(false)
    return (
        <>
            <button id={id}>
                
            </button>
        </>
    )
}