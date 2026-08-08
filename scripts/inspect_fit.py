"""Report what a Garmin FIT file actually contains.

Which fields a device writes varies by model and by which sensors were paired,
so this dumps the message types, the per-field coverage of the record stream,
and whether the fields the calibration work depends on are present.

Usage:
    uv run --extra analysis python scripts/inspect_fit.py data/
    uv run --extra analysis python scripts/inspect_fit.py data/ride.fit
"""

import sys
from collections import Counter
from pathlib import Path

from garmin_fit_sdk import Decoder, Stream

REQUIRED_FIELDS = [
    (("timestamp",), "arrival time, for the weather join"),
    (("position_lat",), "latitude"),
    (("position_long",), "longitude"),
]

WANTED_FIELDS = [
    (("power",), "measured power, lets air speed be solved for directly"),
    (("enhanced_speed", "speed"), "ground speed"),
    (("enhanced_altitude", "altitude"), "elevation, for gradient and air density"),
    (("distance",), "cumulative distance"),
    (("cadence",), "detects coasting, where the power model does not apply"),
    (("temperature",), "air density"),
]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2

    target = Path(argv[1])
    if target.is_dir():
        paths = sorted(target.rglob("*.fit")) + sorted(target.rglob("*.FIT"))
    else:
        paths = [target]

    if not paths:
        print(f"No .fit files found in {target}")
        return 1

    print(f"Found {len(paths)} FIT file(s)\n")
    for path in paths:
        inspect_file(path)
    return 0


def inspect_file(path: Path) -> None:
    """Print a summary of one FIT file.

    Args:
        path: Path to the .fit file.
    """
    print("=" * 72)
    print(path)
    print("=" * 72)

    try:
        stream = Stream.from_file(str(path))
        messages, errors = Decoder(stream).read()
    except Exception as exc:
        print(f"  could not decode: {exc}\n")
        return

    if errors:
        print(f"  {len(errors)} decode error(s), first: {errors[0]}")

    print("\n  Message types:")
    for name, entries in sorted(messages.items(), key=lambda kv: -len(kv[1])):
        print(f"    {name:<28} {len(entries):>7}")

    _print_session(messages.get("session_mesgs", []))
    _print_records(messages.get("record_mesgs", []))
    print()


def _print_session(sessions: list[dict]) -> None:
    """Print sport and totals from the session messages.

    Args:
        sessions: Decoded session_mesgs entries.
    """
    if not sessions:
        print("\n  No session message.")
        return

    session = sessions[0]
    distance_m = session.get("total_distance") or 0.0
    elapsed_s = session.get("total_elapsed_time") or 0.0

    print("\n  Session:")
    print(f"    sport             {session.get('sport')} / {session.get('sub_sport')}")
    print(f"    start             {session.get('start_time')}")
    print(f"    distance          {distance_m / 1000:.1f} km")
    print(f"    elapsed           {elapsed_s / 60:.0f} min")
    print(f"    ascent            {session.get('total_ascent')} m")
    print(f"    avg power         {session.get('avg_power')} W")
    print(f"    avg speed         {_to_kmh(session.get('avg_speed'))}")


def _print_records(records: list[dict]) -> None:
    """Print per-field coverage of the record stream.

    Args:
        records: Decoded record_mesgs entries.
    """
    if not records:
        print("\n  No record messages — nothing to calibrate from.")
        return

    counts = Counter()
    for record in records:
        for field, value in record.items():
            if value is not None:
                counts[field] += 1

    total = len(records)
    print(f"\n  Records: {total} (~{total / 60:.0f} min at 1 Hz)")

    print("\n  Required:")
    for alternatives, why in REQUIRED_FIELDS:
        _print_coverage(alternatives, counts, total, why)

    print("\n  Wanted:")
    for alternatives, why in WANTED_FIELDS:
        _print_coverage(alternatives, counts, total, why)

    known = {f for alternatives, _ in REQUIRED_FIELDS + WANTED_FIELDS for f in alternatives}
    extra = sorted(set(counts) - known)
    if extra:
        print("\n  Also present:")
        for field in extra:
            print(f"    {field:<26} {counts[field] / total:>6.1%}")

    _print_sampling(records)


def _print_coverage(alternatives: tuple[str, ...], counts: Counter, total: int, why: str) -> None:
    """Print coverage for a field, or for the best of several interchangeable ones.

    Args:
        alternatives: Field names in order of preference.
        counts: Number of records carrying a value, per field.
        total: Total number of records.
        why: What the field is needed for.
    """
    found = max(alternatives, key=lambda field: counts[field])
    count = counts[found]
    label = found if count else " / ".join(alternatives)

    print(f"    [{'ok  ' if count else 'MISS'}] {label:<26} {count / total:>6.1%}  {why}")


def _print_sampling(records: list[dict]) -> None:
    """Print the recording interval, which reveals smart recording.

    Args:
        records: Decoded record_mesgs entries.
    """
    stamps = [r["timestamp"] for r in records if r.get("timestamp") is not None]
    if len(stamps) < 2:
        return

    gaps = [
        (b - a).total_seconds()
        for a, b in zip(stamps, stamps[1:])
        if (b - a).total_seconds() > 0
    ]
    if not gaps:
        return

    gaps.sort()
    median = gaps[len(gaps) // 2]
    print(
        f"\n  Sampling: median {median:.0f} s, max gap {gaps[-1]:.0f} s"
        f"{'  (smart recording — uneven, needs resampling)' if median > 1.5 else ''}"
    )


def _to_kmh(speed_m_s: float | None) -> str:
    """Format a speed in m/s as km/h.

    Args:
        speed_m_s: Speed in m/s, or None.

    Returns:
        Formatted speed, or "n/a".
    """
    return f"{speed_m_s * 3.6:.1f} km/h" if speed_m_s else "n/a"


if __name__ == "__main__":
    sys.exit(main(sys.argv))
