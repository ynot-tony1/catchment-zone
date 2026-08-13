# Data sources

Every figure in catchment-zone traces back to a real, publicly published
source — an official government dataset, or (for many catchment boundaries)
a council's own published map or PDF, carefully digitized rather than
estimated. This page lists source categories and policy. The authoritative,
current list of every catchment source, with its own licence and
verification date, is `config/catchment-sources.yml`, not this page — this
page will always lag the registry slightly.

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

There is no single national catchment dataset for the UK; coverage is built
local authority by local authority as sources are found and verified. See
`config/catchment-sources.yml` for the live registry (over 100 local
authorities across England, Scotland, and Wales as of this writing) and
`docs/admissions-and-catchments.md` for how coverage is presented in the
product. `config/catchment-sources.yml`'s `candidates:` section also records
every local authority that has been investigated but not yet landed, with
the specific reason (login wall, bot-check block, no catchment data
published, etc.) — see `PROJECT_STATUS.md` for the full categorized gap
audit and a roadmap for closing the remaining login-wall sources.

### How a source lands

Two broad patterns, both represented in the registry:

- **Official GIS service, queried directly.** Many councils publish
  catchment boundaries through an ArcGIS Feature Service, a WFS endpoint, or
  a downloadable shapefile/GeoJSON, sometimes under an explicit Open
  Government Licence, sometimes with no licence statement published at all.
  `config/catchment-sources.yml`'s `download_url` points straight at that
  service or file; the ingestor re-queries it on each scheduled run.
- **Digitized from a published map with no API.** Where a council only
  publishes a static image, a PDF, or an interactive map with no documented
  reuse licence or accessible data endpoint, the boundary is traced from
  that published source using georeferencing (ground-control points such as
  road junctions, railway stations, or OS grid lines; colour-mask
  segmentation for colour-coded parish/priority maps; point-sample
  reconstruction via Voronoi tessellation clipped to real ONS administrative
  boundaries where only address-level point data, not a boundary map, is
  published) and committed to this repository as a static GeoJSON file under
  `data/digitized-catchments/`, referenced by `download_url` as a
  `raw.githubusercontent.com` URL. This is never invented or estimated
  geometry — every digitized boundary is traced against a real, checkable
  published source, and a fit is only shipped when it lands schools inside
  their boundary with a comfortable containment margin, not a marginal one.
  Where verification can't clear that bar, the source is left out rather
  than shipped with a caveat.

### Licensing

This is a private, non-commercial project. A source's licence status never
gates whether it is included — but it is always disclosed honestly.
`config/catchment-sources.yml`'s `licence` field records the source's own
stated licence where one exists (most commonly Open Government Licence
v3.0), and `"UNCONFIRMED - <why>"` where the source publishes no explicit
reuse licence. An unconfirmed licence is not treated as an implicit "no";
it is treated as an open question, recorded as such, and left for the user
to weigh.

### What is out of scope regardless of licensing

A genuine authentication/login wall — a form asking for a real credential to
view or download the data — is a hard stop; it is never bypassed. This is
independent of licensing: it doesn't matter whether the data behind the
login would otherwise be free to use. A Cloudflare/Incapsula-style bot-check
JavaScript challenge that a normal browser passes automatically is not a
login wall and is not in this category; if the sandbox environment can't get
past one (see the Category B list in `PROJECT_STATUS.md`), that's a network
limitation, not a policy one, and the user's own network sometimes succeeds
where the sandbox doesn't.

Querying an interactive council map tool's own public-facing backend
endpoint — the same request the tool's JavaScript makes in a normal
browser, with no login involved — is in scope and has been the single most
productive technique this project has used for landing sources that have no
documented "API," including legacy ASP.NET map tools with catchment
coordinates embedded directly in server-rendered markup.

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

- Any boundary that can't be traced back to a real published source. No
  catchment geometry in this project is invented, estimated, or
  extrapolated beyond what a verifiable source and a comfortable
  containment margin support.
- A genuine login/credential wall, regardless of what data sits behind it.
- A composite or aggregated "best school" ranking; see
  `docs/methodology.md` for why.
