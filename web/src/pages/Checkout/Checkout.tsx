import { CheckCircle2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../../components/Button/Button'
import { Price } from '../../components/Price/Price'
import { checkout, cart as cartCopy } from '../../copy'
import { useCart } from '../../state/CartContext'
import styles from './Checkout.module.css'

export function Checkout() {
  const { lines, subtotalCents, clear } = useCart()
  const [confirmed, setConfirmed] = useState(false)
  const navigate = useNavigate()

  if (confirmed) {
    return (
      <div className={styles.page}>
        <div className={styles.confirm}>
          <CheckCircle2 size={48} className={styles.confirmIcon} strokeWidth={1.5} />
          <h1 className={styles.title}>{checkout.confirmedHeading}</h1>
          <p>{checkout.confirmedBody}</p>
          <Button variant="primary" style={{ marginTop: 'var(--sp-6)' }} onClick={() => navigate('/')}>
            {checkout.continueBrowsing}
          </Button>
        </div>
      </div>
    )
  }

  if (lines.length === 0) {
    navigate('/cart')
    return null
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>{checkout.heading}</h1>
      <p className={styles.notice}>{checkout.stubNotice}</p>

      {lines.map((line) => (
        <div className={styles.summaryRow} key={line.item.item_id}>
          <span>
            {line.item.title} &times; {line.quantity}
          </span>
          <Price cents={line.item.price_cents * line.quantity} showSavings={false} />
        </div>
      ))}
      <div className={[styles.summaryRow, styles.total].join(' ')}>
        <span>{cartCopy.subtotal}</span>
        <Price cents={subtotalCents} showSavings={false} />
      </div>

      <Button
        variant="primary"
        style={{ width: '100%', marginTop: 'var(--sp-6)' }}
        onClick={() => {
          setConfirmed(true)
          clear()
        }}
      >
        {checkout.placeOrder}
      </Button>
    </div>
  )
}
