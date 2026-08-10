import { useState } from 'react'
import { analyseRoute } from './api'
import { ControlPanel } from './components/ControlPanel'
import { RouteMap } from './components/RouteMap'
import { SummaryPanel } from './components/SummaryPanel'
import { ThemeToggle } from './components/ThemeToggle'
import { useTheme } from './theme'
import type { Analysis } from './types'

export default function App() {
  const { preference, setPreference } = useTheme()
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(gpx: File, avgSpeedKmh: number, startTime: string) {
    setBusy(true)
    setError(null)
    try {
      setAnalysis(await analyseRoute({ gpx, avgSpeedKmh, startTime }))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught))
      setAnalysis(null)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-full flex-col bg-base-200 lg:flex-row">
      <aside className="flex w-full shrink-0 flex-col gap-6 overflow-y-auto border-base-300/70 bg-base-100 p-6 lg:w-[23rem] lg:border-r">
        <header className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <WindMark />
            <div>
              <h1 className="text-xl leading-tight font-semibold tracking-tight">Aeolus</h1>
              <p className="text-xs opacity-55">Wetter entlang deiner Route</p>
            </div>
          </div>
          <ThemeToggle preference={preference} onChange={setPreference} />
        </header>

        <ControlPanel busy={busy} onSubmit={handleSubmit} />

        {error && (
          <div role="alert" className="alert alert-error alert-soft py-2.5 text-sm">
            <span>{error}</span>
          </div>
        )}

        {analysis && (
          <>
            <div className="h-px bg-base-300/70" />
            <SummaryPanel summary={analysis.summary} />
          </>
        )}

        <footer className="mt-auto space-y-2 border-t border-base-300/60 pt-4 text-[11px] leading-relaxed opacity-45">
          <p>
            Wo dich der Wind auf der Route trifft, ist gegen aufgezeichnete Fahrten
            geprüft. Wie stark er sich anfühlt, hängt an Hecken, Senken und Bebauung und
            lässt sich aus einer Vorhersage nicht zuverlässig ableiten.
          </p>
          <p>
            Wetter von{' '}
            <a href="https://open-meteo.com/" target="_blank" rel="noopener" className="link">
              Open-Meteo
            </a>
            , Karte von OpenStreetMap.
          </p>
        </footer>
      </aside>

      <main className="relative min-h-[55vh] flex-1">
        {analysis ? <RouteMap segments={analysis.segments} /> : <EmptyState busy={busy} />}
      </main>
    </div>
  )
}

function WindMark() {
  return (
    <div className="grid size-9 shrink-0 place-items-center rounded-box bg-primary/12 text-primary">
      <svg
        width="19"
        height="19"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.9"
        strokeLinecap="round"
      >
        <path d="M3 8h9.5a2.8 2.8 0 1 0-2.8-2.8" />
        <path d="M3 12.5h13a2.8 2.8 0 1 1-2.8 2.8" />
        <path d="M3 17h6.5" />
      </svg>
    </div>
  )
}

function EmptyState({ busy }: { busy: boolean }) {
  return (
    <div className="flex h-full items-center justify-center bg-gradient-to-b from-base-200 to-base-300/40 p-8 text-center">
      <div className="max-w-xs space-y-3">
        {busy ? (
          <span className="loading loading-ring loading-lg text-primary" />
        ) : (
          <svg
            className="mx-auto text-base-content/15"
            width="52"
            height="52"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
          >
            <path d="M2.5 8h10a3 3 0 1 0-3-3" />
            <path d="M2.5 12.5h14a3 3 0 1 1-3 3" />
            <path d="M2.5 17h7" />
          </svg>
        )}
        <h2 className="text-base font-medium opacity-70">
          {busy ? 'Route wird ausgewertet …' : 'Lade eine GPX-Datei hoch'}
        </h2>
        <p className="text-sm leading-relaxed opacity-45">
          Aeolus schätzt, wann du wo sein wirst, und holt die Vorhersage für genau diese
          Zeitpunkte — statt für den Tag insgesamt.
        </p>
      </div>
    </div>
  )
}
