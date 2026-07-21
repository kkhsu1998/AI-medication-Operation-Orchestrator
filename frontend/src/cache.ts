/**
 * Tiny module-level cache so data survives route changes / mode switches.
 *
 * React Router unmounts a screen on navigation, dropping its component state —
 * which would otherwise refetch everything on return. This store lives outside
 * React, so switching tabs (Stock ↔ Forecast ↔ Dashboard …) or modes reuses the
 * already-loaded data instantly. Writes invalidate the relevant keys.
 */
const store = new Map<string, unknown>()

export function getCache<T>(key: string): T | undefined {
  return store.get(key) as T | undefined
}

export function setCache<T>(key: string, value: T): void {
  store.set(key, value)
}

/** Return cached value if present, else fetch, cache, and return it. */
export async function cached<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  if (store.has(key)) return store.get(key) as T
  const value = await fetcher()
  store.set(key, value)
  return value
}

/** Drop every cache entry whose key starts with `prefix` (e.g. after a write). */
export function invalidate(prefix: string): void {
  for (const key of [...store.keys()]) {
    if (key.startsWith(prefix)) store.delete(key)
  }
}

export function clearCache(): void {
  store.clear()
}
