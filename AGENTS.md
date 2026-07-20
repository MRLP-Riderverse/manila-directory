# Manila Directory — intake rules

- Put raw submissions in the top-level `inbox/`; do not make the steward choose a code folder.
- Add `Group: edm` when the directory group is known.
- Run `python3 scripts/route_inbox.py` before editing or exporting.
- Ambiguous material belongs in `inbox/needs-review/` until a human chooses a group.
- The router never overwrites an existing draft.
- Only `edm/entries/` is exported to the public EDM site after review and promotion.
