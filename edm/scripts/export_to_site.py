#!/usr/bin/env python3
"""Export Manila EDM directory data into static website payloads.

Canonical source of truth:
- ``entries/*/entry.md`` + ``meta.json`` for durable identities
- ``inbox/*.md`` for public draft previews
- ``events/*/event.md`` + ``meta.json`` for time-based activity
- ``locations/*/location.md`` + ``meta.json`` for reusable physical/community places
- ``regions/*/region.md`` + ``meta.json`` for browse/fork geography

Outputs in the sibling ``manila_directory_edm`` site repo:
- ``assets/directory-data.json``
- ``assets/events-data.json``
- ``assets/locations-data.json``
- ``assets/regions-data.json``
- ``assets/search-index.json``
- ``assets/site-meta.json``
- ``assets/calendar/*.ics``

The script is intentionally local/offline. It does not commit, push, or deploy.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_DIRECTORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITE_ROOT = DEFAULT_DIRECTORY_ROOT.parents[1] / "manila" / "edm"
CONTACT_KEYS = {"address", "hours", "phone", "email", "website"}
SCHEMA_VERSION = 1
LANG_KEYS = ("en",)


def clean_text(value: str) -> str:
    """Normalize whitespace while preserving human-authored wording."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def slugify(value: str) -> str:
    """Create a safe fallback slug for records that do not declare an id."""
    value = clean_text(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "untitled"


def localized(value: str | dict | None, fallback: str = "") -> dict[str, str]:
    """Return the standard Manila EDM language object: English-first.

    Drafts and old records may still provide plain strings. We normalize those to
    ``en`` while keeping future language fields can be added by the local steward later.
    """
    if isinstance(value, dict):
        return {key: clean_text(value.get(key, "")) for key in LANG_KEYS}
    return {"en": clean_text(value or fallback)}


def display_text(value: str | dict | None, fallback: str = "") -> str:
    """Pick the public display string for English-first static rendering."""
    if isinstance(value, dict):
        for key in LANG_KEYS:
            text = clean_text(value.get(key, ""))
            if text:
                return text
        return fallback
    return clean_text(value or fallback)


def parse_tags(value: str | list[str] | None) -> list[str]:
    if not value:
        return []
    raw = value if isinstance(value, list) else re.split(r"[|,]", value)
    tags: list[str] = []
    seen: set[str] = set()
    for tag in raw:
        cleaned = clean_text(str(tag)).strip("# ")
        key = cleaned.casefold()
        if cleaned and key not in seen:
            tags.append(cleaned)
            seen.add(key)
    return tags


def public_area(area: str, meta: dict | None = None) -> str:
    if meta:
        location = meta.get("location") or {}
        explicit = clean_text(location.get("public_area", ""))
        if explicit:
            return explicit
        municipality = clean_text(location.get("municipality", ""))
        if municipality:
            area = municipality
    area = clean_text(area)
    return area or "Unsorted"


def timestamp_for(path: Path) -> tuple[str, int]:
    stat = path.stat()
    modified_ts = int(stat.st_mtime)
    modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    return modified_at, modified_ts


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(DEFAULT_DIRECTORY_ROOT))
    except ValueError:
        for marker in ("inbox", "entries", "events", "locations", "regions"):
            if marker in path.parts:
                idx = path.parts.index(marker)
                return str(Path(*path.parts[idx:]))
        return str(path)


def markdown_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"preamble": []}
    current = "preamble"
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            current = stripped[3:].strip().casefold()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def bullet_values(lines: list[str]) -> list[str]:
    return [line.strip()[2:].strip() for line in lines if line.strip().startswith("- ") and line.strip()[2:].strip()]


def parse_contact_lines(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    contact = {key: "" for key in CONTACT_KEYS}
    public_data: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        value = stripped[2:].strip()
        if not value or value.startswith("["):
            continue
        public_data.append(value)
        if ":" not in value:
            continue
        key, val = value.split(":", 1)
        key_norm = key.strip().lower()
        if key_norm in contact:
            contact[key_norm] = clean_text(val)
    return contact, public_data


def first_heading(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return re.sub(r"^#\s*Draft:\s*", "", stripped[2:].strip()).strip()
    return fallback


def source_type(path: Path, draft: bool, sources: list[str]) -> str:
    if draft:
        return "inbox"
    if any(src.casefold() == "in person" for src in sources):
        return "in-person"
    if sources:
        return "public-source"
    return "entry"


def build_item(
    *,
    path: Path,
    title: str,
    status: str,
    category: str = "",
    area: str = "",
    tags: list[str] | None = None,
    description: str = "",
    notes: str = "",
    note_points: list[str] | None = None,
    contact: dict[str, str] | None = None,
    public_data: list[str] | None = None,
    related_places: list[str] | None = None,
    sources: list[str] | None = None,
    meta: dict | None = None,
) -> dict:
    """Build one public directory card item with backwards-compatible fields."""
    draft = status == "draft"
    contact = {**{key: "" for key in CONTACT_KEYS}, **(contact or {})}
    tags = tags or []
    note_points = note_points or []
    related_places = related_places or []
    sources = sources or []
    public_data = public_data or []
    modified_at, modified_ts = timestamp_for(path)
    summary = clean_text(" ".join(part for part in [description, notes] if part))[:220]
    area_value = area or clean_text((meta or {}).get("location", {}).get("municipality", ""))
    public_area_value = public_area(area_value, meta)
    name = clean_text((meta or {}).get("name", "")) or title

    raw_location_value = (meta or {}).get("location")
    raw_location: dict = raw_location_value if isinstance(raw_location_value, dict) else {}
    raw_thumbnail_value = (meta or {}).get("thumbnail")
    raw_thumbnail: dict = raw_thumbnail_value if isinstance(raw_thumbnail_value, dict) else {}

    return {
        "title": name,
        "title_localized": localized((meta or {}).get("title"), name),
        "name": name,
        "sort_name": clean_text((meta or {}).get("sort_name", "")) or name,
        "brand_name": clean_text((meta or {}).get("brand_name", "")),
        "branch_name": clean_text((meta or {}).get("branch_name", "")),
        "aliases": (meta or {}).get("aliases", []) if isinstance((meta or {}).get("aliases", []), list) else [],
        "slug": clean_text((meta or {}).get("slug", "")) or (path.stem if path.name != "entry.md" else path.parent.name),
        "location_id": clean_text((meta or {}).get("location_id", "") or raw_location.get("location_id", "")),
        "region_id": clean_text((meta or {}).get("region_id", "") or raw_location.get("region_id", "") or "metro-manila"),
        "street_id": clean_text((meta or {}).get("street_id", "") or raw_location.get("street_id", "")),
        "status": status,
        "draft": draft,
        "badge": "DRAFT" if draft else "",
        "category": category,
        "area": area_value,
        "public_area": public_area_value,
        "description": description,
        "description_localized": localized((meta or {}).get("summary") or (meta or {}).get("short_description"), description),
        "notes": notes,
        "note_points": note_points,
        "summary": summary,
        "tags": tags,
        "contact": contact,
        "address": contact["address"],
        "hours": contact["hours"],
        "phone": contact["phone"],
        "email": contact["email"],
        "website": contact["website"],
        "thumbnail_src": clean_text(raw_thumbnail.get("src", "")),
        "thumbnail_alt": clean_text(raw_thumbnail.get("alt", "")),
        "public_data": public_data,
        "related_places": related_places,
        "sources": sources,
        "source_type": source_type(path, draft, sources),
        "path": display_path(path),
        "source_modified_at": modified_at,
        "source_modified_ts": modified_ts,
    }


def parse_draft(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title_line = lines[0].strip() if lines else "# Draft: Untitled"
    title = re.sub(r"^#\s*Draft:\s*", "", title_line).strip()
    category = ""
    area = ""
    tags: list[str] = []
    body: list[str] = []

    for line in lines[1:]:
        if line.startswith("Category:"):
            category = clean_text(line.split(":", 1)[1])
            continue
        if line.startswith("Area:"):
            area = clean_text(line.split(":", 1)[1])
            continue
        if line.startswith("Tags:"):
            tags = parse_tags(line.split(":", 1)[1])
            continue
        body.append(line)

    sections = markdown_sections(body)
    description = clean_text(" ".join(sections.get("description", [])))
    note_lines = sections.get("notes", [])
    notes = clean_text(" ".join(note_lines))
    note_points = bullet_values(note_lines)
    contact_lines = sections.get("public data to carry forward", []) or sections.get("public data", []) or sections.get("details", []) or sections.get("contact", [])
    contact, public_data = parse_contact_lines(contact_lines)
    sources = bullet_values(sections.get("public source", []) or sections.get("details and sources", []) or sections.get("sources", []))
    related_places = bullet_values(sections.get("related places", []))

    return build_item(path=path, title=title, status="draft", category=category, area=area, tags=tags, description=description, notes=notes, note_points=note_points, contact=contact, public_data=public_data, related_places=related_places, sources=sources)


def parse_entry(entry_md: Path) -> dict:
    entry_dir = entry_md.parent
    meta_path = entry_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    text = entry_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = first_heading(text, entry_dir.name.replace("-", " ").title())
    sections = markdown_sections(lines[1:] if lines else [])

    description = display_text(meta.get("summary") or meta.get("short_description"), clean_text(" ".join(line for line in sections.get("preamble", []) if line.strip())))
    note_lines = sections.get("public notes", []) or sections.get("notes", [])
    notes = clean_text(" ".join(note_lines))
    note_points = bullet_values(note_lines)

    raw_contact = meta.get("contact")
    meta_contact: dict = raw_contact if isinstance(raw_contact, dict) else {}
    contact_lines = sections.get("contact", [])
    contact, public_data = parse_contact_lines(contact_lines)
    contact.update({key: clean_text(meta_contact.get(key, contact[key])) for key in CONTACT_KEYS})

    sources = bullet_values(sections.get("sources", []) or sections.get("public source", []))
    related_lines = bullet_values(sections.get("related places", []))
    related_meta = meta.get("related", []) if isinstance(meta.get("related", []), list) else []
    related_places = related_lines + [clean_text(item.get("slug") or item.get("name") or "") for item in related_meta if isinstance(item, dict)]
    raw_location = meta.get("location")
    location: dict = raw_location if isinstance(raw_location, dict) else {}

    return build_item(path=entry_md, title=title, status=clean_text(meta.get("status", "published")) or "published", category=clean_text(meta.get("category", "")), area=clean_text(location.get("public_area") or location.get("municipality") or ""), tags=parse_tags(meta.get("tags")), description=description, notes=notes, note_points=note_points, contact=contact, public_data=public_data, related_places=[item for item in related_places if item], sources=sources, meta=meta)


def collect_drafts(directory_root: Path) -> list[Path]:
    inbox = directory_root / "inbox"
    if not inbox.exists():
        return []
    return [path for path in sorted(inbox.glob("*.md")) if not path.name.lower().startswith("_") and "template" not in path.name.lower()]


def collect_entries(directory_root: Path) -> list[Path]:
    entries = directory_root / "entries"
    if not entries.exists():
        return []
    return [path for path in sorted(entries.glob("*/entry.md")) if not any(part.startswith("_") for part in path.relative_to(entries).parts)]


def collect_record_paths(directory_root: Path, folder: str, filename: str) -> list[Path]:
    root = directory_root / folder
    if not root.exists():
        return []
    return [path for path in sorted(root.glob(f"*/{filename}")) if not any(part.startswith("_") for part in path.relative_to(root).parts)]


def parse_location(path: Path) -> dict:
    """Parse a reusable place/corridor/community location record."""
    meta_path = path.parent / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    text = path.read_text(encoding="utf-8")
    title = first_heading(text, path.parent.name.replace("-", " ").title())
    modified_at, modified_ts = timestamp_for(path)
    contact_value = meta.get("contact")
    contact: dict = contact_value if isinstance(contact_value, dict) else {}
    return {
        "id": clean_text(meta.get("id", "")) or path.parent.name,
        "status": clean_text(meta.get("status", "published")) or "published",
        "kind": clean_text(meta.get("kind", "place")) or "place",
        "title": localized(meta.get("title"), title),
        "name": display_text(meta.get("title"), title),
        "summary": localized(meta.get("summary")),
        "region_id": clean_text(meta.get("region_id", "metro-manila")),
        "street_id": clean_text(meta.get("street_id", "")),
        "address": clean_text(meta.get("address", "") or contact.get("address", "")),
        "municipality": clean_text(meta.get("municipality", "Manila")),
        "public_area": clean_text(meta.get("public_area", "Metro Manila")),
        "entry_ids": meta.get("entry_ids", []) if isinstance(meta.get("entry_ids", []), list) else [],
        "nearby_location_ids": meta.get("nearby_location_ids", []) if isinstance(meta.get("nearby_location_ids", []), list) else [],
        "tags": parse_tags(meta.get("tags")),
        "path": display_path(path),
        "source_modified_at": modified_at,
        "source_modified_ts": modified_ts,
    }


def event_is_active(event: dict, now: datetime | None = None) -> bool:
    """Classify an event dynamically without mutating source files.

    The source may say ``status: active``. Once ``expires_at``/``ends_at`` passes,
    the exported payload reports ``computed_status: archived`` so stale events get
    out of the way on the website. A future cron/manual command can later patch the
    source file if we decide we want disk state to follow the computed state.
    """
    if event.get("status") in {"archived", "cancelled"}:
        return False
    cutoff = event.get("expires_at") or event.get("ends_at") or event.get("starts_at")
    if not cutoff:
        return event.get("status") in {"active", "published", "draft", "placeholder"}
    try:
        if cutoff.endswith("Z"):
            cutoff_dt = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
        else:
            cutoff_dt = datetime.fromisoformat(cutoff)
        now = now or datetime.now(tz=cutoff_dt.tzinfo or timezone.utc)
        return cutoff_dt >= now
    except ValueError:
        return True


def parse_event(path: Path) -> dict:
    meta_path = path.parent / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    text = path.read_text(encoding="utf-8")
    title = first_heading(text, path.parent.name.replace("-", " ").title())
    modified_at, modified_ts = timestamp_for(path)
    status = clean_text(meta.get("status", "draft")) or "draft"
    event = {
        "id": clean_text(meta.get("id", "")) or path.parent.name,
        "status": status,
        "computed_status": status,
        "kind": "event",
        "title": localized(meta.get("title"), title),
        "name": display_text(meta.get("title"), title),
        "summary": localized(meta.get("summary")),
        "starts_at": clean_text(meta.get("starts_at", "")),
        "ends_at": clean_text(meta.get("ends_at", "")),
        "expires_at": clean_text(meta.get("expires_at", "") or meta.get("ends_at", "")),
        "timezone": clean_text(meta.get("timezone", "America/Moncton")),
        "region_id": clean_text(meta.get("region_id", "metro-manila")),
        "location_id": clean_text(meta.get("location_id", "")),
        "host_entry_ids": meta.get("host_entry_ids", []) if isinstance(meta.get("host_entry_ids", []), list) else [],
        "performer_entry_ids": meta.get("performer_entry_ids", []) if isinstance(meta.get("performer_entry_ids", []), list) else [],
        "sponsor_entry_ids": meta.get("sponsor_entry_ids", []) if isinstance(meta.get("sponsor_entry_ids", []), list) else [],
        "related_offer_ids": meta.get("related_offer_ids", []) if isinstance(meta.get("related_offer_ids", []), list) else [],
        "tags": parse_tags(meta.get("tags")),
        "wayfinding": localized(meta.get("wayfinding")),
        "bring": localized(meta.get("bring")),
        "calendar": meta.get("calendar", {"ics_enabled": True}) if isinstance(meta.get("calendar", {}), dict) else {"ics_enabled": True},
        "source": meta.get("source", {}) if isinstance(meta.get("source", {}), dict) else {},
        "path": display_path(path),
        "source_modified_at": modified_at,
        "source_modified_ts": modified_ts,
    }
    event["computed_status"] = "active" if event_is_active(event) else "archived"
    return event


def parse_region(path: Path) -> dict:
    meta_path = path.parent / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    text = path.read_text(encoding="utf-8")
    title = first_heading(text, path.parent.name.replace("-", " ").title())
    modified_at, modified_ts = timestamp_for(path)
    return {
        "id": clean_text(meta.get("id", "")) or path.parent.name,
        "status": clean_text(meta.get("status", "published")) or "published",
        "title": localized(meta.get("title"), title),
        "name": display_text(meta.get("title"), title),
        "summary": localized(meta.get("summary")),
        "tags": parse_tags(meta.get("tags")),
        "path": display_path(path),
        "source_modified_at": modified_at,
        "source_modified_ts": modified_ts,
    }


def git_value(directory_root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=directory_root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def latest_source_timestamp(paths: Iterable[Path]) -> tuple[str, int]:
    latest = 0
    for path in paths:
        if path.exists():
            latest = max(latest, int(path.stat().st_mtime))
    if not latest:
        latest = int(datetime.now(tz=timezone.utc).timestamp())
    return datetime.fromtimestamp(latest, tz=timezone.utc).isoformat().replace("+00:00", "Z"), latest


def build_site_meta(directory_root: Path, all_source_paths: list[Path], snapshot_refresh_count: int | None = None) -> dict:
    latest_at, latest_ts = latest_source_timestamp(all_source_paths)
    generated_at = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
    if snapshot_refresh_count is None:
        # Static, privacy-safe joke counter: count local export executions by incrementing
        # the previous site-meta value when available. This is not visitor tracking.
        previous = DEFAULT_SITE_ROOT / "assets" / "site-meta.json"
        try:
            snapshot_refresh_count = int(json.loads(previous.read_text(encoding="utf-8")).get("snapshot_refresh_count", 0)) + 1
        except Exception:
            snapshot_refresh_count = 1
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "latest_source_modified_at": latest_at,
        "latest_source_modified_ts": latest_ts,
        "git_commit": git_value(directory_root, "rev-parse", "--short", "HEAD"),
        "git_commit_time": git_value(directory_root, "log", "-1", "--format=%cI"),
        "snapshot_refresh_count": snapshot_refresh_count,
        "activity_led": activity_led(latest_ts),
    }


def activity_led(latest_ts: int) -> dict:
    age_days = (datetime.now(tz=timezone.utc).timestamp() - latest_ts) / 86400
    if age_days <= 14:
        color, label = "green", "active"
    elif age_days <= 30:
        color, label = "yellow", "warming"
    else:
        color, label = "red", "quiet"
    return {"color": color, "label": label, "age_days": round(age_days, 1)}


def build_directory_payload(directory_root: Path) -> dict:
    items = [parse_entry(path) for path in collect_entries(directory_root)]
    items.extend(parse_draft(path) for path in collect_drafts(directory_root))
    items.sort(key=lambda item: (0 if item["status"] == "published" else 1, item["title"].lower()))
    return {"schema_version": SCHEMA_VERSION, "generated_from": str(directory_root), "entry_count": len(items), "draft_count": sum(1 for item in items if item["draft"]), "published_count": sum(1 for item in items if item["status"] == "published"), "items": items}


def build_payload(directory_root: Path) -> dict:
    """Backward-compatible public API used by existing tests."""
    return build_directory_payload(directory_root)


def build_events_payload(directory_root: Path) -> dict:
    events = [parse_event(path) for path in collect_record_paths(directory_root, "events", "event.md")]
    events.sort(key=lambda event: (event.get("starts_at") or "9999", event.get("name", "")))
    return {"schema_version": SCHEMA_VERSION, "generated_from": str(directory_root), "event_count": len(events), "active_count": sum(1 for event in events if event["computed_status"] == "active"), "archived_count": sum(1 for event in events if event["computed_status"] == "archived"), "items": events}


def build_locations_payload(directory_root: Path) -> dict:
    locations = [parse_location(path) for path in collect_record_paths(directory_root, "locations", "location.md")]
    locations.sort(key=lambda location: location.get("name", ""))
    return {"schema_version": SCHEMA_VERSION, "generated_from": str(directory_root), "location_count": len(locations), "items": locations}


def build_regions_payload(directory_root: Path) -> dict:
    regions = [parse_region(path) for path in collect_record_paths(directory_root, "regions", "region.md")]
    regions.sort(key=lambda region: region.get("name", ""))
    return {"schema_version": SCHEMA_VERSION, "generated_from": str(directory_root), "region_count": len(regions), "items": regions}


def upcoming_event_count_for_entry(entry_id: str, events: list[dict], within_days: int = 7) -> int:
    now = datetime.now(timezone.utc)
    horizon = now.timestamp() + within_days * 86400
    count = 0
    for event in events:
        if entry_id not in event.get("host_entry_ids", []) and entry_id not in event.get("performer_entry_ids", []) and entry_id not in event.get("sponsor_entry_ids", []):
            continue
        try:
            starts = event.get("starts_at", "")
            dt = datetime.fromisoformat(starts.replace("Z", "+00:00"))
            if now.timestamp() <= dt.timestamp() <= horizon:
                count += 1
        except ValueError:
            if event.get("computed_status") == "active":
                count += 1
    return count


def build_search_index(directory_payload: dict, events_payload: dict, locations_payload: dict) -> dict:
    """Build one lightweight static search index across entries, events, locations."""
    events = events_payload.get("items", [])
    items: list[dict] = []
    for entry in directory_payload.get("items", []):
        if entry.get("draft"):
            continue
        event_count = upcoming_event_count_for_entry(entry.get("slug", ""), events)
        badges = [entry.get("category", "")]
        if event_count:
            badges.append(f"{event_count} event{'s' if event_count != 1 else ''} next 7 days")
        items.append({
            "type": "entry",
            "id": entry.get("slug", ""),
            "title": entry.get("title", ""),
            "subtitle": f"{entry.get('category', 'entry')} · {entry.get('public_area', '')}".strip(" ·"),
            "badges": [badge for badge in badges if badge],
            "url": f"directory.html#entry-{entry.get('slug', '')}",
            "terms": [entry.get("title", ""), entry.get("category", ""), entry.get("public_area", ""), entry.get("description", ""), *(entry.get("tags") or []), *(entry.get("aliases") or [])],
        })
    for event in events:
        items.append({
            "type": "event",
            "id": event.get("id", ""),
            "title": event.get("name", ""),
            "subtitle": f"{event.get('computed_status', event.get('status', 'event'))} · {event.get('starts_at') or 'Date TBD'}",
            "badges": ["event", event.get("computed_status", ""), *(event.get("tags") or [])[:2]],
            "url": f"events.html#event-{event.get('id', '')}",
            "terms": [event.get("name", ""), display_text(event.get("summary")), event.get("starts_at", ""), *(event.get("tags") or []), *(event.get("host_entry_ids") or [])],
        })
    for location in locations_payload.get("items", []):
        items.append({
            "type": "location",
            "id": location.get("id", ""),
            "title": location.get("name", ""),
            "subtitle": f"{location.get('kind', 'location')} · {location.get('public_area', '')}".strip(" ·"),
            "badges": ["location", location.get("kind", "")],
            "url": f"events.html#location-{location.get('id', '')}",
            "terms": [location.get("name", ""), display_text(location.get("summary")), location.get("street_id", ""), *(location.get("tags") or [])],
        })
    return {"schema_version": SCHEMA_VERSION, "item_count": len(items), "items": items}


def ics_escape(value: str) -> str:
    return clean_text(value).replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def ics_datetime(value: str) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    except ValueError:
        return ""


def write_calendar_files(site_root: Path, events: list[dict], locations: list[dict]) -> None:
    """Generate static .ics files so mobile users can add events to native calendars."""
    by_location = {location["id"]: location for location in locations}
    out_dir = site_root / "assets" / "calendar"
    out_dir.mkdir(parents=True, exist_ok=True)
    for event in events:
        if not event.get("calendar", {}).get("ics_enabled", True):
            continue
        start = ics_datetime(event.get("starts_at", ""))
        end = ics_datetime(event.get("ends_at", "")) or start
        if not start:
            continue
        location = by_location.get(event.get("location_id", ""), {})
        location_text = location.get("address") or location.get("name", "")
        uid = f"{event['id']}@acadie.sol"
        dtstamp = ics_datetime(event.get("source_modified_at", "")) or start
        body = "\n".join([
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Manila EDM//Events V1//EN",
            "BEGIN:VEVENT",
            f"UID:{ics_escape(uid)}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART:{start}",
            f"DTEND:{end}",
            f"SUMMARY:{ics_escape(event.get('name', 'Manila EDM event'))}",
            f"DESCRIPTION:{ics_escape(display_text(event.get('summary')))}",
            f"LOCATION:{ics_escape(location_text)}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ])
        out_path = out_dir / f"{event['id']}.ics"
        if out_path.exists() and out_path.read_text(encoding="utf-8") == body:
            continue
        out_path.write_text(body, encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def export_all(directory_root: Path, site_root: Path) -> dict[str, dict]:
    directory_payload = build_directory_payload(directory_root)
    events_payload = build_events_payload(directory_root)
    locations_payload = build_locations_payload(directory_root)
    regions_payload = build_regions_payload(directory_root)
    search_payload = build_search_index(directory_payload, events_payload, locations_payload)
    all_sources = collect_entries(directory_root) + collect_drafts(directory_root) + collect_record_paths(directory_root, "events", "event.md") + collect_record_paths(directory_root, "locations", "location.md") + collect_record_paths(directory_root, "regions", "region.md")
    site_meta = build_site_meta(directory_root, all_sources)

    write_json(site_root / "assets" / "directory-data.json", directory_payload)
    write_json(site_root / "assets" / "events-data.json", events_payload)
    write_json(site_root / "assets" / "locations-data.json", locations_payload)
    write_json(site_root / "assets" / "regions-data.json", regions_payload)
    write_json(site_root / "assets" / "search-index.json", search_payload)
    write_json(site_root / "assets" / "site-meta.json", site_meta)
    write_calendar_files(site_root, events_payload.get("items", []), locations_payload.get("items", []))
    return {"directory": directory_payload, "events": events_payload, "locations": locations_payload, "regions": regions_payload, "search": search_payload, "site_meta": site_meta}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Manila EDM public payloads into the static site repo.")
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY_ROOT, help="Directory repo root (default: this repo).")
    parser.add_argument("--site", type=Path, default=DEFAULT_SITE_ROOT, help="Website repo root to write into (default: sibling 'manila_directory_edm').")
    parser.add_argument("--output", type=Path, default=Path("assets/directory-data.json"), help="Legacy single-payload output path inside the website repo.")
    parser.add_argument("--stdout", action="store_true", help="Print legacy directory JSON to stdout instead of writing.")
    parser.add_argument("--all", action="store_true", help="Write all V1 public payloads. This is now the recommended export mode.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    directory_root = args.directory.resolve()
    site_root = args.site.resolve()
    if not directory_root.exists():
        raise SystemExit(f"Directory repo not found: {directory_root}")
    if not site_root.exists() and not args.stdout:
        raise SystemExit(f"Website repo not found: {site_root}")

    if args.stdout:
        print(json.dumps(build_directory_payload(directory_root), indent=2, ensure_ascii=False))
        return 0

    if args.all:
        payloads = export_all(directory_root, site_root)
        print(f"Wrote V1 public payloads into {site_root / 'assets'}")
        print(f"Entries: {payloads['directory']['entry_count']}  Events: {payloads['events']['event_count']}  Locations: {payloads['locations']['location_count']}  Regions: {payloads['regions']['region_count']}")
        return 0

    # Legacy behavior retained for existing muscle memory and tests.
    output_path = args.output if args.output.is_absolute() else site_root / args.output
    payload = build_directory_payload(directory_root)
    write_json(output_path, payload)
    print(f"Wrote {output_path}")
    print(f"Entries: {payload['entry_count']}  Drafts: {payload['draft_count']}  Published: {payload['published_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
