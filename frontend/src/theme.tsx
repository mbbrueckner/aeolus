import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type ThemePreference = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'aeolus:theme'
const THEMES = { light: 'aeolus-light', dark: 'aeolus-dark' } as const

interface Theme {
  preference: ThemePreference
  setPreference: (preference: ThemePreference) => void
  resolved: 'light' | 'dark'
}

/**
 * The theme lives in a context rather than in each component's own state.
 *
 * As a plain hook it held state, so a second caller got a second copy that
 * never heard about changes made through the first — the map kept the previous
 * colours after a toggle. A context makes that impossible.
 */
const ThemeContext = createContext<Theme | null>(null)

/** Read the stored preference, defaulting to following the operating system. */
function storedPreference(): ThemePreference {
  const saved = localStorage.getItem(STORAGE_KEY)
  return saved === 'light' || saved === 'dark' || saved === 'system' ? saved : 'system'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
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

  // "system" deliberately stores no explicit theme, so the page keeps following
  // the operating system when it changes rather than freezing at first load.
  const resolved = preference === 'system' ? (systemDark ? 'dark' : 'light') : preference

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', THEMES[resolved])
    localStorage.setItem(STORAGE_KEY, preference)
  }, [preference, resolved])

  return (
    <ThemeContext.Provider value={{ preference, setPreference, resolved }}>
      {children}
    </ThemeContext.Provider>
  )
}

/**
 * Read the current theme.
 *
 * Throws outside a ThemeProvider rather than quietly falling back, since a
 * silent default is how the colours drifted apart in the first place.
 */
export function useTheme(): Theme {
  const theme = useContext(ThemeContext)
  if (!theme) throw new Error('useTheme must be used inside a ThemeProvider')
  return theme
}
