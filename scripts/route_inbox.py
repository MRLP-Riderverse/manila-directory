#!/usr/bin/env python3
"""Route raw Manila directory drafts into their declared directory group.

The top-level inbox is intentionally permissive. Routing is conservative:
explicit ``Group: edm`` wins; otherwise a draft needs unmistakable EDM signals.
Everything else is parked in ``inbox/needs-review`` for a human decision.
"""

from __future__ import annotations

import argparse
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

EDM_SIGNALS = {
    "edm", "electronic dance music", "house", "techno", "trance", "dubstep",
    "drum and bass", "drum & bass", "dnb", "garage", "hardstyle", "breakbeat",
    "electro", "future bass", "dance music", "dj", "disc jockey",
}


@dataclass(frozen=True)
class RouteResult:
    source: Path
    destination: Path
    group: str | None


def _metadata(text: str) -> tuple[str, str, str]:
    group = ""
    category = ""
    tags = ""
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            continue
        key = key.strip().casefold()
        value = value.strip()
        if key in {"group", "directory", "directory group"}:
            group = value.casefold()
        elif key == "category":
            category = value.casefold()
        elif key == "tags":
            tags = value.casefold()
    return group, category, tags


def classify(text: str) -> str | None:
    group, category, tags = _metadata(text)
    if group:
        return "edm" if group in {"edm", "manila-edm", "manila edm"} else None

    signals = {signal for signal in EDM_SIGNALS if re.search(rf"(?<!\w){re.escape(signal)}(?!\w)", tags)}
    if category in {"dj", "musician", "artist", "producer"} and signals:
        return "edm"
    return "edm" if len(signals) >= 2 else None


def route_file(source: Path, root: Path) -> RouteResult | None:
    if source.suffix.casefold() != ".md" or source.name.startswith("_"):
        return None
    group = classify(source.read_text(encoding="utf-8"))
    if group:
        destination = root / group / "inbox" / source.name
    else:
        destination = root / "inbox" / "needs-review" / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing draft: {destination}")
    shutil.move(str(source), str(destination))
    return RouteResult(source=source, destination=destination, group=group)


def route_inbox(root: Path) -> list[RouteResult]:
    inbox = root / "inbox"
    if not inbox.exists():
        return []
    return [result for source in sorted(inbox.glob("*.md")) if (result := route_file(source, root))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1].parent)
    args = parser.parse_args()
    results = route_inbox(args.root)
    for result in results:
        label = result.group or "needs-review"
        print(f"{label}: {result.source.name} -> {result.destination}")
    print(f"Routed: {len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
