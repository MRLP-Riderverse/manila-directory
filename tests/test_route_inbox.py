from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "route_inbox.py"
spec = importlib.util.spec_from_file_location("route_inbox", SCRIPT)
assert spec is not None and spec.loader is not None
route_inbox = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = route_inbox
spec.loader.exec_module(route_inbox)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_explicit_edm_group_routes_to_edm_inbox(tmp_path: Path):
    source = tmp_path / "inbox" / "artist.md"
    write(source, "# Draft: Manila Artist\n\nGroup: edm\nCategory: artist\nTags: techno | Manila\n")

    result = route_inbox.route_file(source, tmp_path)

    assert result.group == "edm"
    assert result.destination == tmp_path / "edm" / "inbox" / "artist.md"
    assert result.destination.exists()
    assert not source.exists()


def test_unambiguous_edm_tags_route_to_edm_inbox(tmp_path: Path):
    source = tmp_path / "inbox" / "club-artist.md"
    write(source, "# Draft: Club Artist\n\nCategory: musician\nTags: EDM | house | Manila\n")

    result = route_inbox.route_file(source, tmp_path)

    assert result.group == "edm"
    assert result.destination.exists()


def test_unknown_group_stays_in_needs_review(tmp_path: Path):
    source = tmp_path / "inbox" / "unclear.md"
    write(source, "# Draft: Unclear Manila Project\n\nCategory: project\nTags: community\n")

    result = route_inbox.route_file(source, tmp_path)

    assert result.group is None
    assert result.destination == tmp_path / "inbox" / "needs-review" / "unclear.md"
    assert result.destination.exists()


def test_non_markdown_files_are_ignored(tmp_path: Path):
    source = tmp_path / "inbox" / "notes.txt"
    write(source, "not a draft")

    assert route_inbox.route_file(source, tmp_path) is None
    assert source.exists()
