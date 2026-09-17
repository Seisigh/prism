import { Search } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import type { AutocompleteSuggestion } from '../../lib/types'
import styles from './SearchBar.module.css'

interface SearchBarProps {
  categories: string[]
}

export function SearchBar({ categories }: SearchBarProps) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [scope, setScope] = useState('all')
  const [suggestions, setSuggestions] = useState<AutocompleteSuggestion[]>([])
  const [open, setOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(-1)
  const wrapRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  useEffect(() => {
    window.clearTimeout(debounceRef.current)
    if (query.trim().length < 2) {
      setSuggestions([])
      return
    }
    debounceRef.current = window.setTimeout(async () => {
      try {
        const res = await api.autocomplete(query)
        setSuggestions(res.suggestions)
        setOpen(res.suggestions.length > 0)
        setHighlighted(-1)
      } catch {
        // Telemetry/UX never breaks on a failed autocomplete fetch.
        setSuggestions([])
      }
    }, 150)
    return () => window.clearTimeout(debounceRef.current)
  }, [query])

  function submit(q: string) {
    setOpen(false)
    const params = new URLSearchParams({ q })
    navigate(`/search?${params.toString()}`)
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || suggestions.length === 0) {
      if (e.key === 'Enter') submit(query)
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlighted((h) => (h + 1) % suggestions.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlighted((h) => (h <= 0 ? suggestions.length - 1 : h - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (highlighted >= 0) {
        const s = suggestions[highlighted]
        navigate(`/item/${s.item_id}`)
        setOpen(false)
      } else {
        submit(query)
      }
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className={styles.wrap} ref={wrapRef}>
      <div className={styles.field}>
        <select
          className={styles.scope}
          value={scope}
          onChange={(e) => setScope(e.target.value)}
          aria-label="Search category"
        >
          <option value="all">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <input
          className={styles.input}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls="search-suggestions"
          aria-autocomplete="list"
          aria-activedescendant={highlighted >= 0 ? `suggestion-${highlighted}` : undefined}
          placeholder="Search the catalog"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          onFocus={() => suggestions.length > 0 && setOpen(true)}
        />
        <button className={styles.submit} onClick={() => submit(query)} aria-label="Search">
          <Search size={17} strokeWidth={2} />
        </button>
      </div>

      {open && suggestions.length > 0 ? (
        <ul className={styles.dropdown} role="listbox" id="search-suggestions">
          {suggestions.map((s, i) => (
            <li key={s.item_id} role="presentation">
              <button
                id={`suggestion-${i}`}
                role="option"
                aria-selected={highlighted === i}
                className={[styles.suggestion, highlighted === i ? styles.highlighted : ''].join(' ')}
                onMouseEnter={() => setHighlighted(i)}
                onClick={() => {
                  navigate(`/item/${s.item_id}`)
                  setOpen(false)
                }}
              >
                <span>{s.title}</span>
                <span className={styles.suggestionCategory}>{s.category}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
