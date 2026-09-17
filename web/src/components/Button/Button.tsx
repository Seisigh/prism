import { type ButtonHTMLAttributes, forwardRef } from 'react'
import styles from './Button.module.css'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'md' | 'sm'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', size = 'md', className, ...rest },
  ref,
) {
  const classes = [styles.btn, styles[variant], size === 'sm' ? styles.sm : '', className]
    .filter(Boolean)
    .join(' ')
  return <button ref={ref} className={classes} {...rest} />
})
