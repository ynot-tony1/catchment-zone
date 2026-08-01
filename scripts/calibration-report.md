# Free-tier calibration report

This file is a template. It is filled in with real measurements the first
time a pilot import runs against the `aqua-roach` cluster, and is not a
substitute for actually running that import. Do not treat an unfilled
template, or a report older than the current schema/source list, as
authorization for a larger import.

## Procedure

1. Record cluster storage and monthly compute usage before import (CockroachDB
   Cloud console, Cluster > Metrics).
2. Import 10,000 representative school records (`ingestor import-gias
--row-limit 10000`).
3. Import trust relationships (`ingestor import-trusts`).
4. Import a selected set of metrics (`ingestor import-statistics`).
5. Import catchments for the Sheffield pilot authority (`ingestor
import-catchments --local-authority 373`).
6. Build the indexes defined in `packages/database/prisma/schema.prisma`
   (already applied by `prisma migrate deploy`).
7. Record cluster storage and monthly compute usage again.
8. Compute per-row and per-geometry storage cost from the delta.
9. Project full national-scale usage (approximately 32,000 open schools in
   GIAS, England-wide) from the per-row figures.
10. Project catchment usage separately, since it depends entirely on how
    many local authorities are added to `config/catchment-sources.yml`, not
    on school count.
11. Add a 30% safety margin to both projections.
12. Present the report below.
13. Do not start a larger import without explicit approval based on this
    report.

## Report

| Measurement            | Before                      | After | Delta |
| ---------------------- | --------------------------- | ----- | ----- |
| Storage used           | _pending first real import_ |       |       |
| Monthly compute (est.) | _pending first real import_ |       |       |

**Rows imported:** _pending_
**Geometry records imported:** _pending_

**Projected national storage (32,000 schools, 30% margin):** _pending_
**Projected catchment storage per additional local authority (30% margin):** _pending_

**Recommendation:** _pending; do not proceed to a full national GIAS import
until this section is filled in from a real measured pilot run._
