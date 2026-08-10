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
    <section className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold tracking-wide uppercase opacity-60">
          Auf deiner Route
        </h2>
        <span className="text-xs opacity-60">
          {formatKm(summary.total_distance_km)} km · an {formatTime(summary.arrival)}
        </span>
      </div>

      <div className="space-y-2">
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
          colour="#94a3b8"
        />
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Tile label="Wind im Mittel" value={`${summary.mean_wind_km_h.toFixed(0)} km/h`} />
        <Tile label="stärkste Böe" value={`${summary.max_gust_km_h.toFixed(0)} km/h`} />
      </div>

      {summary.rain_km > 0.1 && (
        <div className="alert alert-info alert-soft py-2 text-sm">
          <span>
            Regen auf <strong>{formatKm(summary.rain_km)} km</strong> deiner Strecke
            {summary.rain_share > 0.5 && ' — auf dem Großteil also'}
          </span>
        </div>
      )}

      {summary.unsafe_km > 0.1 && (
        <div className="alert alert-error alert-soft py-2 text-sm">
          <span>
            Auf <strong>{formatKm(summary.unsafe_km)} km</strong> sind die Bedingungen
            kritisch — auf der Karte gestrichelt.
          </span>
        </div>
      )}

      <details className="collapse-arrow collapse bg-base-200/60">
        <summary className="collapse-title min-h-0 py-2 text-sm font-medium">
          Gesamtbewertung: {summary.score >= 0 ? '+' : ''}
          {summary.score.toFixed(2)}
        </summary>
        <div className="collapse-content text-xs leading-relaxed opacity-70">
          <p>
            Eine zusammenfassende Zahl von −1 bis +1. Sie ist noch nicht gegen echte
            Fahrten kalibriert — verlass dich lieber auf die Kilometerangaben oben, die
            kannst du nach der Fahrt überprüfen.
          </p>
        </div>
      </details>
    </section>
  )
}

function WindBar({
  label,
  km,
  total,
  colour,
}: {
  label: string
  km: number
  total: number
  colour: string
}) {
  const share = total > 0 ? km / total : 0

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between text-sm">
        <span className="opacity-70">{label}</span>
        <span className="font-semibold tabular-nums">
          {formatKm(km)} km
          <span className="ml-1.5 text-xs font-normal opacity-60">
            {(share * 100).toFixed(0)} %
          </span>
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-base-300">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${Math.max(share * 100, share > 0 ? 2 : 0)}%`, background: colour }}
        />
      </div>
    </div>
  )
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-base-200/60 px-3 py-2">
      <div className="text-xs opacity-60">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
    </div>
  )
}
