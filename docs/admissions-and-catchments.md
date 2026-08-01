# Admissions and catchments

This is the most sensitive part of SchoolScope England and the part most
likely to mislead a parent if it is built carelessly. Read this before
touching any code under `/admissions`, `services/ingestor/src/schoolscope_ingestor/adapters/catchments.py`,
or `AdmissionArrangement` / `CatchmentArea` handling.

## What this feature is not

It is not an eligibility checker. A polygon match is not an offer, and this
application never claims otherwise. The application must never emit or
render the words "eligible", "guaranteed", or "will be accepted" in relation
to a specific address and a specific school.

## Terminology

Different admission authorities use different terms for the same broad idea.
We preserve the source's own term rather than renaming everything to
"catchment":

* **Catchment area**, used by authorities with a fixed, address-based
  priority zone.
* **Priority admission area**, a common alternative phrasing for the same
  concept.
* **Designated area**, used by some faith and voluntary-aided schools.
* **Admissions area**, a general term some authorities use in policy
  documents.

## Admission criteria we know exist and must represent correctly

* Fixed catchment polygon
* Straight-line distance from the school
* Distance from a nodal point (not the school gate itself)
* Feeder school relationships
* Faith-based criteria
* Selective testing (grammar schools)
* Multiple overlapping criteria applied in a stated priority order
* No catchment area at all, with places allocated purely by other criteria

Being inside a catchment or priority area, where one exists, typically grants
priority, not a guarantee. Siblings, looked-after-child status, special
educational needs, and faith criteria commonly rank above simple geographic
proximity. The admission authority (the local authority for community
schools, the school or trust itself for voluntary-aided, foundation, and
academy schools) makes the actual decision, not this application.

## Result statuses

The `/api/catchments/check-point` endpoint and the `/admissions` page return
only these statuses. No other status string is permitted anywhere in the
codebase:

| Status | Meaning |
|---|---|
| `INSIDE_OFFICIAL_PRIORITY_AREA` | The point falls inside a published boundary for the given school and academic year. |
| `OUTSIDE_OFFICIAL_PRIORITY_AREA` | The point falls outside a published boundary that does exist for the given school and academic year. |
| `NO_FIXED_CATCHMENT_USED` | This school's admission authority does not use a fixed catchment polygon (e.g. pure distance-from-school or feeder-school criteria). |
| `OFFICIAL_BOUNDARY_NOT_AVAILABLE` | We do not currently hold official boundary data for this school or local authority. This is the default for almost all of England right now; see Coverage below. |
| `POSTCODE_RESULT_NEAR_BOUNDARY` | The postcode centroid is within `CATCHMENT_BOUNDARY_WARNING_METRES` of a boundary edge, so an address-level decision cannot be made reliably from a postcode centroid alone. |
| `ACADEMIC_YEAR_NOT_AVAILABLE` | We hold boundary data for this school, but not for the requested academic year. |

Every result, regardless of status, renders this disclaimer:

> This result shows the published priority or catchment area for the
> selected academic year. It does not guarantee that a school place will be
> offered. Check the official admissions policy before applying.

## Coverage

SchoolScope England does not claim, and has never claimed, nationwide
catchment coverage. See `config/catchment-sources.yml` for the current
source list. As of this writing that list has one pilot local authority:

* **Sheffield** (DfE local authority code 373), primary and secondary
  catchment boundaries for academic year 2025-2026, published under the Open
  Government Licence via the council's own ArcGIS Feature Service. Sheffield's
  own dataset description states these boundaries are legally defined by
  postcode and street number, not by the mapped polygon, and that the map is
  illustrative only. That caveat is preserved verbatim in the UI, not
  softened.

Expanding coverage means adding a verified entry to
`config/catchment-sources.yml` (see the `data_source` issue template), never
scraping an interactive council map that has no documented reuse licence or
API.

## Postcode handling

A postcode centroid is an approximation, sometimes hundreds of metres from
any given address inside that postcode. Where a centroid result lands near a
boundary, we say so explicitly and point the user at the council's own
address-level checker rather than asserting a result we cannot stand behind.

We do not store a user's submitted postcode against any identity. See
`docs/privacy.md`.

## Historical offers

Where a local authority publishes prior-year allocation outcomes (applications,
places offered, last distance offered), we store them labelled clearly as:

> Historical information only. It is not a forecast or guarantee for the next
> admissions round.

Boundaries, admission numbers, and oversubscription pressure change year to
year. A furthest-distance-offered figure from a previous year is context, not
a prediction.
