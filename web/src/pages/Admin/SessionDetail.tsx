import { Fragment, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../lib/api'
import type { CatalogItem } from '../../lib/types'
import { ProductImage } from '../../components/ProductImage/ProductImage'
import { ScrollableRegion } from '../../components/ScrollableRegion/ScrollableRegion'
import { Tooltip } from '../../components/Tooltip/Tooltip'
import tooltipStyles from '../../components/Tooltip/Tooltip.module.css'
import shared from './admin-shared.module.css'
import styles from './SessionDetail.module.css'

interface SignalValue {
  raw: number | null
  normalized: number | null
  available: boolean
}

interface SignalRow {
  item_id: string
  item_known: boolean
  surface: string
  mode: string
  start: number
  end: number
  duration_ms: number
  predicted_p_i: number | null
  label: 'committed' | 'fast_skip' | 'ambiguous'
  signals: Record<string, SignalValue>
}

interface SignalDescription {
  measures: string
  higher: string
  lower: string
  unavailable_when: string
}

type SortKey = 'item_id' | 'surface' | 'mode' | 'duration_ms' | 'predicted_p_i' | 'label'
type SortDir = 'asc' | 'desc'
/** No column is sorted yet -- rows render in the order the API returned them (chronological, per admin_signals.py). */
const DEFAULT_SORT: SortKey | null = null

const COLUMN_HELP: Record<SortKey, string> = {
  item_id: 'The catalog item this view was of. A ⚠ means the item_id was not found in the catalog store.',
  surface: 'Where on the site this view happened — home, category, search, detail, compare, or cart.',
  mode: "The browsing mode PRISM inferred for this view: discovery, directed search, broad search, comparison, or refind.",
  duration_ms: "How long the sealed view window lasted, in milliseconds — see item_dwell's own tooltip for how this feeds the model.",
  predicted_p_i: "The ranker's calibrated estimate of interest for this view, 0 to 1. Not imputed when the mode has no trained model — shown as — instead.",
  label: 'What actually happened: committed (added to cart, wishlist, or checkout), fast_skip (seen briefly, never returned to, never committed), or ambiguous (neither).',
}

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'item_id', label: 'Item' },
  { key: 'surface', label: 'Surface' },
  { key: 'mode', label: 'Mode' },
  { key: 'duration_ms', label: 'Duration' },
  { key: 'predicted_p_i', label: 'Predicted p_i' },
  { key: 'label', label: 'Label' },
]

function fmt(n: number | null): string {
  if (n === null) return '—'
  return Number.isInteger(n) ? String(n) : n.toFixed(3)
}

function signalTooltip(name: string, desc: SignalDescription | undefined) {
  if (!desc) return name
  return (
    <>
      <div className={tooltipStyles.heading}>{name}</div>
      <div className={tooltipStyles.row}>
        <b>Measures</b> {desc.measures}
      </div>
      <div className={tooltipStyles.row}>
        <b>Higher</b> {desc.higher}
      </div>
      <div className={tooltipStyles.row}>
        <b>Lower</b> {desc.lower}
      </div>
      <div className={tooltipStyles.row}>
        <b>Unavailable when</b> {desc.unavailable_when}
      </div>
    </>
  )
}

function compareRows(a: SignalRow, b: SignalRow, key: SortKey): number {
  const av = a[key]
  const bv = b[key]
  if (av === null && bv === null) return 0
  if (av === null) return -1
  if (bv === null) return 1
  if (typeof av === 'number' && typeof bv === 'number') return av - bv
  return String(av).localeCompare(String(bv))
}

export function SessionDetail() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const [rows, setRows] = useState<SignalRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [registry, setRegistry] = useState<Record<string, SignalDescription>>({})
  const [expandedItem, setExpandedItem] = useState<CatalogItem | null>(null)
  const [sortKey, setSortKey] = useState<SortKey | null>(DEFAULT_SORT)
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  useEffect(() => {
    if (!sessionId) return
    setRows(null)
    setError(null)
    setExpanded(null)
    fetch(`/api/admin/sessions/${sessionId}/signals`)
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load session signals')
        return r.json()
      })
      .then((d) => setRows(d.rows))
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load session signals'))
  }, [sessionId])

  useEffect(() => {
    fetch('/api/admin/signal-registry')
      .then((r) => (r.ok ? r.json() : {}))
      .then(setRegistry)
      .catch(() => setRegistry({}))
  }, [])

  useEffect(() => {
    setExpandedItem(null)
    if (rows === null || expanded === null) return
    const row = rows[expanded]
    if (!row) return
    api
      .item(row.item_id)
      .then(setExpandedItem)
      .catch(() => setExpandedItem(null))
  }, [expanded, rows])

  const sortedRows = useMemo(() => {
    if (!rows) return null
    const withIndex = rows.map((row, originalIndex) => ({ row, originalIndex }))
    if (sortKey === null) return withIndex // chronological, as returned
    withIndex.sort((a, b) => {
      const cmp = compareRows(a.row, b.row, sortKey)
      return sortDir === 'asc' ? cmp : -cmp
    })
    return withIndex
  }, [rows, sortKey, sortDir])

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
    setExpanded(null)
  }

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <div>
          <h1 className={shared.title}>Session detail</h1>
          <p className={shared.sub}>
            <Link className={shared.link} to="/admin/sessions">
              ← All sessions
            </Link>{' '}
            · <span className={shared.mono}>{sessionId}</span>
          </p>
        </div>
      </div>

      <div className={shared.panel}>
        <div className={shared.panelHeader}>
          <span>Item views — click a row for the full signal breakdown, click a column header to sort</span>
          <span>{rows?.length ?? '—'}</span>
        </div>
        {error ? (
          <p className={shared.errorText}>{error}</p>
        ) : rows === null ? (
          <div className={shared.loading}>Loading…</div>
        ) : rows.length === 0 ? (
          <div className={shared.empty}>No qualifying views in this session yet.</div>
        ) : (
          <ScrollableRegion outerClassName={shared.tableScrollOuter} scrollClassName={shared.tableScroll} ariaLabel="item views">
          <table className={shared.table}>
            <thead>
              <tr>
                {COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    className={styles.sortableHeader}
                    onClick={() => toggleSort(col.key)}
                    role="button"
                    tabIndex={0}
                    aria-sort={sortKey === col.key ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        toggleSort(col.key)
                      }
                    }}
                  >
                    <Tooltip content={COLUMN_HELP[col.key]}>
                      <span className={tooltipStyles.trigger} tabIndex={0}>
                        {col.label}
                      </span>
                    </Tooltip>
                    <span className={styles.sortIndicator}>
                      {sortKey === col.key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(sortedRows ?? []).map(({ row, originalIndex }) => (
                <Fragment key={originalIndex}>
                  <tr
                    className={shared.clickable}
                    onClick={() => setExpanded(expanded === originalIndex ? null : originalIndex)}
                    tabIndex={0}
                    role="button"
                    aria-expanded={expanded === originalIndex}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setExpanded(expanded === originalIndex ? null : originalIndex)
                      }
                    }}
                  >
                    <td className={shared.mono}>
                      {row.item_id}
                      {!row.item_known ? ' ⚠' : ''}
                    </td>
                    <td>{row.surface}</td>
                    <td>
                      <span className={[shared.modeTag, shared[`mode-${row.mode}`]].join(' ')}>{row.mode.replace('_', ' ')}</span>
                    </td>
                    <td>{Math.round(row.duration_ms)}ms</td>
                    <td className={styles.pScore}>{row.predicted_p_i === null ? '—' : row.predicted_p_i.toFixed(3)}</td>
                    <td>
                      <span className={[shared.labelTag, shared[`label-${row.label}`]].join(' ')}>{row.label.replace('_', ' ')}</span>
                    </td>
                  </tr>
                  {expanded === originalIndex ? (
                    <tr className={styles.expandRow}>
                      <td colSpan={6}>
                        <div className={styles.expandedItemHeader}>
                          <div className={styles.expandedThumb}>
                            <ProductImage path={expandedItem?.images?.grid ?? null} alt={expandedItem?.alt_text ?? ''} />
                          </div>
                          <div>
                            <div className={styles.expandedTitle}>{expandedItem?.title ?? row.item_id}</div>
                            <div className={shared.mono} style={{ fontSize: 11, color: 'var(--slate-soft)' }}>
                              {row.item_id}
                            </div>
                          </div>
                        </div>
                        <div className={styles.signalGrid}>
                          {Object.entries(row.signals)
                            .sort(([a], [b]) => a.localeCompare(b))
                            .map(([name, v]) => (
                              <div key={name} className={styles.signalCard}>
                                <div className={styles.signalName}>
                                  <span className={[shared.availDot, v.available ? shared.availYes : shared.availNo].join(' ')} />
                                  <Tooltip content={signalTooltip(name, registry[name])}>
                                    <span className={tooltipStyles.trigger} tabIndex={0}>
                                      {name}
                                    </span>
                                  </Tooltip>
                                </div>
                                {v.available ? (
                                  <div className={styles.signalValues}>
                                    <span>
                                      raw <b>{fmt(v.raw)}</b>
                                    </span>
                                    <span>
                                      z <b>{fmt(v.normalized)}</b>
                                    </span>
                                  </div>
                                ) : (
                                  <div className={styles.unavailable}>unavailable — not imputed as zero</div>
                                )}
                              </div>
                            ))}
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              ))}
            </tbody>
          </table>
          </ScrollableRegion>
        )}
      </div>
    </div>
  )
}
