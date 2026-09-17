import { whatGetsRecorded } from '../../copy'
import { ENVELOPE_FIELDS, EVENT_TYPES } from '../../lib/eventSchema'
import styles from '../../styles/contentPage.module.css'

export function WhatGetsRecorded() {
  return (
    <div className={styles.page}>
      <h1 className={styles.title}>{whatGetsRecorded.heading}</h1>
      <p className={styles.section}>{whatGetsRecorded.recorded}</p>
      <p className={styles.section}>{whatGetsRecorded.notRecorded}</p>
      <p className={styles.section}>{whatGetsRecorded.why}</p>
      <p className={styles.section}>{whatGetsRecorded.howLong}</p>

      <h2 style={{ fontSize: 'var(--fs-20)', marginTop: 'var(--sp-8)' }}>Envelope fields</h2>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Field</th>
            <th>What it means</th>
          </tr>
        </thead>
        <tbody>
          {ENVELOPE_FIELDS.map((f) => (
            <tr key={f.field}>
              <td>
                <code>{f.field}</code>
              </td>
              <td>{f.description}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 style={{ fontSize: 'var(--fs-20)', marginTop: 'var(--sp-8)' }}>Event types</h2>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Type</th>
            <th>What it means</th>
          </tr>
        </thead>
        <tbody>
          {EVENT_TYPES.map((e) => (
            <tr key={e.type}>
              <td>
                <code>{e.type}</code>
              </td>
              <td>{e.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
