import { ArrowRight } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { home } from '../../copy'
import { api } from '../../lib/api'
import type { Rail as RailType } from '../../lib/types'
import { ItemGrid } from '../../components/ItemGrid/ItemGrid'
import styles from './Home.module.css'

export function Home() {
  const [slide, setSlide] = useState(0)
  const [rails, setRails] = useState<RailType[] | null>(null)

  useEffect(() => {
    const id = window.setInterval(() => setSlide((s) => (s + 1) % home.heroSlides.length), 6000)
    return () => window.clearInterval(id)
  }, [])

  useEffect(() => {
    api
      .home()
      .then((r) => setRails(r.rails))
      .catch(() => setRails([]))
  }, [])

  return (
    <div className={styles.page}>
      <section className={styles.hero} aria-roledescription="carousel" aria-label="Featured">
        {home.heroSlides.map((s, i) => (
          <div key={s.title} className={[styles.heroSlide, i === slide ? styles.active : ''].join(' ')} aria-hidden={i !== slide}>
            <div className={styles.heroContent}>
              <div className={styles.heroEyebrow}>{s.eyebrow}</div>
              <h1 className={styles.heroTitle}>{s.title}</h1>
              <p className={styles.heroBody}>{s.body}</p>
              {s.href ? (
                <Link to={s.href} className={styles.categoryCardLink}>
                  {s.cta} <ArrowRight size={14} />
                </Link>
              ) : null}
            </div>
          </div>
        ))}
        <div className={styles.heroDots}>
          {home.heroSlides.map((s, i) => (
            <button
              key={s.title}
              className={[styles.heroDot, i === slide ? styles.active : ''].join(' ')}
              onClick={() => setSlide(i)}
              aria-label={`Show slide ${i + 1}`}
              aria-current={i === slide}
            />
          ))}
        </div>
      </section>

      <section className={styles.categoryRow}>
        {home.categoryCards.map((c) => (
          <Link key={c.title} to={c.href} className={styles.categoryCard}>
            <div>
              <div className={styles.categoryCardTitle}>{c.title}</div>
            </div>
            <span className={styles.categoryCardLink}>
              {c.subtitle} <ArrowRight size={12} />
            </span>
          </Link>
        ))}
      </section>

      {(rails ?? [null, null, null, null]).map((rail, i) => (
        <section className={styles.rail} key={rail?.rail_id ?? i}>
          <div className={styles.railHeader}>
            <h2 className={styles.railTitle}>{rail?.title ?? home.popularRailTitle}</h2>
            {rail ? (
              <Link className={styles.railLink} to={`/category/${encodeURIComponent(rail.title ?? '')}`}>
                See all
              </Link>
            ) : null}
          </div>
          <ItemGrid items={rail?.items ?? null} skeletonCount={6} />
        </section>
      ))}
    </div>
  )
}
