import ToggleButton from '../ToggleButton/ToggleButton'
import './PollControls.css'
import eye from '../../assets/eye.svg'
import eyeSlash from '../../assets/eye-slash.svg'
import locked from '../../assets/locked.svg'
import unlocked from '../../assets/unlocked.svg'
import play from '../../assets/play.svg'
import stop from '../../assets/stop.svg'

export default function PollControls({showResults = false, onToggleResults, isOpen = false, onToggleOpen, busy = false}){
    return (
    <>
    <div className="poll-controls">
        {/* add a regular (non toggle button here for adding 30 sec) */}
        <ToggleButton
            id='hidden-btn'
            on={eye}
            off={eyeSlash}
            active={showResults}
            onChange={onToggleResults}
            label={showResults ? 'Hide results' : 'Show results'}
        />
        <ToggleButton id='open-btn' on={unlocked} off={locked} />
        <ToggleButton
            id='play-btn'
            on={stop}
            off={play}
            active={isOpen}
            onChange={onToggleOpen}
            label={isOpen ? 'Close poll' : 'Open poll'}
            disabled={busy}
        />
    </div>
    </>)
}
