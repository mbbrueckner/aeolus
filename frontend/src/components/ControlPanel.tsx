import { useRef, useState } from 'react'

interface Props {
  busy: boolean
  onSubmit: (gpx: File, avgSpeedKmh: number, startTime: string) => void
}

/** Local wall-clock time in the format a datetime-local input expects. */
function nowForInput(): string {
  const now = new Date()
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset(), 0, 0)
  return now.toISOString().slice(0, 16)
}

export function ControlPanel({ busy, onSubmit }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [speed, setSpeed] = useState(22)
  const [start, setStart] = useState(nowForInput)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function accept(dropped: File | null | undefined) {
    if (dropped && dropped.name.toLowerCase().endsWith('.gpx')) {
      setFile(dropped)
    }
  }

  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault()
        if (file) onSubmit(file, speed, start)
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
              {(file.size / 1024).toFixed(0)} kB · andere Datei wählen
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
            <p className="text-sm font-medium">GPX-Datei hierher ziehen</p>
            <p className="mt-0.5 text-xs opacity-50">oder klicken zum Auswählen</p>
          </>
        )}
      </div>

      <Field label="Abfahrt">
        <input
          type="datetime-local"
          required
          value={start}
          className="input w-full"
          onChange={(event) => setStart(event.target.value)}
        />
      </Field>

      <Field
        label="Schnitt"
        hint={
          <span className="tabular-nums">
            {speed.toFixed(1)} <span className="opacity-50">km/h</span>
          </span>
        }
      >
        <input
          type="range"
          min={10}
          max={45}
          step={0.5}
          value={speed}
          className="range range-primary range-xs"
          onChange={(event) => setSpeed(Number(event.target.value))}
        />
        <div className="mt-1 flex justify-between px-0.5 text-[10px] opacity-35">
          <span>10</span>
          <span>45</span>
        </div>
      </Field>

      <button type="submit" className="btn btn-primary w-full" disabled={!file || busy}>
        {busy && <span className="loading loading-spinner loading-sm" />}
        {busy ? 'Vorhersage wird geholt …' : 'Route auswerten'}
      </button>
    </form>
  )
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-baseline justify-between text-sm font-medium">
        <span className="opacity-75">{label}</span>
        {hint}
      </span>
      {children}
    </label>
  )
}
