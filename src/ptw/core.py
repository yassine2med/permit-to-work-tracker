"""Permit-to-work log checks for hot work and confined space permits."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

MAX_HOURS = {"hot work": 8.0, "confined space": 12.0}
CLOSE_GRACE = timedelta(minutes=60)


@dataclass(frozen=True)
class Permit:
    permit_id: str
    kind: str
    location: str
    issued: datetime
    expires: datetime
    closed: datetime | None
    gas_test: bool
    fire_watch: bool


@dataclass(frozen=True)
class Finding:
    permit_id: str
    rule: str
    detail: str


def _bool(value: str) -> bool:
    return value.strip().lower() in {"y", "yes", "true", "1"}


def load_permits(path: str | Path) -> list[Permit]:
    """Read permits from CSV. Raises ValueError on a bad row or missing column."""
    required = {"permit_id", "kind", "location", "issued", "expires", "closed", "gas_test", "fire_watch"}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing columns: {', '.join(sorted(missing))}")
        permits = []
        for line, row in enumerate(reader, start=2):
            try:
                kind = row["kind"].strip().lower()
                if kind not in MAX_HOURS:
                    raise ValueError(f"unknown kind '{row['kind']}'")
                issued = datetime.fromisoformat(row["issued"])
                expires = datetime.fromisoformat(row["expires"])
                closed = datetime.fromisoformat(row["closed"]) if row["closed"].strip() else None
            except ValueError as exc:
                raise ValueError(f"line {line}: {exc}") from exc
            permits.append(Permit(row["permit_id"].strip(), kind, row["location"].strip(), issued, expires,
                                  closed, _bool(row["gas_test"]), _bool(row["fire_watch"])))
    return permits


def check(permits: list[Permit], now: datetime) -> list[Finding]:
    """Return rule violations for the permit list as of `now`."""
    out: list[Finding] = []
    for p in permits:
        hours = (p.expires - p.issued).total_seconds() / 3600
        if hours <= 0:
            out.append(Finding(p.permit_id, "bad-window", "expiry is not after issue time"))
        elif hours > MAX_HOURS[p.kind]:
            out.append(Finding(p.permit_id, "too-long", f"{hours:.1f} h exceeds {MAX_HOURS[p.kind]:.0f} h limit for {p.kind}"))
        if p.kind == "confined space" and not p.gas_test:
            out.append(Finding(p.permit_id, "no-gas-test", "confined space permit has no gas test recorded"))
        if p.kind == "hot work" and not p.fire_watch:
            out.append(Finding(p.permit_id, "no-fire-watch", "hot work permit has no fire watch"))
        if p.closed is None and p.expires < now:
            late = (now - p.expires).total_seconds() / 3600
            out.append(Finding(p.permit_id, "not-closed", f"expired {late:.1f} h ago and still open"))
        if p.closed is not None and p.closed > p.expires + CLOSE_GRACE:
            out.append(Finding(p.permit_id, "closed-late", "closed more than 60 min after expiry"))
    out.extend(_conflicts(permits))
    return sorted(out, key=lambda f: (f.permit_id, f.rule))


def _conflicts(permits: list[Permit]) -> list[Finding]:
    """Hot work and confined space permits must not overlap in one location."""
    found = []
    hot = [p for p in permits if p.kind == "hot work"]
    cs = [p for p in permits if p.kind == "confined space"]
    for a in hot:
        for b in cs:
            if a.location == b.location and a.issued < (b.closed or b.expires) and b.issued < (a.closed or a.expires):
                found.append(Finding(a.permit_id, "conflict", f"overlaps confined space permit {b.permit_id} at {a.location}"))
    return found


def format_report(permits: list[Permit], findings: list[Finding]) -> str:
    """Plain text report."""
    lines = [f"Permits checked: {len(permits)}", f"Findings: {len(findings)}"]
    for f in findings:
        lines.append(f"  {f.permit_id:<8} {f.rule:<14} {f.detail}")
    return "\n".join(lines)
