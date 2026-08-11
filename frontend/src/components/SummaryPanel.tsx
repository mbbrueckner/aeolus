import { Trans, useTranslation } from 'react-i18next'
import type { LiveSummary } from '../field'
import type { RainTier, Summary } from '../types'
import { ALIGNMENT_COLOUR, RAIN_COLOUR, RAIN_KEY, formatKm, formatTime } from '../wind'

interface Props {
  live: LiveSummary | null
  shownTime: Date | null
  summary: Summary | null
}

export function SummaryPanel({ live, shownTime, summary }: Props) {
  return (
    <div className="space-y-5">
      {live && <AtThisMoment live={live} shownTime={shownTime} />}
      {summary && <OnYourRide summary={summary} />}
    </div>
  )
}

/** The whole route as it stands at the moment shown on the map. */
function AtThisMoment({ live, shownTime }: { live: LiveSummary; shownTime: Date | null }) {
  const { t } = useTranslation()

  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold">{t('summary.onRoute')}</h2>
        <span className="text-xs opacity-50">
          {shownTime
            ? t('summary.at', {
                time: shownTime.toLocaleTimeString(undefined, {
                  hour: '2-digit',
                  minute: '2-digit',
                }),
              })
            : ''}{' '}
          · {formatKm(live.totalKm)} km
        </span>
      </div>

      <div className="space-y-2.5">
        <Bar label={t('wind.headwind')} km={live.headwindKm} total={live.totalKm} colour={ALIGNMENT_COLOUR.headwind} />
        <Bar label={t('wind.crosswind')} km={live.crosswindKm} total={live.totalKm} colour={ALIGNMENT_COLOUR.crosswind} />
        <Bar label={t('wind.tailwind')} km={live.tailwindKm} total={live.totalKm} colour={ALIGNMENT_COLOUR.tailwind} />
        <Bar label={t('wind.calm')} km={live.calmKm} total={live.totalKm} colour="currentColor" muted />
      </div>

      <div className="grid grid-cols-2 gap-2.5">
        <Tile label={t('summary.meanWind')} value={live.meanWindKmH.toFixed(0)} unit="km/h" />
        <Tile
          label={t('summary.rainRisk')}
          value={live.maxProbability.toFixed(0)}
          unit="%"
          muted={live.maxProbability < 15}
        />
      </div>

      {live.rainKm > 0.05 ? (
        <p className="rounded-box border border-info/25 bg-info/8 px-3.5 py-2.5 text-sm text-info">
          <Trans
            i18nKey="summary.rainOnRoute"
            values={{ km: formatKm(live.rainKm), peak: live.maxRainMmH.toFixed(1) }}
            components={[<strong key="km" />]}
          />
        </p>
      ) : (
        <p className="rounded-box border border-base-300/60 bg-base-200/40 px-3.5 py-2.5 text-sm opacity-60">
          {t('summary.dryEverywhere')}
        </p>
      )}
    </section>
  )
}

/** What the rider is expected to meet, given a departure time and speed. */
function OnYourRide({ summary }: { summary: Summary }) {
  const { t } = useTranslation()

  return (
    <section className="space-y-4 rounded-box border border-primary/25 bg-primary/5 px-3.5 py-3.5">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-primary">{t('summary.onRide')}</h2>
        <span className="text-xs opacity-55">
          {t('summary.arriving', { time: formatTime(summary.arrival) })}
        </span>
      </div>

      <div className="space-y-2.5">
        <Bar label={t('wind.headwind')} km={summary.headwind_km} total={summary.total_distance_km} colour={ALIGNMENT_COLOUR.headwind} />
        <Bar label={t('wind.crosswind')} km={summary.crosswind_km} total={summary.total_distance_km} colour={ALIGNMENT_COLOUR.crosswind} />
        <Bar label={t('wind.tailwind')} km={summary.tailwind_km} total={summary.total_distance_km} colour={ALIGNMENT_COLOUR.tailwind} />
      </div>

      <RainSection summary={summary} />

      {summary.unsafe_km > 0.1 && (
        <p className="rounded-box border border-error/25 bg-error/10 px-3.5 py-2.5 text-sm text-error">
          <Trans
            i18nKey="summary.unsafe"
            values={{ km: formatKm(summary.unsafe_km) }}
            components={[<strong key="km" />]}
          />
        </p>
      )}

      <details className="group rounded-box bg-base-200/60">
        <summary className="flex cursor-pointer list-none items-center justify-between px-3.5 py-2.5 text-sm">
          <span className="opacity-70">{t('summary.score')}</span>
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
          {t('summary.scoreNote')}
        </p>
      </details>
    </section>
  )
}

function RainSection({ summary }: { summary: Summary }) {
  const { t } = useTranslation()

  if (summary.rain_km <= 0.05) {
    return <p className="text-sm opacity-60">{t('summary.dryThroughout')}</p>
  }

  const tiers: { tier: RainTier; km: number }[] = [
    { tier: 'light', km: summary.light_rain_km },
    { tier: 'moderate', km: summary.moderate_rain_km },
    { tier: 'heavy', km: summary.heavy_rain_km },
  ]

  return (
    <div className="space-y-2 rounded-box border border-info/25 bg-info/10 px-3 py-2.5">
      {summary.rain_start_km !== null && (
        <p className="text-sm leading-snug">
          <Trans
            i18nKey={summary.rain_start_time ? 'summary.rainFromAt' : 'summary.rainFrom'}
            values={{
              km: formatKm(summary.rain_start_km),
              time: formatTime(summary.rain_start_time),
            }}
            components={[<strong key="km" />]}
          />
        </p>
      )}
      <ul className="space-y-1">
        {tiers
          .filter(({ km }) => km > 0.05)
          .map(({ tier, km }) => (
            <li key={tier} className="flex items-center gap-2 text-sm">
              <span
                className="h-2 w-5 shrink-0 rounded-full"
                style={{ background: RAIN_COLOUR[tier] }}
              />
              <span className="opacity-70">{t(RAIN_KEY[tier])}</span>
              <span className="ml-auto font-semibold tabular-nums">
                {formatKm(km)}
                <span className="ml-1 text-xs font-normal opacity-45">km</span>
              </span>
            </li>
          ))}
      </ul>
    </div>
  )
}

function Bar({
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
          className="h-full rounded-full transition-[width] duration-500 ease-out"
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

function Tile({
  label,
  value,
  unit,
  muted = false,
}: {
  label: string
  value: string
  unit: string
  muted?: boolean
}) {
  return (
    <div
      className={`rounded-box border border-base-300/60 bg-base-200/40 px-3.5 py-2.5 ${
        muted ? 'opacity-55' : ''
      }`}
    >
      <div className="text-[11px] opacity-55">{label}</div>
      <div className="mt-0.5 text-xl leading-none font-semibold tabular-nums">
        {value}
        <span className="ml-1 text-xs font-normal opacity-45">{unit}</span>
      </div>
    </div>
  )
}
