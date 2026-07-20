from __future__ import annotations

import json
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lookup_cards.py"


def run_lookup(tmp_path: Path, query: str) -> dict:
    result = subprocess.run(
        ["python3", str(SCRIPT), query, "--root", str(tmp_path), "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_exact_draft_match_returns_card_content(tmp_path: Path):
    write(
        tmp_path / "inbox" / "eastside-deli.md",
        "# Draft: Eastside Deli\n\n## Notes\nGreat donair.\n\n## Admin notes\n- Submitted by : Acadie.sol\n",
    )

    payload = run_lookup(tmp_path, "Eastside Deli")

    assert payload["status"] == "exact"
    assert payload["match"]["title"] == "Eastside Deli"
    assert "Great donair." in payload["match"]["content"]
    assert payload["match"]["type"] == "draft"


def test_ambiguous_lookup_returns_candidate_cards(tmp_path: Path):
    write(
        tmp_path / "inbox" / "big-d-drive-in.md",
        "# Draft: Big D Drive-In\n\n## Notes\nClassic drive-in.\n",
    )
    write(
        tmp_path / "inbox" / "big-deal-market.md",
        "# Draft: Big Deal Market\n\n## Notes\nCorner store.\n",
    )

    payload = run_lookup(tmp_path, "Big")

    assert payload["status"] == "ambiguous"
    assert len(payload["matches"]) >= 2
    titles = {match["title"] for match in payload["matches"]}
    assert "Big D Drive-In" in titles
    assert "Big Deal Market" in titles


def test_specific_prefix_query_prefers_big_deal_market_as_exact(tmp_path: Path):
    write(
        tmp_path / "inbox" / "big-d-drive-in.md",
        "# Draft: Big D Drive-In\n\n## Notes\nClassic drive-in.\n",
    )
    write(
        tmp_path / "inbox" / "big-deal-market.md",
        "# Draft: Big Deal Market\n\n## Notes\nCorner store.\n",
    )

    payload = run_lookup(tmp_path, "Big Deal")

    assert payload["status"] == "exact"
    assert payload["match"]["title"] == "Big Deal Market"
    assert payload["match"]["type"] == "draft"


def test_clean_entry_can_be_found_from_meta_name(tmp_path: Path):
    write(
        tmp_path / "entries" / "marie-boudreau" / "meta.json",
        json.dumps(
            {
                "slug": "marie-boudreau",
                "name": "Marie Boudreau",
                "category": "artist",
                "short_description": "Visual artist.",
            }
        ),
    )
    write(
        tmp_path / "entries" / "marie-boudreau" / "entry.md",
        "# Marie Boudreau\n\nAcadian visual artist.\n",
    )

    payload = run_lookup(tmp_path, "Marie Boudreau")

    assert payload["status"] == "exact"
    assert payload["match"]["type"] == "entry"
    assert payload["match"]["path"].endswith("entries/marie-boudreau/entry.md")


def test_none_when_no_cards_match(tmp_path: Path):
    write(tmp_path / "inbox" / "frost-bite.md", "# Draft: Frost Bite\n")

    payload = run_lookup(tmp_path, "Nonexistent Cafe")

    assert payload["status"] == "none"
