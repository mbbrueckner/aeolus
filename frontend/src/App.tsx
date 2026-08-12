import { useEffect, useMemo, useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { analyseRoute } from './api'
import { ControlPanel } from './components/ControlPanel'
import { RouteMap } from './components/RouteMap'
import { SummaryPanel } from './components/SummaryPanel'
import { LanguageToggle } from './components/LanguageToggle'
import { ThemeToggle } from './components/ThemeToggle'
import { slotIndexAt, summariseAtSlot, timeAtSlot } from './field'
import { useTheme } from './theme'
import type { Analysis } from './types'

export default function App() {
  const { t } = useTranslation()
  const { preference, setPreference } = useTheme()
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [slot, setSlot] = useState(0)
  const [playing, setPlaying] = useState(false)

  // Open on the departure time when there is one, otherwise on now.
  useEffect(() => {
    if (!analysis?.field) return
    setPlaying(false)
    const start = analysis.segments.find((segment) => segment.time)?.time
    setSlot(slotIndexAt(analysis.field, start ? new Date(start) : new Date()))
  }, [analysis])

  const shownTime = analysis?.field ? timeAtSlot(analysis.field, slot) : null
  const live = useMemo(() => {
    if (!analysis?.field) return null
    return summariseAtSlot(analysis.segments, analysis.field, slot)
  }, [analysis, slot])

  async function handleSubmit(
    gpx: File,
    ride: { avgSpeedKmh: number; startTime: string } | null,
  ) {
    setBusy(true)
    setError(null)
    try {
      setAnalysis(
        await analyseRoute({
          gpx,
          avgSpeedKmh: ride?.avgSpeedKmh,
          startTime: ride?.startTime,
        }),
      )
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
              <p className="text-xs opacity-55">{t('app.tagline')}</p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1.5">
            <ThemeToggle preference={preference} onChange={setPreference} />
            <LanguageToggle />
          </div>
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
            <SummaryPanel live={live} shownTime={shownTime} summary={analysis.summary} />
          </>
        )}

        <footer className="mt-auto space-y-2 border-t border-base-300/60 pt-4 text-[11px] leading-relaxed opacity-45">
          <p>{t('app.disclaimer')}</p>
          <p>
            <Trans
              i18nKey="app.builtBy"
              components={[
                <a
                  key="site"
                  href="https://mbrueckner.dev/"
                  target="_blank"
                  rel="noopener"
                  className="link"
                />,
                <a
                  key="source"
                  href="https://github.com/mbbrueckner/aeolus"
                  target="_blank"
                  rel="noopener"
                  className="link inline-flex items-center gap-1"
                >
                  <GitHubMark />
                </a>,
              ]}
            />
          </p>
          <p>
            <Trans
              i18nKey="app.attribution"
              components={[
                <a
                  key="open-meteo"
                  href="https://open-meteo.com/"
                  target="_blank"
                  rel="noopener"
                  className="link"
                />,
              ]}
            />
          </p>
        </footer>
      </aside>

      <main className="relative min-h-[55vh] flex-1">
        {analysis ? (
          <RouteMap
            analysis={analysis}
            slot={slot}
            onSlotChange={setSlot}
            playing={playing}
            onPlayingChange={setPlaying}
          />
        ) : (
          <EmptyState busy={busy} />
        )}
      </main>
    </div>
  )
}

function GitHubMark() {
  return (
    <>
      <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38
          0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01
          1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95
          0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.4 7.4 0 0 1 2-.27c.68 0
          1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0
          3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0
          .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
      </svg>
    </>
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
  const { t } = useTranslation()

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
          {busy ? t('empty.analysing') : t('empty.prompt')}
        </h2>
        <p className="text-sm leading-relaxed opacity-45">{t('empty.hint')}</p>
      </div>
    </div>
  )
}
