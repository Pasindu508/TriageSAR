# packages/shared

`openapi.json` is the machine-readable contract between the API (`apps/api`) and the web app (`apps/web`).
It is generated, not hand-written:

```bash
python scripts/export_openapi.py
```

The TypeScript types in `apps/web/src/types/api.ts` mirror this schema (`schema_version` 1.0).
