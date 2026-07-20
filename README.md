# Manila Directory

Local-first source repository for a Manila-based directory. The first public group is EDM, but the repository is intentionally structured to support additional directory groups later.

## Intake flow

Everything can start in the top-level `inbox/`. A small router classifies clear EDM drafts and keeps ambiguous material in `inbox/needs-review/`:

```bash
python3 scripts/route_inbox.py
```

```text
manila-directory/
├── inbox/                 # easiest drop zone for raw submissions
│   └── needs-review/      # uncertain group; never silently published
└── edm/                   # first directory group
    ├── inbox/             # routed EDM drafts
    ├── entries/           # cleaned canonical records
    ├── schemas/
    ├── scripts/
    └── tests/
```

## Publish path

1. Drop a draft into `inbox/`.
2. Include `Group: edm` when known. Otherwise use clear EDM tags such as `house`, `techno`, or `DJ`.
3. Run `python3 scripts/route_inbox.py`.
4. Review and clean the routed draft in `edm/inbox/`.
5. Promote stable records into `edm/entries/<slug>/` with `entry.md` and `meta.json`.
6. Export the reviewed data into the separate site repository:

```bash
cd edm
python3 scripts/export_to_site.py --site ../../manila/edm
```

The site never decides group membership. The data repository and exporter do. The browser only renders the generated payload.

## Language

The initial public layer is English-first. Tagalog can be added later from steward-provided copy. French/Acadian language fields are not part of this derivative.
