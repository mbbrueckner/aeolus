import { useState } from 'react'
import { analyseRoute } from './api'
import { ControlPanel } from './components/ControlPanel'
import { RouteMap } from './components/RouteMap'
import { SummaryPanel } from './components/SummaryPanel'
import type { Analysis } from './types'

export default function App() {
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
      <aside className="flex w-full shrink-0 flex-col gap-5 overflow-y-auto bg-base-100 p-5 shadow-xl lg:w-96">
        <header>
          <h1 className="text-2xl font-bold tracking-tight">Aeolus</h1>
          <p className="text-sm opacity-60">Wetter entlang deiner Route</p>
        </header>

        <ControlPanel busy={busy} onSubmit={handleSubmit} />

        {error && (
          <div className="alert alert-error alert-soft py-2 text-sm">
            <span>{error}</span>
          </div>
        )}

        {analysis && <SummaryPanel summary={analysis.summary} />}

        <footer className="mt-auto space-y-2 pt-4 text-xs leading-relaxed opacity-50">
          <p>
            Wo dich der Wind auf der Route trifft, ist gegen aufgezeichnete Fahrten
            geprüft. Wie stark er sich anfühlt, hängt stark von Hecken, Senken und
            Bebauung ab und lässt sich aus einer Vorhersage nicht zuverlässig ableiten.
          </p>
          <p>
            Wetterdaten von{' '}
            <a
              href="https://open-meteo.com/"
              target="_blank"
              rel="noopener"
              className="link"
            >
              Open-Meteo
            </a>
            , Karte von OpenStreetMap.
          </p>
        </footer>
      </aside>

      <main className="relative min-h-[60vh] flex-1">
        {analysis ? (
          <RouteMap segments={analysis.segments} />
        ) : (
          <EmptyState busy={busy} />
        )}
      </main>
    </div>
  )
}

function EmptyState({ busy }: { busy: boolean }) {
  return (
    <div className="flex h-full items-center justify-center p-8 text-center">
      <div className="max-w-sm space-y-3">
        <div className="text-5xl opacity-20">🌬️</div>
        <h2 className="text-lg font-semibold opacity-70">
          {busy ? 'Route wird ausgewertet …' : 'Lade eine GPX-Datei hoch'}
        </h2>
        <p className="text-sm opacity-50">
          Aeolus schätzt, wann du wo bist, und holt die Vorhersage für genau diese
          Zeitpunkte — statt für den Tag insgesamt.
        </p>
      </div>
    </div>
  )
}
