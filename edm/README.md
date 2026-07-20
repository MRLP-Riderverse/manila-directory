# Manila Directory — EDM

This repository is the local-first data layer for a Manila-based electronic dance music directory.

The first directory group lives under `edm/`, so future Manila directory groups can be added without mixing their data. This is a derivative of the Acadie.sol directory protocol, not a shared database.

## Structure

```text
manila-directory/
└── edm/
    ├── entries/       # artist, collective, label, venue records
    ├── inbox/         # low-friction drafts
    ├── schemas/       # data contracts
    ├── scripts/       # validation and site export
    └── README.md
```

Markdown is the human source of truth; `meta.json` is the machine-readable index card; Git is the distribution layer. The public site is a separate repository/project under `manila/edm/`.

## Scope

The first release is English-first and focused on artist discovery and search. Tagalog fields can be added when the local steward supplies them. No Acadie.sol records are copied into this directory.

## Export

```bash
cd edm
python3 scripts/export_to_site.py --site ../../manila/edm
```

The export is local and offline. It does not commit, push, or deploy.
