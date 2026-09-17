import { Link, useNavigate } from 'react-router-dom'
import { Button } from '../../components/Button/Button'
import { Price } from '../../components/Price/Price'
import { ProductImage } from '../../components/ProductImage/ProductImage'
import { cart, emptyStates } from '../../copy'
import { useCart } from '../../state/CartContext'
import styles from './Cart.module.css'

export function Cart() {
  const { lines, subtotalCents, setQuantity, remove } = useCart()
  const navigate = useNavigate()

  if (lines.length === 0) {
    return (
      <div className={styles.page}>
        <div className={styles.emptyWrap}>
          <h1 className={styles.title}>{emptyStates.cartEmpty.heading}</h1>
          <p>{emptyStates.cartEmpty.body}</p>
          <Button variant="primary" style={{ marginTop: 'var(--sp-4)' }} onClick={() => navigate('/')}>
            {emptyStates.cartEmpty.action}
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <div>
        <h1 className={styles.title}>{cart.heading}</h1>
        <div className={styles.lines}>
          {lines.map((line) => (
            <div className={styles.line} key={line.item.item_id}>
              <div className={styles.lineImage}>
                <ProductImage path={line.item.images?.grid ?? null} alt={line.item.alt_text} />
              </div>
              <div className={styles.lineInfo}>
                <Link to={`/item/${line.item.item_id}`} className={styles.lineTitle}>
                  {line.item.title}
                </Link>
                <span className={styles.lineBrand}>{line.item.brand}</span>
                <div className={styles.lineActions}>
                  <select
                    className={styles.qtySelect}
                    value={line.quantity}
                    onChange={(e) => setQuantity(line.item.item_id, Number(e.target.value))}
                    aria-label={`Quantity for ${line.item.title}`}
                  >
                    {[1, 2, 3, 4, 5].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                  <button className={styles.removeBtn} onClick={() => remove(line.item.item_id)}>
                    Remove
                  </button>
                </div>
              </div>
              <div className={styles.linePrice}>
                <Price cents={line.item.price_cents * line.quantity} showSavings={false} />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className={styles.summary}>
        <div className={styles.summaryRow} style={{ color: 'var(--slate)' }}>
          <span>{cart.itemCount(lines.reduce((s, l) => s + l.quantity, 0))}</span>
        </div>
        <div className={styles.summaryRow} style={{ fontWeight: 700, fontSize: 'var(--fs-16)' }}>
          <span>{cart.subtotal}</span>
          <Price cents={subtotalCents} showSavings={false} />
        </div>
        <Button variant="primary" style={{ width: '100%' }} onClick={() => navigate('/checkout')}>
          {cart.proceedToCheckout}
        </Button>
      </div>
    </div>
  )
}
