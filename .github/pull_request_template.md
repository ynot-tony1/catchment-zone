## What this changes

## Why

## Testing

- [ ] Unit tests pass locally (`pnpm test` / `pytest`)
- [ ] Typecheck / lint pass (`pnpm typecheck`, `pnpm lint`, `ruff check`, `mypy`)
- [ ] `next build` succeeds
- [ ] Manually exercised the affected page(s)

## Data and admissions checklist (delete if not applicable)

- [ ] No guarantee language introduced (no "eligible", "guaranteed", "will be accepted")
- [ ] No composite/opaque ranking score introduced
- [ ] Catchment or admissions results still show academic year, source, and the standard disclaimer
- [ ] No user-submitted postcode or home coordinate is persisted or logged
- [ ] New data source has a documented licence in config/catchment-sources.yml or config/statistics-sources.yml

## Security checklist (delete if not applicable)

- [ ] No secrets committed
- [ ] No new client-exposed environment variable contains a credential
- [ ] Database errors are not surfaced raw to the client
