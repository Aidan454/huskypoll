import { useId, useState } from 'react'
import { QuestionBody } from '../PollParts.jsx'
import Markdown from '../Markdown.jsx'
import { Field } from '../ui.jsx'

/** Local-only practice inputs: no API calls and no real answer submission. */
export default function StudentQuestionPreview({ question, onBack }) {
  const choiceName = useId()
  const [selected, setSelected] = useState([])
  const [answer, setAnswer] = useState('')
  function choose(id) {
    setSelected((previous) => question.type === 'mc_single'
      ? [id]
      : previous.includes(id) ? previous.filter((value) => value !== id) : [...previous, id])
  }
  return (
    <div className="student-question-preview">
      <p className="alert alert-info">Preview only. Answers here are not submitted, and no poll is opened. The answer key and explanation are hidden.</p>
      <QuestionBody question={question} />
      {!question.body_md && !question.body_media_url && <p className="muted">Your question will appear here.</p>}
      {question.type === 'mc_multi' && <p className="small muted">Choose all that apply.</p>}
      {question.options.map((option) => (
        <label key={option.id} className={selected.includes(option.id) ? 'choice selected' : 'choice'}>
          <input type={question.type === 'mc_single' ? 'radio' : 'checkbox'} name={choiceName}
            checked={selected.includes(option.id)} onChange={() => choose(option.id)} />
          <span className="letter">{option.letter}</span>
          <span className="grow"><Markdown text={option.text_md} /></span>
        </label>
      ))}
      {question.type.startsWith('mc') && !question.options.length && <p className="muted">Add answer choices to preview them.</p>}
      {question.type === 'free_text' && <Field label="Your answer"><textarea value={answer} onChange={(event) => setAnswer(event.target.value)} maxLength={2000} /></Field>}
      {question.type === 'numeric' && <Field label="Your answer"><input type="number" step="any" value={answer} onChange={(event) => setAnswer(event.target.value)} /></Field>}
      <button type="button" className="btn btn-primary btn-block" disabled>Submit answer (preview only)</button>
      <div className="form-actions"><button type="button" className="btn" onClick={onBack}>Back to editing</button></div>
    </div>
  )
}
