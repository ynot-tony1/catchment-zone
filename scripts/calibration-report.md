# Free-tier calibration report

This file is filled in with real measurements from the pilot import run
against the `aqua-roach` cluster on 2026-08-02, and is not a substitute for
actually running that import. Do not treat an unfilled template, or a report
older than the current schema/source list, as authorization for a larger
import.

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

## What actually ran (2026-08-02)

Step 4 (`import-statistics`) did not import any metric rows. That command
only resolves the current release for each configured DfE publication; it
has never actually fetched and written `SchoolMetric` rows (a pre-existing,
explicitly documented TODO in `adapters/statistics.py`, not something this
pilot broke). Live investigation during this pilot also found that the only
two publications that currently resolve at all (`pupil-absence-in-schools-in-
england`, `pupil-attendance-in-schools`) only expose Local
authority/Regional/National-level data via the EES API, not per-school rows
— so `SchoolMetric`, which requires a non-null `school_urn`, cannot be
populated from either source as currently designed. The other two configured
publications (`school-capacity`, `school-workforce-in-england`) don't
currently exist in the EES API's public catalogue at all. Metrics import is
therefore a known, open gap — see `PROJECT_STATUS.md` — not part of this
report's measurements.

Steps 2, 3, 5 and 6 ran for real against production and are what this report
measures. Getting there also required fixing four real bugs surfaced only by
running the pipeline for real (missing `updated_at` on every raw upsert,
missing `local_authorities` population, missing id-generation for
`catchment_sources`/`catchment_areas`, and `catchment_areas` never being
persisted at all plus two missing unique indexes) — see recent commit
history for detail.

## Report

**Method note on storage figures:** the `school_ingestor` credential (by
design, least-privilege) does not have the `VIEWACTIVITY` grant CockroachDB
requires to read cluster-level storage/compute metrics via SQL, and this
report was produced without console access. The before/after cluster-level
figures below are therefore not available from this session; the storage
figures instead come from `pg_column_size()` summed over every row actually
written, queried directly against production immediately after the import.
That is a real, precise measurement of each row's logical payload size, but
it is not the same number as CockroachDB Cloud's on-disk storage metric,
which additionally reflects the cluster's replication factor (commonly 3x on
CockroachDB Cloud), index storage, and MVCC version history. Treat the
figures below as a solid lower bound and multiply by roughly 3-4x for a
rough estimate of actual on-disk consumption. Whoever next has console
access should paste in the real before/after console figures to replace this
section outright.

| Table               | Rows imported | Logical bytes (`pg_column_size` sum) | Bytes/row (avg) |
| -------------------- | -------------: | -------------------------------------: | ----------------: |
| schools              | 10,000         | 2,614,272                               | 261.4              |
| local_authorities    | 92              | 4,453                                   | 48.4               |
| academy_trusts       | 7,176           | 654,817                                 | 91.3               |
| catchment_sources    | 2               | 1,013                                   | 506.5              |
| catchment_areas      | 127             | 2,879,873                               | 22,676.2           |
| **Total**            | **17,397**      | **6,154,428 (5.87 MiB)**                 |                    |

**Rows imported:** 10,000 schools, 92 local authorities, 7,176 academy
trusts (this is already the full national trust register — `import-trusts`
was not run with a row limit).
**Geometry records imported:** 127 catchment areas for Sheffield (LA 373):
101 primary + 26 secondary, 0 rejected. Backed by 2 `catchment_sources` rows
(one per source type).

**Projected national storage (32,000 schools, 30% margin):**
32,000 x 261.4 bytes/row × 1.3 ≈ 10.9 MB logical (≈ 33-44 MB on-disk at a
3-4x replication/index multiplier). `local_authorities` and
`academy_trusts` are already at or near national scale from this pilot
(England has on the order of 150 local authorities and this import already
found 92 from a 10,000-school, non-exhaustive sample) and do not scale
further with school count in any material way.

**Projected catchment storage per additional local authority (30%
margin):** 2,880,886 bytes (2.75 MiB) x 1.3 ≈ 3.57 MiB logical per local
authority (≈ 10.7-14.3 MiB on-disk at a 3-4x multiplier), dominated almost
entirely by `catchment_areas` geometry, not the `catchment_sources` summary
row. Sheffield's 127 catchment areas are one specific local authority's
data density and may not be representative of every LA (more or fewer
schools, more or less detailed source geometry); treat this as a
single-sample estimate, not a guaranteed per-LA ceiling.

**Recommendation:** Catchment geometry, not school count, is the dominant
storage driver by a wide margin — one local authority's catchment data
(≈2.75 MiB logical) is roughly the same order of magnitude as the entire
10,000-school pilot's school data (≈2.61 MiB logical). A national GIAS
import (schools/trusts/local authorities) looks cheap and safe to project
from this data. Catchment coverage should be rolled out deliberately, one
local authority at a time, with actual CockroachDB Cloud console storage
figures checked after each addition, rather than assumed to scale linearly
from this single Sheffield sample. Before approving a larger GIAS import,
someone with CockroachDB Cloud console access should replace the "Method
note on storage figures" section above with real before/after cluster
metrics so the on-disk replication multiplier is measured rather than
estimated. The `import-statistics` gap (see "What actually ran" above)
means this report has no data point yet for `SchoolMetric` storage cost at
any scale — that needs its own calibration pass once a school-level metrics
source is identified.
