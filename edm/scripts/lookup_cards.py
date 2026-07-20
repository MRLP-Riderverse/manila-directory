#!/usr/bin/env python3
"""Search Acadie.sol directory drafts and clean entries by business name.

Use cases:
- draft inbox lookups from conversational triggers
- future clean-entry lookups across entries/
- ambiguity surfacing when multiple likely cards exist

By default, prints JSON so Hermes can reason over the result deterministically.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable


@dataclass
class Card:
    title: str
    path: Path
    card_type: str  # draft | entry
    content: str


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def normalize_tokens(value: str) -> list[str]:
    return [part for part in re.split(r"[^a-z0-9]+", value.casefold()) if part]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_first_heading(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def load_draft_cards(root: Path) -> list[Card]:
    cards: list[Card] = []
    for path in sorted((root / "inbox").glob("*.md")):
        content = read_text(path)
        title = ""
        first_line = content.splitlines()[0].strip() if content.splitlines() else ""
        if first_line.startswith("# Draft:"):
            title = first_line.split(":", 1)[1].strip()
        if not title:
            title = path.stem.replace("-", " ").strip()
        cards.append(Card(title=title, path=path.resolve(), card_type="draft", content=content))
    return cards


def load_entry_cards(root: Path) -> list[Card]:
    cards: list[Card] = []
    for entry_dir in sorted((root / "entries").glob("*")):
        if not entry_dir.is_dir():
            continue
        entry_md = entry_dir / "entry.md"
        meta_json = entry_dir / "meta.json"
        content = ""
        title = ""
        if entry_md.exists():
            content = read_text(entry_md)
            title = extract_first_heading(content)
        if meta_json.exists():
            try:
                meta = json.loads(read_text(meta_json))
            except json.JSONDecodeError:
                meta = {}
            title = (meta.get("name") or title or entry_dir.name).strip()
            if not content:
                content = json.dumps(meta, indent=2, ensure_ascii=False)
        if title:
            cards.append(Card(title=title, path=(entry_md if entry_md.exists() else meta_json).resolve(), card_type="entry", content=content))
    return cards


def score_match(query: str, title: str) -> float:
    qn = normalize_text(query)
    tn = normalize_text(title)
    if not qn or not tn:
        return 0.0
    if qn == tn:
        return 1.0

    q_tokens = normalize_tokens(query)
    t_tokens = normalize_tokens(title)
    q_set = set(q_tokens)
    t_set = set(t_tokens)
    token_overlap = len(q_set & t_set) / max(len(q_set), len(t_set), 1)
    ratio = SequenceMatcher(None, qn, tn).ratio()

    substring_score = 0.0
    shorter, longer = sorted((qn, tn), key=len)
    if len(shorter) >= 4 and shorter in longer:
        substring_score = min(0.96, 0.82 + (len(shorter) / max(len(longer), 1)) * 0.14)

    prefix_score = 0.0
    if q_tokens and t_tokens:
        if q_tokens[0] == t_tokens[0]:
            prefix_score = 0.78
        prefix_len = min(len(q_tokens), len(t_tokens))
        if q_tokens[:prefix_len] == t_tokens[:prefix_len]:
            prefix_score = max(prefix_score, 0.88)
        if len(q_tokens) >= 2 and len(q_tokens) <= len(t_tokens) and q_tokens == t_tokens[: len(q_tokens)]:
            prefix_score = max(prefix_score, 0.96)

    token_subset_score = 0.0
    if q_set and t_set and (q_set <= t_set or t_set <= q_set):
        token_subset_score = 0.9

    return max(ratio, token_overlap, substring_score, prefix_score, token_subset_score)


def find_matches(cards: Iterable[Card], query: str) -> list[dict]:
    ranked = []
    for card in cards:
        score = score_match(query, card.title)
        if score >= 0.45:
            ranked.append(
                {
                    "title": card.title,
                    "path": str(card.path),
                    "type": card.card_type,
                    "score": round(score, 4),
                    "content": card.content,
                }
            )
    ranked.sort(key=lambda item: (-item["score"], item["title"].casefold(), item["path"]))
    return ranked


def classify(matches: list[dict]) -> dict:
    if not matches:
        return {"status": "none", "matches": []}

    top = matches[0]
    second = matches[1] if len(matches) > 1 else None
    second_score = second["score"] if second else 0.0

    is_clear = False
    if top["score"] >= 0.99:
        is_clear = True
    elif top["score"] >= 0.94 and (top["score"] - second_score) >= 0.08:
        is_clear = True
    elif top["score"] >= 0.9 and second_score < 0.75:
        is_clear = True

    if is_clear:
        return {"status": "exact", "match": top, "matches": [top]}

    shortlist = [item for item in matches if item["score"] >= 0.72][:5]
    if shortlist:
        return {"status": "ambiguous", "matches": shortlist}

    return {"status": "none", "matches": []}


def render_human(result: dict, query: str) -> str:
    status = result["status"]
    if status == "exact":
        match = result["match"]
        return (
            f"Found {match['type']} card for: {query}\n"
            f"Path: {match['path']}\n\n"
            f"{match['content'].rstrip()}\n"
        )
    if status == "ambiguous":
        lines = [f"Possible cards found for: {query}"]
        for item in result["matches"]:
            lines.append(f"- [{item['type']}] {item['title']} — {item['path']} (score {item['score']})")
        return "\n".join(lines) + "\n"
    return f"No directory cards found for: {query}\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search directory draft and entry cards")
    parser.add_argument("query", help="Business or entry name to search for")
    parser.add_argument("--root", default=".", help="Path to acadie_sol_directory root")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    cards = load_draft_cards(root) + load_entry_cards(root)
    matches = find_matches(cards, args.query)
    result = classify(matches)
    payload = {"query": args.query, **result}

    if args.format == "text":
        print(render_human(payload, args.query), end="")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
