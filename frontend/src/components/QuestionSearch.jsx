import { parseTags } from './questionSearch.js'
import { QUESTION_TYPE_SHORT } from '../format.js'
import './QuestionBank.css'

export function TagEditor({ value, onChange, suggestions = [] }) {
  const chosen = parseTags(value)
  return <div className="field">
    <label>Question tags
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder="Lect 2.3, Recursion" />
    </label>
    <span className="hint small muted">Separate tags with commas. Reuse tags to group questions by lecture or topic.</span>
    {suggestions.length > 0 && <details className="bank-tag-suggestions" open>
      <summary>Existing tags — click to reuse</summary>
      <div className="bank-tags">{suggestions.map((tag) => <button type="button" className="btn btn-sm" key={tag}
        aria-pressed={chosen.some((t) => t.toLowerCase() === tag.toLowerCase())}
        onClick={() => onChange(chosen.some((t) => t.toLowerCase() === tag.toLowerCase())
          ? chosen.filter((t) => t.toLowerCase() !== tag.toLowerCase()).join(', ') : [...chosen, tag].join(', '))}>{tag}</button>)}</div>
    </details>}
  </div>
}

export default function QuestionSearch({ questions, search, setSearch, selectedTags, setSelectedTags, type, setType }) {
  const tags = [...new Set(questions.flatMap((q) => q.tags || []))].sort((a, b) => a.localeCompare(b))
  return <section className="card bank-search" aria-label="Find questions">
    <div className="bank-search-row">
      <label className="grow">Search questions
        <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Question text, Lect 2.3, keywords…" />
      </label>
      {setType && <label>Question type<select value={type} onChange={(e) => setType(e.target.value)}>
        <option value="">All types</option>{Object.entries(QUESTION_TYPE_SHORT).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select></label>}
    </div>
    {tags.length > 0 && <details open>
      <summary>Filter by tags {selectedTags.length > 0 && `(${selectedTags.length} selected)`}</summary>
      <div className="bank-tags">{tags.map((tag) => <button key={tag} type="button" className={`btn btn-sm ${selectedTags.includes(tag) ? 'btn-primary' : ''}`}
        aria-pressed={selectedTags.includes(tag)} onClick={() => setSelectedTags(selectedTags.includes(tag) ? selectedTags.filter((t) => t !== tag) : [...selectedTags, tag])}>{tag}</button>)}</div>
      {selectedTags.length > 1 && <p className="small muted">Showing questions with all selected tags.</p>}
    </details>}
    {(search || selectedTags.length > 0 || type) && <button type="button" className="linkbtn" onClick={() => { setSearch(''); setSelectedTags([]); setType?.('') }}>Clear filters</button>}
  </section>
}
