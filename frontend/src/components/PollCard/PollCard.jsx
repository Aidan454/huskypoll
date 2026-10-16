import ToggleButton from '../ToggleButton/ToggleButton'
import './PollCard.css'

export default function PollCard({question, type}){
    return (
    <>
    <div className="poll">
        <div id="poll-name">{question}</div>
        <div id="poll-info">
            <div id="poll-type">{type}</div>
        </div>
        <div className="poll-buttons">
            <ToggleButton id='toggle-btn' />
            <ToggleButton id='toggle-btn' />
            <ToggleButton id='toggle-btn' />
        </div>
    </div>
    </>)
}
