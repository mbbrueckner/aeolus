interface Props {
  value: Date
  onChange: (value: Date) => void
  days?: number
}

const SLOT_MINUTES = 15
const SLOTS_PER_DAY = (24 * 60) / SLOT_MINUTES

/**
 * A departure picker built from a select and a slider.
 *
 * The native datetime-local control is drawn by the browser and ignores the
 * page's styling, which left it looking out of place. Its granularity is also
 * wrong here: the forecast comes in quarter hours, so that is what the slider
 * steps in.
 */
export function DepartureField({ value, onChange, days = 7 }: Props) {
  const today = startOfDay(new Date())
  const chosenDay = startOfDay(value)
  const slot = Math.round((value.getTime() - chosenDay.getTime()) / (SLOT_MINUTES * 60_000))

  const options = Array.from({ length: days }, (_, offset) => {
    const day = new Date(today)
    day.setDate(day.getDate() + offset)
    return day
  })

  function setDay(day: Date) {
    const next = new Date(day)
    next.setMinutes(slot * SLOT_MINUTES, 0, 0)
    onChange(next)
  }

  function setSlot(next: number) {
    const updated = new Date(chosenDay)
    updated.setMinutes(next * SLOT_MINUTES, 0, 0)
    onChange(updated)
  }

  return (
    <div className="space-y-3">
      <label className="block">
        <span className="mb-1.5 block text-sm font-medium opacity-75">Tag</span>
        <select
          className="select select-sm w-full"
          value={chosenDay.getTime()}
          onChange={(event) => setDay(new Date(Number(event.target.value)))}
        >
          {options.map((day, offset) => (
            <option key={day.getTime()} value={day.getTime()}>
              {labelFor(day, offset)}
            </option>
          ))}
        </select>
      </label>

      <label className="block">
        <span className="mb-1.5 flex items-baseline justify-between text-sm font-medium">
          <span className="opacity-75">Uhrzeit</span>
          <span className="tabular-nums opacity-60">
            {value.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
          </span>
        </span>
        <input
          type="range"
          min={0}
          max={SLOTS_PER_DAY - 1}
          step={1}
          value={slot}
          aria-label="Uhrzeit"
          className="range range-primary range-xs"
          onChange={(event) => setSlot(Number(event.target.value))}
        />
        <div className="mt-0.5 flex justify-between px-0.5 text-[10px] opacity-35">
          <span>00:00</span>
          <span>12:00</span>
          <span>23:45</span>
        </div>
      </label>
    </div>
  )
}

function startOfDay(date: Date): Date {
  const copy = new Date(date)
  copy.setHours(0, 0, 0, 0)
  return copy
}

function labelFor(day: Date, offset: number): string {
  if (offset === 0) return 'Heute'
  if (offset === 1) return 'Morgen'
  return day.toLocaleDateString(undefined, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })
}
