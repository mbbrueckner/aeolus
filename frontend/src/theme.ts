import { useEffect, useState } from 'react'

export type ThemePreference = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'aeolus:theme'
const THEMES = { light: 'aeolus-light', dark: 'aeolus-dark' } as const

/** Read the stored preference, defaulting to following the operating system. */
function storedPreference(): ThemePreference {
  const saved = localStorage.getItem(STORAGE_KEY)
  return saved === 'light' || saved === 'dark' || saved === 'system' ? saved : 'system'
}

/**
 * Track the theme preference and keep `data-theme` on the document in sync.
 *
 * This owns state rather than reading a context, so calling it from a second
 * component creates a second, independent copy that never hears about changes
 * made through the first. Call it once, at the top, and pass what is needed
 * down.
 *
 * "system" deliberately stores no explicit theme, so the page keeps following
 * the operating system when it changes rather than freezing at whatever it was
 * on first load.
 */
export function useTheme() {
  const [preference, setPreference] = useState<ThemePreference>(storedPreference)
  const [systemDark, setSystemDark] = useState(
    () => window.matchMedia('(prefers-color-scheme: dark)').matches,
  )

  useEffect(() => {
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (event: MediaQueryListEvent) => setSystemDark(event.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  const resolved = preference === 'system' ? (systemDark ? 'dark' : 'light') : preference

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', THEMES[resolved])
    localStorage.setItem(STORAGE_KEY, preference)
  }, [preference, resolved])

  return { preference, setPreference, resolved }
}
