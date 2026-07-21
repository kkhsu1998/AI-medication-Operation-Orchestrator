import { C } from './theme'

/** Consistent color + label for each detected issue kind (used across panels). */
export const KIND: Record<string, { label: string; color: string }> = {
  stockout: { label: 'Stockout', color: C.red },
  shortage: { label: 'Shortage', color: C.amber },
  expiration_risk: { label: 'Expiring', color: C.purple },
  overstock: { label: 'Overstock', color: C.blue },
}

export const kindOf = (k: string) => KIND[k] ?? { label: k, color: C.muted }
