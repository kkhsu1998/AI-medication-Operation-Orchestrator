/**
 * Shared design tokens — the single source of truth for the dark theme.
 * Extracted from the original orchestrator UI so every screen matches.
 */
export const C = {
  bg: '#0F141B',
  panel: '#171F29',
  panelAlt: '#1D2733',
  border: '#28323F',
  text: '#EDEFF2',
  muted: '#8A94A6',
  muted2: '#5C6779',
  amber: '#E8A33D',
  red: '#D9524B',
  blue: '#4C86C7',
  purple: '#9B7FD4',
  teal: '#4FA88A',
} as const

export const fonts = {
  display: "'Space Grotesk', sans-serif",
  body: "'IBM Plex Sans', sans-serif",
  mono: "'IBM Plex Mono', monospace",
} as const
