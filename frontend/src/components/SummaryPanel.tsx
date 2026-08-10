import type { Summary } from '../types'
import { ALIGNMENT_COLOUR, formatKm, formatTime } from '../wind'

interface Props {
  summary: Summary
}

export function SummaryPanel({ summary }: Props) {
  const calmKm = Math.max(
    0,
    summary.total_distance_km -
      summary.headwind_km -
      summary.tailwind_km -
      summary.crosswind_km,
  )

  return (
    <section className="space-y-5">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold">Auf deiner Route</h2>
        <span className="text-xs opacity-50">
          {formatKm(summary.total_distance_km)} km · an {formatTime(summary.arrival)}
        </span>
      </div>

      <div className="space-y-2.5">
        <WindBar
          label="Gegenwind"
          km={summary.headwind_km}
          total={summary.total_distance_km}
          colour={ALIGNMENT_COLOUR.headwind}
        />
        <WindBar
          label="Seitenwind"
          km={summary.crosswind_km}
          total={summary.total_distance_km}
          colour={ALIGNMENT_COLOUR.crosswind}
        />
        <WindBar
          label="Rückenwind"
          km={summary.tailwind_km}
          total={summary.total_distance_km}
          colour={ALIGNMENT_COLOUR.tailwind}
        />
        <WindBar
          label="kaum Wind"
          km={calmKm}
          total={summary.total_distance_km}
          colour="currentColor"
          muted
        />
      </div>

      <div className="grid grid-cols-2 gap-2.5">
        <Tile label="Wind im Mittel" value={summary.mean_wind_km_h.toFixed(0)} unit="km/h" />
        <Tile label="stärkste Böe" value={summary.max_gust_km_h.toFixed(0)} unit="km/h" />
      </div>

      {summary.rain_km > 0.1 && (
        <Notice tone="info">
          Regen auf <strong>{formatKm(summary.rain_km)} km</strong>
          {summary.rain_share > 0.5 ? ' — also auf dem Großteil der Strecke' : ' deiner Strecke'}
        </Notice>
      )}

      {summary.unsafe_km > 0.1 && (
        <Notice tone="error">
          Auf <strong>{formatKm(summary.unsafe_km)} km</strong> sind die Bedingungen
          kritisch — auf der Karte gestrichelt.
        </Notice>
      )}

      <details className="group rounded-box bg-base-200/60">
        <summary className="flex cursor-pointer list-none items-center justify-between px-3.5 py-2.5 text-sm">
          <span className="opacity-70">Gesamtbewertung</span>
          <span className="flex items-center gap-1.5 font-semibold tabular-nums">
            {summary.score >= 0 ? '+' : ''}
            {summary.score.toFixed(2)}
            <svg
              className="opacity-40 transition-transform group-open:rotate-180"
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </span>
        </summary>
        <p className="px-3.5 pb-3 text-xs leading-relaxed opacity-60">
          Eine zusammenfassende Zahl von −1 bis +1. Sie ist noch nicht gegen echte
          Fahrten kalibriert — verlass dich lieber auf die Kilometer oben, die kannst du
          nach der Fahrt überprüfen.
        </p>
      </details>
    </section>
  )
}

function WindBar({
  label,
  km,
  total,
  colour,
  muted = false,
}: {
  label: string
  km: number
  total: number
  colour: string
  muted?: boolean
}) {
  const share = total > 0 ? km / total : 0
  const empty = km < 0.05

  return (
    <div className={empty ? 'opacity-35' : undefined}>
      <div className="mb-1 flex items-baseline justify-between text-sm">
        <span className="opacity-70">{label}</span>
        <span className="font-semibold tabular-nums">
          {formatKm(km)}
          <span className="ml-1 text-xs font-normal opacity-45">km</span>
          <span className="ml-2 inline-block w-9 text-right text-xs font-normal opacity-45">
            {(share * 100).toFixed(0)} %
          </span>
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-base-300/70">
        <div
          className="h-full rounded-full transition-[width] duration-700 ease-out"
          style={{
            width: `${share > 0 ? Math.max(share * 100, 2) : 0}%`,
            background: colour,
            opacity: muted ? 0.3 : 1,
          }}
        />
      </div>
    </div>
  )
}

function Tile({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="rounded-box border border-base-300/60 bg-base-200/40 px-3.5 py-2.5">
      <div className="text-[11px] opacity-55">{label}</div>
      <div className="mt-0.5 text-xl leading-none font-semibold tabular-nums">
        {value}
        <span className="ml-1 text-xs font-normal opacity-45">{unit}</span>
      </div>
    </div>
  )
}

function Notice({ tone, children }: { tone: 'info' | 'error'; children: React.ReactNode }) {
  const styles =
    tone === 'error'
      ? 'border-error/25 bg-error/10 text-error'
      : 'border-info/25 bg-info/10 text-info'

  return (
    <p className={`rounded-box border px-3.5 py-2.5 text-sm leading-snug ${styles}`}>
      {children}
    </p>
  )
}
