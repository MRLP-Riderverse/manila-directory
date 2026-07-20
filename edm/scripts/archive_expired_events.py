#!/usr/bin/env python3
"""Archive expired Acadie.sol events by patching their source meta.json files.

This script is the safe automation hook for the future cron/trigger layer:
- reads ``events/*/meta.json``
- compares ``expires_at`` first, then ``ends_at``
- changes ``status`` from active/published to archived only when expired
- defaults to dry-run, so humans/dev workers can inspect changes first

The static exporter already computes archived state dynamically for rendering. This
script is for when we want the durable data repo to follow that computed state.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ARCHIVABLE_STATUSES = {"active", "published"}


def parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def archive_expired_events(events_root: Path, *, dry_run: bool = True, include_placeholders: bool = False) -> list[Path]:
    now = datetime.now(timezone.utc)
    statuses = set(ARCHIVABLE_STATUSES)
    if include_placeholders:
        statuses.add("placeholder")
    changed: list[Path] = []

    for meta_path in sorted(events_root.glob("*/meta.json")):
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        status = str(data.get("status", "")).strip()
        if status not in statuses:
            continue
        cutoff = parse_dt(str(data.get("expires_at") or data.get("ends_at") or ""))
        if not cutoff:
            continue
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        if cutoff >= now:
            continue

        data["status"] = "archived"
        data.setdefault("archive", {})["archived_at"] = now.isoformat().replace("+00:00", "Z")
        data["archive"]["archived_by"] = "scripts/archive_expired_events.py"
        changed.append(meta_path)
        if not dry_run:
            meta_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch expired Acadie.sol event meta.json files to archived status.")
    parser.add_argument("--events-root", type=Path, default=Path(__file__).resolve().parents[1] / "events")
    parser.add_argument("--apply", action="store_true", help="Write changes. Without this, only reports what would change.")
    parser.add_argument("--include-placeholders", action="store_true", help="Also archive placeholder events when expired.")
    args = parser.parse_args()

    changed = archive_expired_events(args.events_root, dry_run=not args.apply, include_placeholders=args.include_placeholders)
    mode = "archived" if args.apply else "would archive"
    if changed:
        for path in changed:
            print(f"{mode}: {path}")
    else:
        print("no expired events to archive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
