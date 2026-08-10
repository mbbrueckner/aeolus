import { useEffect, useMemo } from 'react'
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import type { Segment } from '../types'
import {
  ALIGNMENT_COLOUR,
  ALIGNMENT_LABEL,
  RAIN_COLOUR,
  RAIN_LABEL,
  RAIN_WIDTH,
  arrowRotation,
  formatTime,
  isNotable,
  segmentColour,
} from '../wind'

interface Props {
  segments: Segment[]
}

export function RouteMap({ segments }: Props) {
  const wet = segments.some((segment) => segment.rain_tier !== null)

  return (
    <div className="relative h-full w-full">
      <MapContainer
        center={[48.14, 11.58]}
        zoom={11}
        scrollWheelZoom
        className="h-full w-full"
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        />

        {/* Rain first, so it sits underneath the wind-coloured route. */}
        {segments.map((segment, index) =>
          segment.rain_tier ? (
            <Polyline
              key={`rain-${index}`}
              positions={segment.coordinates}
              pathOptions={{
                color: RAIN_COLOUR[segment.rain_tier],
                weight: RAIN_WIDTH[segment.rain_tier],
                opacity: 0.45,
                lineCap: 'round',
              }}
            />
          ) : null,
        )}

        {segments.map((segment, index) => (
          <Polyline
            key={`line-${index}`}
            positions={segment.coordinates}
            pathOptions={{
              color: segmentColour(segment),
              weight: 6,
              opacity: 0.9,
              dashArray: segment.unsafe ? '10 8' : undefined,
            }}
          />
        ))}

        {segments.map((segment, index) => (
          <Marker key={`arrow-${index}`} position={segment.point} icon={windIcon(segment)}>
            <Popup>
              <SegmentPopup segment={segment} />
            </Popup>
          </Marker>
        ))}

        <FitToRoute segments={segments} />
      </MapContainer>

      <Legend showRain={wet} />
    </div>
  )
}

function Legend({ showRain }: { showRain: boolean }) {
  return (
    <div className="pointer-events-none absolute bottom-6 left-4 z-1000 rounded-box border border-base-300/60 bg-base-100/92 px-3.5 py-2.5 text-xs shadow-lg backdrop-blur-sm">
      <p className="mb-1.5 font-medium opacity-55">Wind auf der Route</p>
      <ul className="space-y-1">
        {(['headwind', 'crosswind', 'tailwind'] as const).map((alignment) => (
          <li key={alignment} className="flex items-center gap-2">
            <span
              className="h-1 w-6 rounded-full"
              style={{ background: ALIGNMENT_COLOUR[alignment] }}
            />
            {ALIGNMENT_LABEL[alignment]}
          </li>
        ))}
        <li className="flex items-center gap-2 opacity-60">
          <span className="h-1 w-6 rounded-full bg-slate-400" />
          kaum Wind
        </li>
      </ul>

      {showRain && (
        <>
          <p className="mt-2.5 mb-1.5 font-medium opacity-55">Niederschlag</p>
          <ul className="space-y-1">
            {(['light', 'moderate', 'heavy'] as const).map((tier) => (
              <li key={tier} className="flex items-center gap-2">
                <span
                  className="h-2.5 w-6 rounded-full"
                  style={{ background: RAIN_COLOUR[tier], opacity: 0.55 }}
                />
                {RAIN_LABEL[tier]}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

function SegmentPopup({ segment }: { segment: Segment }) {
  return (
    <div className="min-w-52 text-sm">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <span className="font-semibold">{formatTime(segment.time)}</span>
        <span className="opacity-55">{segment.distance_km.toFixed(1)} km</span>
      </div>

      <dl className="space-y-1">
        <Row
          label="Wind"
          value={`${segment.wind_speed_km_h.toFixed(0)} km/h`}
          accent={isNotable(segment) ? ALIGNMENT_COLOUR[segment.alignment] : undefined}
          note={isNotable(segment) ? ALIGNMENT_LABEL[segment.alignment] : 'schwach'}
        />
        <Row label="Böen" value={`${segment.wind_gusts_km_h.toFixed(0)} km/h`} />
        <Row
          label="Regen"
          value={
            segment.rain_tier ? `${segment.precipitation_mm_h.toFixed(1)} mm/h` : 'trocken'
          }
          accent={segment.rain_tier ? RAIN_COLOUR[segment.rain_tier] : undefined}
          note={segment.rain_tier ? RAIN_LABEL[segment.rain_tier] : undefined}
        />
      </dl>

      {segment.unsafe && (
        <p className="mt-2 rounded-md bg-error/15 px-2 py-1 text-xs font-medium text-error">
          Kritische Bedingungen
        </p>
      )}
    </div>
  )
}

function Row({
  label,
  value,
  note,
  accent,
}: {
  label: string
  value: string
  note?: string
  accent?: string
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="opacity-55">{label}</dt>
      <dd className="text-right font-medium" style={accent ? { color: accent } : undefined}>
        {value}
        {note && <span className="ml-1 text-xs font-normal opacity-70">{note}</span>}
      </dd>
    </div>
  )
}

/** Pan and zoom so the whole route is visible whenever it changes. */
function FitToRoute({ segments }: { segments: Segment[] }) {
  const map = useMap()

  const bounds = useMemo(() => {
    const points = segments.flatMap((segment) => segment.coordinates)
    return points.length ? L.latLngBounds(points) : null
  }, [segments])

  useEffect(() => {
    if (bounds) {
      map.fitBounds(bounds, { padding: [40, 40] })
    }
  }, [bounds, map])

  return null
}

/** An arrow pointing where the wind is blowing, labelled with its speed. */
function windIcon(segment: Segment): L.DivIcon {
  const colour = isNotable(segment) ? ALIGNMENT_COLOUR[segment.alignment] : '#64748b'
  const rotation = arrowRotation(segment.wind_direction_deg)
  const drop = segment.rain_tier
    ? `<span style="color:${RAIN_COLOUR[segment.rain_tier]};font-size:9px;">&#9679;</span>`
    : ''

  return L.divIcon({
    className: '',
    iconSize: [46, 46],
    iconAnchor: [23, 23],
    html: `
      <div style="display:flex;flex-direction:column;align-items:center;line-height:1;gap:1px;">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none"
             style="transform:rotate(${rotation}deg);filter:drop-shadow(0 1px 2px oklch(0% 0 0 / .3))">
          <path d="M12 3 L12 21 M12 3 L7 9 M12 3 L17 9"
                stroke="${colour}" stroke-width="3.2"
                stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span style="font-size:10px;font-weight:600;color:${colour};
                     background:color-mix(in oklch, var(--color-base-100) 85%, transparent);
                     border-radius:4px;padding:1px 4px;white-space:nowrap;
                     box-shadow:0 1px 3px oklch(0% 0 0 / .18);">
          ${segment.wind_speed_km_h.toFixed(0)}${drop}
        </span>
      </div>`,
  })
}
