import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { DepartureField } from './DepartureField'

interface Props {
  busy: boolean
  onSubmit: (gpx: File, ride: { avgSpeedKmh: number; startTime: string } | null) => void
}

/** Now, rounded up to the next quarter hour the forecast is published for. */
function nextQuarterHour(): Date {
  const now = new Date()
  now.setMinutes(Math.ceil(now.getMinutes() / 15) * 15, 0, 0)
  return now
}

export function ControlPanel({ busy, onSubmit }: Props) {
  const { t } = useTranslation()
  const [file, setFile] = useState<File | null>(null)
  const [planRide, setPlanRide] = useState(false)
  const [speed, setSpeed] = useState(22)
  const [start, setStart] = useState(nextQuarterHour)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function accept(dropped: File | null | undefined) {
    if (dropped && dropped.name.toLowerCase().endsWith('.gpx')) setFile(dropped)
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault()
        if (file) {
          // toISOString carries the zone, so the server does not read a local
          // wall-clock time as UTC.
          onSubmit(
            file,
            planRide ? { avgSpeedKmh: speed, startTime: start.toISOString() } : null,
          )
        }
      }}
    >
      <div
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          accept(event.dataTransfer.files?.[0])
        }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-box border border-dashed px-4 py-5 text-center transition-colors ${
          dragging
            ? 'border-primary bg-primary/8'
            : file
              ? 'border-primary/40 bg-primary/5'
              : 'border-base-300 bg-base-200/50 hover:border-base-content/25 hover:bg-base-200'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".gpx"
          className="hidden"
          onChange={(event) => accept(event.target.files?.[0])}
        />

        {file ? (
          <>
            <p className="truncate text-sm font-medium">{file.name}</p>
            <p className="mt-0.5 text-xs opacity-50">
              {t('controls.changeFile', { size: (file.size / 1024).toFixed(0) })}
            </p>
          </>
        ) : (
          <>
            <svg
              className="mx-auto mb-1.5 opacity-30"
              width="26"
              height="26"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 15V4M12 4 8 8M12 4l4 4" />
              <path d="M4 15v3.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V15" />
            </svg>
            <p className="text-sm font-medium">{t('controls.drop')}</p>
            <p className="mt-0.5 text-xs opacity-50">{t('controls.dropHint')}</p>
          </>
        )}
      </div>

      <div className="rounded-box border border-base-300/60">
        <label className="flex cursor-pointer items-center gap-3 px-3.5 py-2.5">
          <input
            type="checkbox"
            checked={planRide}
            onChange={(event) => setPlanRide(event.target.checked)}
            className="toggle toggle-primary toggle-sm"
          />
          <span className="flex-1">
            <span className="block text-sm font-medium">{t('controls.planRide')}</span>
            <span className="block text-xs opacity-50">
              {planRide ? t('controls.planRideOn') : t('controls.planRideOff')}
            </span>
          </span>
        </label>

        {planRide && (
          <div className="space-y-4 border-t border-base-300/60 px-3.5 py-3.5">
            <DepartureField value={start} onChange={setStart} />

            <label className="block">
              <span className="mb-1.5 flex items-baseline justify-between text-sm font-medium">
                <span className="opacity-75">{t('controls.speed')}</span>
                <span className="tabular-nums opacity-60">{speed.toFixed(1)} km/h</span>
              </span>
              <input
                type="range"
                min={10}
                max={45}
                step={0.5}
                value={speed}
                className="range range-primary range-xs"
                onChange={(event) => setSpeed(Number(event.target.value))}
              />
            </label>
          </div>
        )}
      </div>

      <button type="submit" className="btn btn-primary w-full" disabled={!file || busy}>
        {busy && <span className="loading loading-spinner loading-sm" />}
        {busy ? t('controls.submitting') : t('controls.submit')}
      </button>
    </form>
  )
}
