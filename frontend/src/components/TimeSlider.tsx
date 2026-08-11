import { useEffect, useRef } from 'react'
import { timeAtSlot } from '../field'
import type { Field } from '../types'

interface Props {
  field: Field
  slot: number
  onSlotChange: (slot: number) => void
  playing: boolean
  onPlayingChange: (playing: boolean) => void
  rideStart: Date | null
  rideEnd: Date | null
}

// Playback advances in small steps so the rider glides rather than teleports.
const FRAME_MS = 60
const SLOTS_PER_FRAME = 0.09

/** One minute, as a fraction of a quarter-hour slot. */
const MINUTE = 1 / 15

export function TimeSlider({
  field,
  slot,
  onSlotChange,
  playing,
  onPlayingChange,
  rideStart,
  rideEnd,
}: Props) {
  const last = field.slots.length - 1
  const slotRef = useRef(slot)
  slotRef.current = slot

  useEffect(() => {
    if (!playing) return
    const timer = window.setInterval(() => {
      const next = slotRef.current + SLOTS_PER_FRAME
      onSlotChange(next >= last ? 0 : next)
    }, FRAME_MS)
    return () => window.clearInterval(timer)
  }, [playing, last, onSlotChange])

  const current = timeAtSlot(field, slot)
  const rideRange = rideWindow(field, rideStart, rideEnd)

  return (
    <div className="pointer-events-auto absolute inset-x-3 bottom-3 z-1000 rounded-box border border-base-300/60 bg-base-100/93 px-4 py-3 shadow-lg backdrop-blur-sm sm:inset-x-auto sm:right-4 sm:left-4">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => onPlayingChange(!playing)}
          aria-label={playing ? 'Pause' : 'Abspielen'}
          className="btn btn-circle btn-primary btn-sm shrink-0"
        >
          {playing ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="5" width="4" height="14" rx="1" />
              <rect x="14" y="5" width="4" height="14" rx="1" />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5.5v13l11-6.5z" />
            </svg>
          )}
        </button>

        <div className="min-w-0 flex-1">
          <div className="mb-1 flex items-baseline justify-between gap-2 text-sm">
            <span className="font-semibold tabular-nums">
              {current.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
            </span>
            <span className="truncate text-xs opacity-50">
              {current.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })}
            </span>
          </div>

          <div className="relative">
            {rideRange && (
              <div
                className="pointer-events-none absolute inset-y-0 rounded-full bg-primary/25"
                style={{
                  left: `${rideRange.from * 100}%`,
                  width: `${Math.max(rideRange.to - rideRange.from, 0.01) * 100}%`,
                }}
                aria-hidden
              />
            )}
            <input
              type="range"
              min={0}
              max={last}
              step={MINUTE}
              value={slot}
              aria-label="Uhrzeit"
              className="range range-primary range-xs relative w-full"
              onChange={(event) => {
                onPlayingChange(false)
                onSlotChange(Number(event.target.value))
              }}
            />
          </div>

          <div className="mt-0.5 flex justify-between text-[10px] opacity-40">
            <span>{formatSlot(field.slots[0])}</span>
            {rideRange && <span className="text-primary opacity-80">deine Fahrt</span>}
            <span>{formatSlot(field.slots[last])}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

/** Where the ride sits within the field's time range, as fractions from 0 to 1. */
function rideWindow(field: Field, start: Date | null, end: Date | null) {
  if (!start || !end || field.slots.length < 2) return null

  const first = field.slots[0]
  const span = field.slots[field.slots.length - 1] - first
  if (span <= 0) return null

  const from = (start.getTime() / 1000 - first) / span
  const to = (end.getTime() / 1000 - first) / span

  if (to < 0 || from > 1) return null
  return { from: Math.max(0, from), to: Math.min(1, to) }
}

function formatSlot(unix: number): string {
  return new Date(unix * 1000).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  })
}
