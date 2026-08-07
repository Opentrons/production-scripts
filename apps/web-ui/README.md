# Web UI

The repository's only Vue application. It contains the dashboard, downloads, robot operations, test management, data views, and version workflows.

```text
src/
├── views/                   # all Vue files, grouped by feature
│   ├── dashboard/
│   ├── data/
│   ├── devices/components/
│   ├── layouts/
│   ├── test_modules/components/
│   └── version_modules/
├── styles/                  # standalone CSS, grouped by feature
│   ├── dashboard/
│   └── version_modules/
└── scripts/                 # all TypeScript files, grouped by responsibility
    ├── api/
    ├── router/
    ├── stores/
    ├── types/
    ├── utils/
    └── modules/
        ├── test_modules/
        └── version_modules/
```

```bash
make web-install
make web-dev
make web-build
```
