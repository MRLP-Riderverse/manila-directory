# Promote a Draft to an Official Entry

Use this when a draft is stable enough to become part of the official directory. Capture stays permissive; promotion is where canonical decisions happen.

## MVP public card contract

Every official entry should support a quick public card with:

- `name` — canonical display name
- `slug` — stable URL-safe identifier
- `status` — `published` for official entries
- `category` — coarse public type
- `short_description` — one-line summary
- `location.public_area` — public browse area, e.g. `Acadie-Bathurst`
- `tags` — small list of public browse/search hints
- `contact.address` / `phone` / `hours` / `email` / `website` — only public values

Full pages can later render richer notes, reviews, photos, source history, and unique local context. Do not force full-page richness into the quick card.

## Manual promotion checklist

1. Pick the canonical display name.
2. Pick the slug. Include branch/location when needed.
3. Preserve aliases for common local/user names.
4. Confirm category and public area.
5. Move stable public prose into `entry.md`.
6. Move machine-readable fields into `meta.json`.
7. Keep admin-only notes out of the public entry.
8. Keep uncertainty cautious: use sources or notes, not confident claims.
9. Run `python3 scripts/export_to_site.py --stdout` and inspect the payload.
10. Run `python3 scripts/export_to_site.py` to update the site payload.
11. Review the public card locally before publishing.

## Name policy

- Intake can lightly clean obvious title issues.
- Promotion is where canonical identity is decided.
- For chains or repeated names, prefer `Brand — Branch/Area` as display name.
- Keep `brand_name`, `branch_name`, and `aliases` in `meta.json` when they help search and future full pages.

## Repo boundary rule

- Directory repo decides meaning, status, canonical fields, and public/private separation.
- Site repo renders declared payload fields and handles UX interaction.
- If a rule should apply everywhere, put it in the directory/exporter, not only in browser JavaScript.
