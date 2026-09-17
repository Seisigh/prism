import { useState } from 'react'
import { Button } from '../../components/Button/Button'
import { deleteDialog, errors } from '../../copy'
import { useSession } from '../../state/SessionContext'
import styles from '../../styles/contentPage.module.css'

type Status = 'idle' | 'confirming' | 'success' | 'not-found'

export function DeleteMyData() {
  const { code: sessionCode } = useSession()
  const [input, setInput] = useState(sessionCode ?? '')
  const [status, setStatus] = useState<Status>('idle')

  async function handleDelete() {
    try {
      const res = await fetch(`/api/sessions/${encodeURIComponent(input)}`, { method: 'DELETE' })
      setStatus(res.ok ? 'success' : 'not-found')
    } catch {
      setStatus('not-found')
    }
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>{deleteDialog.heading}</h1>
      <p className={styles.section}>{deleteDialog.body(input || 'your code')}</p>

      <form
        className={styles.form}
        onSubmit={(e) => {
          e.preventDefault()
          setStatus('confirming')
        }}
      >
        <input
          className={styles.input}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="a7f3-92kd"
          aria-label="Your code"
        />
        <Button type="submit" variant="danger" disabled={!input}>
          {deleteDialog.confirm}
        </Button>
      </form>

      {status === 'confirming' ? (
        <div className={styles.resultBox}>
          <p>{deleteDialog.body(input)}</p>
          <div style={{ display: 'flex', gap: 'var(--sp-2)', marginTop: 'var(--sp-3)' }}>
            <Button variant="danger" onClick={handleDelete}>
              {deleteDialog.confirm}
            </Button>
            <Button variant="secondary" onClick={() => setStatus('idle')}>
              {deleteDialog.cancel}
            </Button>
          </div>
        </div>
      ) : null}

      {status === 'success' ? (
        <div className={[styles.resultBox, styles.success].join(' ')}>
          <strong>{errors.deletionConfirmed.heading}</strong>
          <p>{errors.deletionConfirmed.body(input)}</p>
        </div>
      ) : null}

      {status === 'not-found' ? (
        <div className={styles.resultBox}>
          <strong>{errors.deletionCodeNotFound.heading}</strong>
          <p>{errors.deletionCodeNotFound.body}</p>
        </div>
      ) : null}
    </div>
  )
}
