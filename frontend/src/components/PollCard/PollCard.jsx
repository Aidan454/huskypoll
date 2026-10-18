import ToggleButton from '../ToggleButton/ToggleButton'
import './PollCard.css'
import eye from '../../assets/eye.svg'
import eyeSlash from '../../assets/eye-slash.svg'
import locked from '../../assets/locked.svg'
import unlocked from '../../assets/unlocked.svg'
import play from '../../assets/play.svg'
import stop from '../../assets/stop.svg'

export default function PollCard({question, type}){
    return (
    <>
    <div className="poll">
        <div id="poll-name">{question}</div>
        <div id="poll-info">
            <div id="poll-type">{type}</div>
        </div>
        <div className="poll-buttons">
            <ToggleButton id='hidden-btn' on={eyeSlash} off={eye} />
            <ToggleButton id='open-btn' on={unlocked} off={locked} />
            <ToggleButton id='play-btn' on={stop} off={play} />
        </div>
    </div>
    </>)
}
