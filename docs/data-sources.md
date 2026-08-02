# Data sources

Every figure in catchment-zone traces back to an official, publicly
documented source. This page lists them. If a source is not listed here, it
is not used.

## School and trust directory

**Get Information about Schools (GIAS)**, `https://get-information-schools.service.gov.uk/`.
The Department for Education's live register of schools, academies,
colleges, and trusts. We use the Downloads section's establishment and group
data extracts (the "Establishment and group data" and "Scheduled extracts"
tabs), discovered at ingestion time rather than hardcoded to a dated file
name, since GIAS republishes extracts on its own schedule.

## Education statistics and performance

**Explore Education Statistics (EES) API**, base URL
`https://api.education.gov.uk/statistics/v1`, documented at
`https://api.education.gov.uk/statistics/docs/`. See
`config/statistics-sources.yml` for the specific publications currently
ingested (school capacity, pupil absence/attendance, school workforce). The
ingestor resolves the current dataset identifier and release for each
publication through the API's own catalogue rather than a hardcoded UUID.

## Catchment and priority admission areas

There is no single national catchment dataset in England; coverage is built
local authority by local authority as verified, licensed, machine-readable
sources are found. See `config/catchment-sources.yml` for the live registry
and `docs/admissions-and-catchments.md` for the coverage policy.

Current pilot source: **Sheffield City Council**, Primary and Secondary
Catchment Boundaries (academic year 2025-2026), published via the council's
ArcGIS Feature Service under the Open Government Licence v3.0 (contains OS
data, Crown copyright and database right). Source item pages:

- `https://sheffield-city-council-open-data-sheffieldcc.hub.arcgis.com/datasets/1cfbc328f918482bb25f4d092eb45d8b_1/about` (primary)
- `https://sheffield-city-council-open-data-sheffieldcc.hub.arcgis.com/datasets/a3883491804f4886a33c1b66b59fbe47_3/about` (secondary)

## Admission arrangements

Where machine-readable oversubscription criteria are not published in a
structured format (the common case), we store the official policy URL, the
academic year, the admission authority name, and a short manually verified
neutral summary. We do not run automated interpretation of admissions PDFs
into binding eligibility rules.

## Postcode lookup

Postcode-to-coordinate lookup uses a configurable geocoder
(`POSTCODE_GEOCODER` environment variable), defaulting to `postcodes.io`, a
free, open UK postcode API built on Ordnance Survey and ONS open data. We
cache only the postcode-to-coordinate result (see `PostcodeCache` in
`docs/database.md`), never the fact that a specific user looked it up.

## What we deliberately do not use

- Interactive council map applications with no documented API or reuse
  licence. We do not scrape these.
- Any source without an explicit, checkable licence statement.
- A composite or aggregated "best school" ranking; see
  `docs/methodology.md` for why.
