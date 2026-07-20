# Public Directory Payload Contract

`assets/directory-data.json` is the handoff contract from `acadie_sol_directory` to the static `acadie_sol` site.

The site should consume these declared fields instead of inventing canonical meaning in the browser.

## Top-level shape

```json
{
  "schema_version": 1,
  "generated_from": "/path/to/acadie_sol_directory",
  "entry_count": 59,
  "draft_count": 59,
  "published_count": 0,
  "items": []
}
```

## Item shape

```json
{
  "title": "Big D Drive-In",
  "name": "Big D Drive-In",
  "slug": "big-d-drive-in",
  "status": "draft",
  "draft": true,
  "badge": "DRAFT",
  "category": "food",
  "area": "Acadie-Bathurst",
  "public_area": "Acadie-Bathurst",
  "description": "Classic burger drive-in on St Peter Ave in Bathurst.",
  "notes": "Home of the Big D Burger.",
  "summary": "Classic burger drive-in on St Peter Ave in Bathurst.",
  "tags": ["drive-in", "burger", "restaurant"],
  "contact": {
    "address": "2035 St Peter Ave, Bathurst, NB E2A 7J5, Canada",
    "hours": "Mon-Sun 11:00–19:00",
    "phone": "506-546-3585",
    "email": "",
    "website": ""
  },
  "address": "2035 St Peter Ave, Bathurst, NB E2A 7J5, Canada",
  "hours": "Mon-Sun 11:00–19:00",
  "phone": "506-546-3585",
  "email": "",
  "website": "",
  "related_places": [],
  "sources": [],
  "source_type": "inbox",
  "path": "inbox/big-d-drive-in.md"
}
```

Legacy flat fields like `address`, `phone`, and `area` stay for backwards compatibility, but new rendering should prefer `contact` and `public_area`.

## Boundary principle

- Exporter normalizes public meaning.
- Site renders public meaning.
- Drafts may be incomplete, but the payload shape should stay stable.
