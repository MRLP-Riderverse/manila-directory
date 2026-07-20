# Manila EDM Directory — working rules

- This is the source-of-truth data layer; do not add HTML/CSS/JS here.
- Every published entry has both `entry.md` and `meta.json`.
- Drafts begin in `inbox/`; promote only after the public card fields are stable.
- Keep this project independent from Acadie.sol. Do not import Acadie records.
- English is the initial public language. Add Tagalog only from steward-provided wording.
- Run `python3 scripts/export_to_site.py --site ../../manila/edm` after data changes.
