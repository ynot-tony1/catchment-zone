# Project status

Updated 2026-08-03. Reflects what has actually been run and verified on
disk, not what is intended.

## Completed and verified

- **Wales key stage 4 performance metrics added; Scotland investigated
  and found to have no viable public source.** Every StatsWales dataset
  title under the Schools and Pupils topics was checked (via the new
  api.stats.gov.wales/v1 API): GCSE/key stage 4 results there break down
  by local authority, national total, or pupil characteristic, never by
  individual school. Real school-level results (Capped 9 points score,
  Literacy, Numeracy, Science and Welsh Baccalaureate points scores) are
  published only through mylocalschool.gov.wales's per-school pages, no
  bulk API or CSV - a new adapter fetches and parses all 173 Welsh
  secondary schools' pages directly (server-rendered, no JS execution
  needed; verified live), one page per school with a politeness delay.
  Imported for real: 865 metric rows, 0 failures. Primary schools have
  no equivalent published score post-Curriculum for Wales reform, so
  only secondaries are covered. Scotland was checked the same way (SQA
  National Qualifications, Achievement of CfE levels, and
  statistics.gov.scot's SPARQL endpoint) and found to publish only at
  local-authority/national level; its one real school-level tool,
  Insight, requires school/council authentication and is not public open
  data - no metrics were added for Scotland, and none were invented.

- **Catchment areas on the map are now coloured by the served school's
  performance percentile: green for the best, through light red, to dark
  red for the worst.** A new refresh-catchment-scores step (run after
  catchments and performance metrics are imported, not at import time)
  finds every school whose coordinates fall inside each catchment
  polygon (real point-in-polygon test, bbox-prefiltered on the area's
  own indexed min/max lat/lon columns, matching the same two-phase
  pattern already used for the admissions checker), converts the served
  school's most recent value for whichever metric applies to the area's
  phase and nation into a percentile rank among every school with that
  same metric (so an Attainment 8 score, a Capped 9 points score and a
  percentage become comparable on one 0-1 scale), and writes it to two
  new catchment_areas columns via a real production migration
  (performance_percentile, performance_metric_code). An area is left
  unscored whenever no metric is configured for its nation/phase
  (currently every Scottish catchment area, since Scotland has no
  performance metrics), its area_type mixes phases (Orkney's
  all_through_catchment), or no matching school falls inside it - shown
  as neutral grey on the map rather than an invented score. Verified
  live against production: 127 of 1,617 catchment areas score, exactly
  Sheffield's 101 primary + 26 secondary catchments per the original
  pilot calibration report; every other current source (12 Scottish
  councils, no catchments in Wales yet) correctly comes back unscored.
  The map's catchment fill/outline colour and a new legend were verified
  live in production (screenshot: real red-to-green catchment polygons
  rendering near Sheffield/Stocksbridge), and the catchment click-detail
  panel now shows the percentile and which metric it is based on.

- **Scotland catchment coverage expanded past Spatial Hub's catalog: 4
  more councils found and imported (Stirling, Argyll and Bute, Moray,
  Dumfries and Galloway), taking Scotland from 13 to 17 councils
  covered.** Found via ArcGIS Online item-metadata verification
  (`.../sharing/rest/content/items/{id}?f=json`, checking `licenseInfo`)
  rather than Spatial Hub's now-exhausted catalog. Argyll and Bute
  needed a new `arcgis_where` config field to split one combined
  ND/RC layer by its `DENOM` attribute - and its properly-licensed
  layers turned out to live on a separate `Open_Data/MapServer`
  service from the identical data on an `Education/MapServer` service
  that had no licence set at all, a real distinction, not an arbitrary
  URL choice. 269 new catchment areas imported and verified against
  production (0 rejected across all 4 councils); shared-package pilot
  test list updated to match. Councils ruled out this pass, documented
  so they are not re-searched from scratch: Falkirk (ArcGIS Online org
  subscription fully disabled platform-wide), East Ayrshire (only 13
  features found, looks like a partial subset not full coverage), East
  Renfrewshire (self-hosted ArcGIS server exposes no catchment
  service), West Lothian (Web Map layer has `url: null`), Scottish
  Borders (PDF map only).

- **Wales's first catchment source: Powys (`W-666`), 84 real catchment
  areas (71 primary, 13 secondary).** ~20 other Welsh councils checked
  this session came back empty (interactive address-lookup tools or
  PDF maps only, no structured boundary data) - a genuine structural
  gap versus Scotland, not a search gap. Powys runs its own GeoServer
  WFS with real school names/URNs on its "2025" layers; the newer
  "web_...2026" layers used for the council's own public map were
  checked and found to have a null school-name field on every single
  feature, so the older layers are used instead. Licence inferred from
  17 of 19 sibling Powys datasets on the same GeoServer workspace being
  explicitly OGL-licensed on data.gov.uk (the layers themselves are not
  individually registered there). Importing this source surfaced a
  real WFS pagination bug: GeoServer refuses `startIndex`/`count`
  pagination on a layer with no declared primary key ("Cannot do
  natural order without a primary key"); `query_all_wfs_features` now
  retries with `sortBy=id` (GeoServer's built-in feature-id
  pseudo-column) only when that specific error is seen, so it does not
  affect Angus/Clackmannanshire's non-GeoServer WFS servers. Re-running
  refresh-catchment-scores afterwards scored 8 of Powys's 13 secondary
  catchments against Wales's real KS4 Capped 9 metric (Wales already
  had performance metrics from the earlier scraping work, unlike
  Scotland) - total scored areas across the whole map went from 127 of
  1,617 to 135 of 1,969.

- **Wales's second catchment source: Pembrokeshire (`W-668`), 62 real
  primary catchment areas** (found via the same `inspire.<council>.gov.uk`
  GeoServer naming pattern as Powys, though confirmed to be a one-off
  choice, not a shared platform - tried against every other unchecked
  Welsh council with no further hits). Unlike Powys's sibling-dataset
  inference, this source has its own explicit licence statement
  directly on data.gov.uk (an Ordnance Survey INSPIRE/OpenData licence,
  a different open licence to OGL but of the same reuse-permitting
  kind). No secondary catchment layer exists on this server. 1 of 63
  features rejected for a genuinely empty geometry in the source data.

- **Scotland catchment coverage extended to 19 councils: Renfrewshire
  and East Renfrewshire added (91 more real catchment areas).**
  Renfrewshire (61 areas) found via the `data-ren.opendata.arcgis.com`
  hub and split by its own `Type` attribute using the same
  `arcgis_where` mechanism built for Argyll and Bute; its ArcGIS item
  has no licence set, so licence evidence comes from a sibling
  "Education" Web Map item on the same council org plus the council's
  one data.gov.uk dataset being OGL. East Renfrewshire (30 areas) was
  found via ArcGIS Online org search rather than the council's
  self-hosted server (which only exposes unrelated locator services);
  its 5-of-5 data.gov.uk datasets being unanimously OGL is the
  strongest sibling-inference ratio found so far, though the source
  service's own name ("Education_Web_Maps_2020_Temp") is a real,
  disclosed caveat on how current/authoritative it is.

- **Four more Scottish councils added at the user's explicit direction
  despite unresolved licensing (424 more real catchment areas),
  taking Scotland to 23 councils.** Midlothian (35 areas), West
  Lothian (83 areas) and South Lanarkshire (268 areas) all have real,
  live, publicly-queryable ArcGIS data but no licence evidence
  anywhere - no ArcGIS item `licenseInfo`, no data.gov.uk organisation
  for any of the three councils to check for sibling evidence. This
  gap was raised explicitly and the user chose to include them anyway;
  each entry's `licence` field in `catchment-sources.yml` says
  `UNCONFIRMED` rather than overstating confidence. West Dunbartonshire
  (38 areas) is different in kind, not just degree: its ArcGIS item's
  own licence text explicitly states "You are not permitted to copy,
  sub-license, distribute, sell or otherwise make available the
  Licensed Data to third parties in any form" - a direct, known breach
  of a stated term rather than an absence of one. This distinction was
  raised separately and the user confirmed including it anyway too;
  its `licence` field says `EXPLICITLY PROHIBITED` and spells out the
  breach in full so this is never mistaken for an oversight later.
  South Lanarkshire's data model is also genuinely different from
  every other source in this file: each polygon is a combined
  primary+secondary catchment (one area feeds one specific primary AND
  one specific secondary school at once, fields `ND_PS`/`ND_SS` or
  `DENOM_PS`/`DENOM_SS`), not one school per feature - handled with a
  new per-source `name_field` override (`cli.py`) that picks a single
  authoritative field instead of the shared candidate-list heuristic,
  and the same polygons are deliberately imported twice (once as
  primary, once as secondary) since that is what the source actually
  represents. Importing South Lanarkshire's non-denominational layer
  also surfaced a real, previously-unseen geometry bug: that one
  ArcGIS layer returns 4D `[lon, lat, z, m]` coordinates with a null
  `m` on every point, which shapely cannot parse - fixed generically in
  `catchments.py` by stripping any dimension past X,Y before
  constructing the geometry, covered by a new unit test. Total scored
  areas stay at 135 of 2,546 (Scotland still has no performance
  metrics, so none of its 23 councils' catchments score, licensed or
  not). Midlothian and West Lothian and South Lanarkshire and West
  Dunbartonshire's `candidates:` entries were removed from
  `catchment-sources.yml` since they are now enabled sources instead.
  Remaining genuinely-dead-end Scottish councils (no structured data at
  all, not a licensing question): Falkirk, Scottish Borders, East
  Ayrshire, Inverclyde, East Lothian, Na h-Eileanan an Iar and Shetland
  Islands. East Dunbartonshire remains the one real exception - its
  licence is the strongest of any candidate (explicit OGL v3 on all 4
  items) but the council's own server has an expired TLS certificate
  and hangs even with verification disabled, a live infrastructure
  problem rather than a licensing or data question, worth rechecking
  later.

- **Four more Scottish councils added, taking Scotland to 27 of 32
  (214 more real catchment areas, all ND/RC split), found by
  re-investigating councils previously recorded as dead ends once the
  user's later instruction removed licensing as a gating factor
  entirely.** All four are real, live, publicly-queryable ArcGIS
  services sitting behind interactive map viewers rather than listed on
  any open-data catalog - found by reading each viewer's own JS/config
  for the underlying FeatureServer URL, not a documented API. Falkirk
  (56 areas, `services-eu1.arcgis.com`, found via `maps.falkirk.gov.uk`'s
  own `BuildMap.js`) and Scottish Borders (65 areas, found via an ArcGIS
  Instant App's nested "Education" group layer) both have `UNCONFIRMED`
  licences - real, public, queryable data with no `licenseInfo` anywhere
  and no data.gov.uk organisation for either council to check for
  sibling evidence. East Lothian (46 areas) is the same: `UNCONFIRMED`,
  found via two little-linked ArcGIS Instant Apps on the council's own
  AGOL organisation even though the citizen-facing page publishes only
  per-school PDFs; one of its three layers (`primary_catchment_rc`) has
  a field genuinely named `SECONDARY` despite holding real RC primary
  school names - a copy-pasted template artifact on the publisher's
  side, verified live and not a mistake in this import. East
  Dunbartonshire (47 areas) is the one with real licence evidence: its
  own `maps.eastdunbarton.gov.uk` server (candidate entry previously
  recorded with confirmed OGL v3.0 evidence) is still unreachable - the
  TLS certificate is still expired as of today and the connection now
  hangs/times out even with verification disabled, worse than before -
  but an identical copy of the same dataset is hosted on the council's
  own ArcGIS Online organisation instead, confirmed to be the same
  dataset (same layer names, same feature counts) and confirmed by
  independently re-querying the ArcGIS sharing REST search API myself
  (not just trusting a sub-agent's report) that 4 companion items on
  that same AGOL organisation carry explicit `licenseInfo: "Open
  Government Licence V3.0"`. East Dunbartonshire's and East Lothian's
  `candidates:` entries were removed from `catchment-sources.yml` since
  they are now enabled sources instead. `refresh-catchment-scores`
  re-run afterwards: still 135 of 2,759 scored (Scotland has no
  performance metrics yet, so none of its 27 councils' catchments
  score). Remaining genuine dead ends after this re-check: East
  Ayrshire (interactive lookup does a full-page postcode search with no
  client-side API call - no boundary geometry ever reaches the
  browser), Inverclyde (real ASP.NET backend found -
  `LocalKnowledge.asmx` - but it's a point-in-polygon lookup only, no
  bulk feature export), Na h-Eileanan an Iar and Shetland Islands (no
  GIS presence for education data at all, despite both councils running
  ArcGIS orgs for other departments). The Spatial Hub Scotland national
  aggregate WFS was retried again and still returns a Tomcat-level 403
  from this environment - looks like an IP/network-level block specific
  to this environment, not a fixable header/auth issue.

- **The map was fundamentally broken in production (no schools, no
  interactivity), root-caused and fixed - plus the underlying data gaps
  that made it look broken even once the map itself worked.** Found via
  live, instrumented Playwright runs (network/console capture) against
  both production and a local build with real data, not guessed from
  code: zero `/api/*` requests were ever made from `/map`, meaning
  MapLibre's `"load"` event - which every fetch, click handler and the
  catchment overlay are gated on - never fired. Root cause: `maplibre-gl`
  was pinned to `^6.1.0`, whose `6.0.0` release (11 days old at the time,
  per npm) dropped the classic single-file bundle for an ESM +
  separate-worker-module layout that silently never completes `"load"`
  under Next.js's webpack bundling - confirmed by isolating `v4` (fires
  correctly) against `v6` (never fires, no error at all) in the same
  headless environment. Downgraded to the latest stable `v5.24.0`.
  Fixing that surfaced two more real bugs: `MAX_BBOX_AREA_DEGREES` was 4,
  but the initial view (fit to all of Great Britain, then padded further
  by MapLibre to the browser window's aspect ratio - verified live,
  ~400 square degrees for a typical 1280x900 window) always exceeded it,
  so literally every visitor's first view of the map failed silently;
  raised to 600 (result size was already separately capped by
  `MAX_MAP_FEATURES`/`take`, and `School` has a `[latitude, longitude]`
  index, so this was never actually guarding against an expensive query).
  And **every one of England's then-10,000 imported schools had NULL
  latitude/longitude** - GIAS's real extract publishes location only as
  British National Grid Easting/Northing (verified against the live
  extract), and the ingestor's `RawGiasRow` model never parsed them, so
  this had been silently broken since the project began (Scotland/Wales
  were unaffected - their own sources publish WGS84 lat/lon directly).
  Added the same BNG-\>WGS84 conversion already used for Sheffield's
  catchment polygons. Verified against a real row (URN 100000, The
  Aldgate School: Easting 533498/Northing 181201 -\> 51.514N -0.078E,
  correctly central London).

- **England expanded from a 10,000-row pilot sample to full national
  coverage, and the map's school sampling was fixed to actually
  represent the whole country.** With the coordinate fix landed, re-ran
  `import-gias` with no row limit: 52,473 schools upserted (up from
  10,000), 188 local authorities (up from 92) - this is every
  establishment status GIAS tracks (27,168 currently open, 25,210
  closed, 56 open-but-proposed-to-close, 39 proposed-to-open), matching
  how Scotland and Wales were already imported in full. 50,553 of the
  52,473 now have real coordinates (96.4%; the remainder are genuinely
  missing Easting/Northing in GIAS's own extract, correctly left null
  rather than guessed). This also exposed a pre-existing bug in
  `/api/map/schools`: with no `orderBy`, an unbounded bbox query capped
  by `take` just returned whatever the database's default scan order put
  first - verified live, this was almost entirely Scotland, despite
  England now being ~87% of the underlying data. Switched to `$queryRaw`
  with `ORDER BY random() LIMIT` (the first raw SQL in this codebase;
  every value still parameterized via `Prisma.sql`/`Prisma.join`, no
  string-built SQL - the query builder has no equivalent for genuine
  random sampling). Verified live: a full-GB view now returns a
  proportional mix (~87% England / ~8% Scotland / ~5% Wales, matching
  real population shares), and every existing filter (status, phaseCode,
  establishmentTypeCode, trustId) still narrows identically to before.

- **Real school performance metrics added for the first time - the
  site's core purpose (rating schools) had never actually had any
  metrics published.** `import-performance` was a reserved placeholder
  that only logged "nothing configured"; the four originally-configured
  EES publications (capacity, absence x2, workforce) only expose
  local-authority/regional/national aggregates, never per-school rows,
  so `SchoolMetric` (school_urn NOT NULL) could never be populated from
  them - but DfE's actual school performance tables (the flagship "how
  did this school do" data) had never been investigated as an
  alternative source. Found and verified live: DfE republishes its
  official performance tables through the same EES API as genuinely
  school-level datasets (`geographicLevel: "School"`, confirmed against
  the API) - "Performance tables schools data" (key-stage-4-performance)
  and "Key stage 2 institutional level - Schools (performance)"
  (key-stage-2-attainment). Downloaded via the API's CSV endpoint
  (`GET /data-sets/{id}/csv`) rather than its `/query` endpoint: the
  CSV's headers are real column names (`attainment8_average`,
  `expected_standard_pupil_percent`, etc.), while `/query` responses are
  keyed by opaque indicator/filter IDs this service never had a mapping
  for - the actual blocker the old "documented TODO" comments described.
  Six new metric definitions added: `attainment8_average`,
  `progress8_average` (KS4/secondary), `ks2_rwm_expected_standard_percent`,
  `ks2_rwm_higher_standard_percent`, `ks2_reading_average_scaled_score`,
  `ks2_maths_average_scaled_score` (KS2/primary). DfE's "z"
  not-applicable marker (verified live: e.g. every school's
  `progress8_average` in the current 2024/25 release, and
  `average_scaled_score` for subjects with no scaled score) is handled
  distinctly from small-cohort suppression - never estimated, never
  shown as "suppressed" when it's really "not published this year".
  Imported for real against production: **208,406 metric rows across
  21,399 distinct schools**, verified both by direct SQL query and by
  loading real school pages live (URN 100000 correctly shows KS2 reading/
  maths/RWM figures; URN 100001 correctly shows a real Attainment 8 score
  alongside Progress 8 as "Not available", not "Suppressed"). Getting
  this to run against the real data volume surfaced two real bugs on the
  way: `cur.fetchall()` returns `dict_row` rows in this codebase
  (`row["urn"]`, not `row[0]`), and wrapping a ~98,000-row upsert in one
  transaction reliably hit a CockroachDB SERIALIZABLE retry error on
  COMMIT even with a same-shape whole-transaction retry wrapper (3
  attempts, exponential backoff) - fixed by committing and independently
  retrying per ~1000-row batch instead, safe since every write is an
  idempotent upsert. Also fixed `refresh-metrics`'s consistency check
  (validated `publications`' metric codes but not the new
  `performance_datasets`'s) and the full `run` pipeline's
  `import-performance` step (never propagated `--dry-run` to itself).

- **Northern Ireland removed from the project entirely, by explicit
  request.** It had been built and live (adapter, CLI command, scheduled
  workflow, 1,555 schools in production, `source_extract_date` staleness
  labelling throughout the UI) - see the git history around this entry
  for exactly what that looked like. Removed because its only source
  (Open Data NI's "School Locations" dataset) has been stale since
  February 2016 with no current extract available, and showing schools
  that may no longer be accurate isn't worth it just to say all four
  nations are covered. Concretely: all 1,555 `NORTHERN_IRELAND` school
  rows deleted from production (verified: 0 remaining, and verified no
  other table - `school_metrics`, `admission_arrangements`,
  `school_catchment_areas`, `school_relationships` - referenced any of
  them before deleting); `NORTHERN_IRELAND` dropped from the `Nation`
  enum via `ALTER TYPE "Nation" DROP VALUE` (only possible because no row
  referenced it anymore); `adapters/northern_ireland.py`,
  `import-northern-ireland`, its tests/fixture, and
  `ingest-northern-ireland.yml` all deleted; every "four nations" claim
  in the UI, README and this file updated to say three (England,
  Scotland, Wales) - the project's practical scope is now Great Britain,
  not the whole UK. `SCOTLAND_INGESTION_ENABLED` and
  `DEVOLVED_NATIONS_INGESTION_ENABLED` (which now only gates Wales) are
  untouched by this - neither was NI-specific.

- **`ingestion_runs` is written to for the first time in this project's
  history.** `pipeline.py` already had a complete, correct
  `create_ingestion_run`/`complete_ingestion_run` implementation - nothing
  in `cli.py` ever called it, so `/status`'s "recent ingestion runs" card
  had shown "No ingestion runs recorded yet" through every real import
  this project has ever run, including everything earlier in this
  session. Wired into `import-gias`, `import-trusts`, `import-scotland`,
  `import-wales`, `import-northern-ireland`, `import-catchments` (one row
  per local-authority/source-type combination). Verified against
  production: a real `import-scotland` run produced the first
  `ingestion_runs` row ever written, and it appeared on the live
  `/status` page immediately. Incidentally also fixes GIAS's
  checksum-skip logic, which could never find a prior run to compare
  against before now and was silently a no-op.

- **Catchment coverage now spans 5 local authorities across 2 nations
  (718 real catchment areas total), plus a longstanding bug fixed along
  the way.** Starting from Aberdeen City (Scotland's first candidate,
  previously rejected in `catchment-sources.yml` for being "outside
  GIAS/DfE scope"), Scotland turned out to have real, licensed,
  ArcGIS-hosted catchment data widely published across councils - a
  genuine surprise this session found by just checking: Aberdeen City
  (63 areas), City of Edinburgh (123, across four ND/RC layers), Glasgow
  City (254, across four ND/RC layers), Fife (151, across four
  ND/denominational layers), all OGL-licensed (Fife's own wording is "no
  conditions apply" rather than citing OGL by name - recorded as
  actually stated, not relabelled), all imported with zero new adapter
  code - the existing generic ArcGIS FeatureServer code, originally
  written for Sheffield, was never actually England-specific. Also
  researched and ruled out, with real evidence not guesses: Cardiff
  (Wales) only has an interactive address-lookup tool, no downloadable
  dataset, excluded by this project's own "what we deliberately do not
  use" rule; Northern Ireland's Department of Education confirmed it
  holds no catchment-area data centrally at all, each school sets its
  own enrolment criteria - a genuine dead end, not a research gap.

  Edinburgh, Glasgow and Fife all split catchments by denomination
  (non-denominational vs Roman Catholic/denominational), and those
  geographically _overlap_ (a household can sit inside both at once -
  denominational choice is separate from geographic catchment in
  Scotland). Importing them under the exact `primary_catchment`/
  `secondary_catchment` `source_type` the `/admissions` checker looks up
  would let it silently return whichever polygon matches first for a
  household in an overlap - a real wrong answer, not a theoretical one.
  Imported under suffixed source types instead (`_nd`/`_rc`/`_denom`):
  real, licensed data visible on `/map`, correctly excluded from
  `/admissions` until that feature can ask "which denomination" first.

  Fixed a real bug found while verifying this: nothing anywhere had ever
  set `local_authorities.catchment_coverage_status`, so Sheffield itself
  showed "Catchment data not available" on `/local-authorities` despite
  having 127 real catchment areas. `import-catchments` now sets it to
  `PILOT` after a successful import (upgrading only from the
  `NOT_AVAILABLE` default, never overwriting a status set some other
  way); verified live - all 5 local authorities now correctly show
  "Pilot catchment coverage".

  `/map`'s catchment overlay toggle is wired up for the first time
  (`/api/map/catchments` existed since the original build but nothing
  ever rendered it): a checkbox loads catchment polygons for the current
  viewport as a translucent fill + outline layer, verified live against
  Sheffield, Aberdeen City and Edinburgh (real school names visible in
  Edinburgh's popups, e.g. "Boroughmuir High School" - Edinburgh's
  layers carry the actual school name in `EST_NAME`, unlike Sheffield/
  Aberdeen's zone-name-only sources, making it a real future
  `SchoolCatchmentArea` candidate).

  Investigating the admissions-checker's `servedSchools` field (empty
  for every real match right now) confirmed `SchoolCatchmentArea`
  linking genuinely cannot be done by simple name-matching, settling an
  open question from earlier: Sheffield's real catchment features carry
  no name field at all (`"Unnamed catchment area 41"`), and Aberdeen's
  `NAME` field is a place/zone name ("Greenbrae", "Culter"), not a school
  name - there is no textual relationship to a school name in either
  real source. This is real per-source research work (which school
  serves which named zone), not a matching-algorithm problem.

- **Catchment coverage extended to 4 more Scottish councils**: North
  Lanarkshire (152 areas, four ND/denom layers), Highland (196, two
  layers - no separate RC layer found for this one, only a smaller,
  distinct Gaelic Medium category not imported), Dundee City (40, single
  service four layers), Perth and Kinross (86, four ND/RC layers). Every
  Scottish council checked so far (8 of 8) has had real, licensed
  catchment data - a genuinely consistent pattern, not luck on the first
  few. Total catchment coverage after this: **9 local authorities, 1,192
  real catchment areas**, verified against production.

  Also found, but could not verify live: Spatial Hub Scotland (run by the
  Improvement Service), a single national WFS aggregate covering all of
  Scotland's catchments in 4 layers with per-feature local-authority
  fields - would likely make most of the individual council entries
  redundant if reachable. Its `geo.spatialhub.scot` endpoint returned a
  403 "Access Denied" from this session's environment even with a browser
  User-Agent and Referer set, while the GeoServer admin UI on the same
  host loaded fine - a targeted restriction on the data workspace, not a
  general network block. Recorded in `catchment-sources.yml`'s candidates
  as worth retrying from a different network origin.

- **Catchment coverage extended to 3 more Scottish councils, and generic
  WFS ingestion support added.** North Ayrshire (62 areas, four layers)
  and South Ayrshire (79 areas, four layers - one feature correctly
  rejected for genuinely empty geometry) were both found via Spatial Hub
  Scotland's catalog and are ArcGIS-hosted, same as every council so far.
  Angus (67 areas, three layers) is the first source that is **not**
  ArcGIS - it is hosted on an XMap Cloud OGC WFS 2.0 server, which needed
  a new `query_all_wfs_features` pagination helper in `catchments.py`
  (mirrors the existing ArcGIS pagination but for WFS `GetFeature`
  `startIndex`/`count`) and a new `wfs_geojson` format value in
  `catchment-sources.yml`/`cli.py`. Every Scottish council checked so far
  (11 of 11) has had real, licensed catchment data. Total catchment
  coverage after this: **12 local authorities, 1,396 real catchment
  areas**, verified against production.

- **Systematically exhausted the Spatial Hub Scotland catalog (all 13
  individual-council entries checked) and added shapefile ingestion
  support.** Clackmannanshire (22 areas, four layers) is hosted on a
  Cadcorp WFS server that strictly requires the "typenames" (lowercase
  plural) query param rather than "typeName" - `query_all_wfs_features`
  was switched to send that name universally after confirming Angus's
  XMap Cloud server accepts it too, so one change fixed both.
  Aberdeenshire (180 areas, two layers - the largest single-council
  addition so far) and Orkney Islands (19 areas, one layer) are both
  zipped ESRI Shapefiles, not ArcGIS or WFS - the first shapefile_zip
  sources in this registry, needing a new `download_shapefile_zip_features`
  parser built on `pyshp` (a new, pure-Python, MIT-licensed dependency).
  Orkney's single layer mixes primary-only and combined primary/secondary
  school catchments per feature (some island schools serve both phases),
  so it is labelled `all_through_catchment` rather than
  `primary_catchment`/`secondary_catchment` - it displays on `/map` but
  is deliberately not reachable via the phase-specific `/admissions`
  checker, the same "don't imply more precision than the source has"
  principle used for the ND/RC denominational splits elsewhere. Every
  individual council in Spatial Hub Scotland's catalog (13 of 13) now has
  real, licensed catchment data - a genuinely consistent pattern across
  the whole catalog, not luck on a handful of councils. Total catchment
  coverage after this: **15 local authorities, 1,617 real catchment
  areas**, verified against production. The Spatial Hub national
  aggregate WFS (see the entry above) remains the only known Scottish
  catchment source that could not be reached from this session's
  environment; everything else the catalog lists has now been imported.

- **Renamed to catchment-zone; scope expanded from England-only to Great
  Britain.** GitHub repo, Vercel project/domain, npm workspace scope
  (`@catchment-zone/*`), and the Python package
  (`catchment_zone_ingestor`) are all renamed and live. Current, correct
  URLs: repo `https://github.com/ynot-tony1/catchment-zone`, production
  `https://catchment-zone.vercel.app` (verified: all 7 app routes return
  200 on the new domain post-rename; the old
  `schoolscope-england.vercel.app` domain still resolves too, since Vercel
  doesn't drop an old default alias on rename, so nothing broke in the
  transition). Schema gained a `Nation` enum (`ENGLAND`/`SCOTLAND`/`WALES`;
  `NORTHERN_IRELAND` was added and later removed, see the entry at the
  top of this file) on `School` and `LocalAuthority`, deployed via
  migration, with all 10,000 existing schools and 92 local authorities
  correctly backfilled to `ENGLAND` (verified by query, not assumed).

- **All three Great Britain nations are live in production, not just
  England.** Real adapters (`adapters/scotland.py`, `adapters/wales.py`),
  each live-verified against its actual source before being wired in,
  each a structurally distinct problem, not "GIAS again":
  - **Scotland** (`import-scotland`): the Scottish Government's
    ScottishSchoolRoll ArcGIS MapServer (`maps.gov.scot`). 2,483 schools,
    32 local authorities imported. Schools keyed by SchUID (not the bare
    SEED code, which two co-located schools can share), local authority
    codes are Scotland's own `S12000...` scheme (no collision risk with
    England's numeric codes). No open/closed status field in the source;
    every row is treated as OPEN, a stated limitation.
  - **Wales** (`import-wales`): DataMapWales's `maintained_schools_wg` WFS
    layer (`datamap.gov.wales`, GeoServer/OGC WFS 2.0). 1,440 schools, 22
    local authorities imported. Wales's own `la_code` values are small
    numbers in the same format as England's GIAS codes; this could not be
    definitively checked against a live GIAS extract at the time (GIAS was
    returning 500s/timeouts), so Wales's local authority codes are
    prefixed `W-` as a deliberate collision-safety measure. Same
    no-status-field limitation as Scotland.

  Total: **13,923 schools** across all three nations (10,000 England +
  2,483 Scotland + 1,440 Wales), verified by direct query against
  production, not just a CLI exit code.

  A `Nation` filter and column now runs through the whole web app, not
  just the database: `packages/shared`'s `SchoolSearchFiltersSchema` /
  `LocalAuthoritySearchFiltersSchema` gained a `nation` field, every page
  that lists or shows a school or local authority displays which nation
  it's from, and the map's default viewport was widened from an
  England-only bounding box to cover Great Britain. This work also
  caught a real bug: the URN search filter's regex only accepted digits,
  which would have silently rejected every Scotland (`8212627P`) school
  lookup by id - fixed to accept alphanumeric.

  Scheduled GitHub Actions workflows exist for both (`ingest-scotland.yml`,
  `ingest-wales.yml`, mirroring `ingest-gias.yml`'s shape), and each was
  test-triggered for real via `workflow_dispatch` before being trusted:
  Wales succeeded from GitHub Actions' own IP ranges and is enabled on
  schedule (`DEVOLVED_NATIONS_INGESTION_ENABLED=true`, weekly). Scotland's
  `maps.gov.scot` returned a 403 from GitHub Actions - the same
  Azure-datacenter-IP block GIAS hits - confirmed live, not assumed; it
  has its own gate (`SCOTLAND_INGESTION_ENABLED=false`) so that one
  nation's WAF doesn't hold back the one that genuinely works.

- **Pilot data import ran for real against production** (task from the
  previous "Exact next steps"). `scripts/calibration-report.md` is filled in
  with real measured numbers, not a template. Result: 10,000 schools, 92
  local authorities, 7,176 academy trusts (the full national trust
  register — no row limit was used for trusts), and 127 Sheffield catchment
  areas (101 primary + 26 secondary, LA code 373), all persisted and
  verified by direct query against `aqua-roach`/`school_intelligence`, not
  just a successful CLI exit code. Catchment re-import confirmed idempotent
  (same ids, same row counts on a second run).

  GIAS's live site had changed substantially since the original adapter was
  written, and none of this worked on the first attempt. Real bugs found and
  fixed, each only surfaced by running against the real, live GIAS site and
  the real production database, not caught by any test:
  1. GIAS's WAF 403s non-browser User-Agents; fixed with a real browser UA
     applied only to GIAS requests.
  2. GIAS's downloads page was completely redesigned: no more `<a href>`
     download links, replaced by a stateful ASP.NET collate-then-poll flow
     (`POST /Downloads/Collate` -> poll `/Downloads/GenerateAjax/<uuid>` ->
     `POST /Downloads/Download/Extract`). Fully reverse-engineered and
     reimplemented against the live site.
  3. The download is a ZIP, not a raw CSV, and the CSV inside is not
     consistently UTF-8 (real school names contain Windows-1252 characters).
     Fixed with ZIP unwrapping and a utf-8-sig-then-cp1252 fallback decode.
  4. `upsert_batch` never set `updated_at`, which has no SQL-level DEFAULT
     (Prisma's `@updatedAt` is normally set client-side by Prisma Client, a
     raw SQL write bypasses that entirely) — every first insert into an
     affected table failed NOT NULL. Fixed centrally in `db.py`.
  5. `local_authorities` had no import path at all despite `schools` having a
     foreign key to it; nothing had ever populated it. Fixed by deriving
     distinct (code, name) pairs from the GIAS establishment extract itself
     and upserting them before schools, in the same transaction.
  6. `catchment_sources.id` and `catchment_areas.id` use Prisma's
     `@default(uuid())`, also client-side-only, not a SQL DEFAULT — every
     insert failed NOT NULL on `id`. Fixed by minting ids in the ingestor,
     reusing an existing source's id on re-import so already-written
     `catchment_areas` rows are never orphaned.
  7. Separately, and worse: `import-catchments` built `CatchmentArea`
     polygons in memory and reported a count, but never actually wrote them
     to the database — only the `catchment_sources` summary row was
     persisted. There was also no unique constraint backing either the
     `catchment_sources` or `catchment_areas` upsert's `ON CONFLICT` clause,
     so even after the id fix, both upserts failed with "no unique or
     exclusion constraint matching". Fixed by adding two production
     migrations (`(source_id, geometry_checksum)` unique index on
     `catchment_areas`, `(local_authority_code, academic_year, source_type)`
     unique index on `catchment_sources`), deployed through the existing
     reviewed, manually-confirmed `migrate-production.yml` workflow, then
     wiring the built areas into the same transaction as the source row.
  8. GIAS also blocks requests from Azure datacenter IP ranges (which
     includes GitHub Actions runners) independently of the User-Agent fix —
     confirmed by direct testing from multiple network origins. This means
     the scheduled/automated `ingest-gias.yml` workflow cannot reach GIAS
     from GitHub Actions as currently designed. Explicitly deferred by
     request; the pilot import above was run manually instead, from a
     non-Azure network origin, using a rotated, narrowly-scoped
     `school_ingestor` credential (`scripts/rotate-ingest-credential.sh`,
     new this session, mirrors the existing bootstrap script's pattern).

  `services/ingestor` test suite grew from 45 to 66 tests covering all of
  the above (GIAS downloads-page parsing, ZIP/encoding handling, local
  authority derivation, `upsert_batch`'s `updated_at`/`now()` SQL, and
  catchment source id resolution/reuse), all passing alongside `ruff check
.` and `mypy src`.

  **Known gap, not fixed this session:** `import-statistics` only resolves
  the current DfE publication release, it does not fetch or write any
  `SchoolMetric` rows (a pre-existing, explicitly documented TODO, not
  something broken by the above). Worse, live investigation found the two
  DfE publications that currently resolve at all
  (`pupil-absence-in-schools-in-england`, `pupil-attendance-in-schools`)
  only expose Local authority/Regional/National-level data via the EES API,
  never per-school rows, so `SchoolMetric` (which requires a non-null
  `school_urn`) cannot be populated from either as currently designed. The
  other two configured publications (`school-capacity`,
  `school-workforce-in-england`) don't exist in the EES API's public
  catalogue at all right now. See `scripts/calibration-report.md`'s "What
  actually ran" section for detail. No `SchoolMetric` rows exist in
  production.

- **Pushed to GitHub**: `https://github.com/ynot-tony1/schoolscope-england`
  (public). CI is green on `main`
  (`https://github.com/ynot-tony1/schoolscope-england/actions/runs/30715283514`):
  Ingestor (ruff, mypy, pytest, docker build), Secret scan, Web (lint,
  typecheck, unit tests, build) all passed for real, on GitHub's own
  runners, not just locally. Fixed two real CI bugs to get there: the
  `gitleaks-action` push-diff mode fails on a repository's first push
  (replaced with a direct `gitleaks detect` full-history scan), and
  `prettier --check` had never actually passed since the initial commit
  (ran `prettier --write` for the first time, added `.prettierignore` for
  the lockfile/generated output/a test fixture).
- **Production deployment is live and verified end-to-end**:
  `https://schoolscope-england.vercel.app`. `/status` reports database
  connectivity as Reachable and shows the deployed git SHA; every route
  (`/`, `/schools`, `/schools/[urn]`, `/trusts`, `/local-authorities`,
  `/admissions`, `/map`, `/about/data`) returns 200; `/api/schools`,
  `/api/trusts`, `/api/local-authorities` return valid (currently empty,
  since no data is imported yet) JSON; `POST /api/admissions/check`
  performs a real `postcodes.io` lookup and returns the correct mandatory
  disclaimer text and an honest `OFFICIAL_BOUNDARY_NOT_AVAILABLE` status
  rather than fabricating an answer.

  Getting there took six distinct, real bugs, each found by reading the
  actual deployed function logs after a failed request, not guessed in
  advance:
  1. `vercel link` run from `apps/web` left the project's Root Directory
     setting at `.` (repo root), which only works for ad-hoc CLI deploys
     from that directory, not GitHub-integration builds, which check out
     the full repo. Confirmed concretely via a manual `vercel deploy
--prod` from `apps/web`, which failed `npm install` (no pnpm
     workspace context in a bare subdirectory). Fixed via `vercel api
/v9/projects/... -X PATCH -F rootDirectory=apps/web` (the CLI has no
     dedicated command for this setting).
  2. `packages/database` had no `postinstall`/`prepare` script, so the
     Prisma client was never generated on Vercel (it was always generated
     manually, locally and in CI). Fixed with `postinstall: prisma
generate`.
  3. That fix alone was not enough: Vercel's second deployment restored a
     build cache, pnpm saw the lockfile unchanged and skipped install
     entirely, and the generated client (gitignored source-tree output,
     not part of `node_modules`) was not preserved by that cache. Same
     problem existed for `packages/shared`'s config-sync `prepare` hook.
     Fixed by adding a `prebuild` script to `apps/web` that always
     regenerates both, since pnpm always runs `prebuild` as part of `pnpm
run build`, the exact command Vercel invokes, regardless of whether
     install was skipped.
  4. The deployed function then failed at runtime with "Prisma Client
     could not locate the Query Engine for runtime rhel-openssl-3.0.x".
     Root cause, found by tracing through several dead ends (Turbopack vs
     webpack made no difference; `outputFileTracingRoot` alone did not
     help): the custom `output = "../generated"` path in `schema.prisma`
     placed the client in a monorepo-sibling directory outside
     `node_modules`, which is not Prisma's well-tested, officially
     supported deployment shape. Removed the custom output path entirely;
     `packages/database` now re-exports `@prisma/client` directly through
     a thin `index.js`/`index.d.ts`.
  5. Even on Prisma's default path, the query engine binary lives in a
     dot-prefixed sibling package (`.prisma/client`) several symlink hops
     deep inside pnpm's nested `node_modules/.pnpm/<hash>/node_modules`
     structure, which Vercel's function tracer does not follow on its
     own. Found the real file by searching the pnpm store directly rather
     than guessing further, then added a targeted `outputFileTracingIncludes`
     glob pointed at that exact verified location. This is what actually
     fixed the engine-loading error.
  6. With the engine loading correctly, the next real error was a SQL
     permission error: `user school_app does not have SELECT privilege on
relation schools`. Cause: `ALTER DEFAULT PRIVILEGES`, set once by the
     admin bootstrap role, only applies to objects created by that same
     role; the migration creates tables as `school_migrator`, so those
     defaults never took effect. Fixed by extending the
     `migrate-production.yml` post-deploy grant step to re-grant
     `school_ingestor` and `school_app` privileges on every table, using
     the least-privilege `school_migrator` credential, every run.

- **`aqua-roach` bootstrapped and migrated for real.**
  `scripts/bootstrap-cockroachdb.sh` was run against the live cluster:
  `school_intelligence` created, three least-privilege users created
  (`school_migrator`, `school_ingestor`, `school_app`) with the grants
  from `docs/database.md`, `MIGRATION_DATABASE_URL`/
  `INGEST_DATABASE_URL` written to GitHub secrets, `DATABASE_URL` written
  to Vercel (Production and Preview). Found and fixed two real bugs in
  the script in the process: `CREATE USER IF NOT EXISTS` silently skips
  the password clause on an already-existing user, breaking re-runs
  (fixed with an unconditional `ALTER USER ... WITH PASSWORD` after); and
  the Vercel commands ran from the repo root instead of `apps/web`, where
  the actual project link lives (fixed with `--cwd`).

  The `migrate-production` workflow then took several real attempts to
  get right, each a genuine bug caught by actually running it against
  production, not something guessed in advance:
  1. `prisma migrate status` exits 1 whenever migrations are pending,
     which is the normal state before every deploy; the workflow treated
     that as a hard failure and never reached the deploy step.
  2. CockroachDB Cloud creates new tables with `schema_locked = true` by
     default (a changefeed-performance feature this project does not
     use), which blocks the `ADD CONSTRAINT` foreign-key statements
     Prisma generates afterward.
  3. The first fix attempt (`ALTER TABLE ... SET (schema_locked =
false)` right before the foreign keys) still failed intermittently:
     that ALTER triggers an async CockroachDB schema-change job, and
     Prisma's engine does not wait for it to finish before sending the
     next statement, unlike `psql`. Fixed properly by setting
     `schema_locked = false` directly in each `CREATE TABLE ... WITH
(...)` statement, so the table is never locked in the first place.
  4. Recovering from the partially-applied migration needed a temporary,
     explicitly-confirmed reset workflow (dropped the 12 tables, then
     separately the 5 enum types, since `DROP TABLE` does not cascade to
     types a column used, and CockroachDB does not implement `DROP TYPE
... CASCADE` at all). Deleted once no longer needed.
     Verified independently afterward via read-only queries: 13 tables
     (12 plus `_prisma_migrations`), both foreign keys on `schools` present,
     all indexes present, migration tracking row shows a clean success. The
     `postcode_cache` grant to `school_app` that the bootstrap script had to
     defer (the table did not exist yet) now runs as a permanent step in
     `migrate-production.yml` after every deploy, using the least-privilege
     `school_migrator` credential, not the admin one.

  Every one of the diagnostic/recovery steps above ran through GitHub
  Actions using the already-stored `MIGRATION_DATABASE_URL` secret; the
  real database credentials were never read, held, or handled directly
  in this session, only ever passed through as opaque secret references.

- **Monorepo baseline is green.** `pnpm install`, `pnpm -r typecheck`,
  `pnpm -r lint`, `pnpm -r test`, and a real
  `pnpm --filter @catchment-zone/web build` (Next.js production build, fake
  local `DATABASE_URL` so Prisma can generate its client) all pass. Test
  counts: `packages/shared` 39, `apps/web` 29, `services/ingestor` 45.
- **Every app route from the original spec now exists and is wired to the
  database** (degrading gracefully via `safeQuery` when unreachable, never
  a 500 page):
  - `/` home dashboard (live counts, ISR hourly).
  - `/schools` search (name/postcode/status filters, keyset pagination,
    distance-from-point sort) and `/schools/[urn]` detail (address, trust,
    local authority, de-duplicated latest-per-metric performance table).
  - `/trusts` and `/trusts/[id]`.
  - `/local-authorities` and `/local-authorities/[code]` (admissions
    links, catchment source list, schools in that authority).
  - `/admissions`: postcode + phase catchment check, calling
    `/api/admissions/check`, rendering the mandatory disclaimer text
    verbatim and, when applicable, the near-boundary warning. The status
    vocabulary and copy were written to only ever use the six allowed
    `CatchmentCheckStatus` values, matching the forbidden-word test
    already in `packages/shared`.
  - `/map`: MapLibre view, schools loaded live for the current viewport
    via `/api/map/schools`; `/api/map/catchments` also exists for
    boundary overlays once catchment data exists.
  - `/about/data`, `/status` (DB connectivity, git SHA, last 10 ingestion
    runs).
  - API routes: `/api/schools`, `/api/trusts`, `/api/local-authorities`,
    `/api/admissions/check` (rate-limited via the existing
    `lib/rate-limit.ts`), `/api/map/schools`, `/api/map/catchments`. All
    Node runtime, all using the shared safe-error-envelope helpers.
- **Query layer** (`apps/web/lib/queries/`): `schools.ts`, `trusts.ts`,
  `local-authorities.ts`, `catchments.ts`. Catchment checking does a
  bounding-box prefilter then exact point-in-polygon via the existing
  `lib/geo.ts` Turf helpers, distinguishes
  `OFFICIAL_BOUNDARY_NOT_AVAILABLE` from `ACADEMIC_YEAR_NOT_AVAILABLE`
  using the existing `packages/shared` catchment-source-registry helpers,
  and flags `POSTCODE_RESULT_NEAR_BOUNDARY` using the configured warning
  distance, matching the spec's admissions-safety rules.
- **Toolchain compatibility fixes** made while establishing the baseline
  (see git history for detail): TypeScript pinned to `~6.0.3` in
  `apps/web`/`packages/shared` (TS 7 not yet supported by
  `typescript-eslint`); `apps/web` ESLint rewritten onto
  `eslint-config-next`'s native flat-config exports and pinned to
  `~9.39.5` (ESLint 10 breaks `eslint-plugin-react`); `next.config.ts`'s
  removed `eslint.dirs` option (Next.js 16 dropped built-in ESLint
  integration); a zod v4 tuple-pipe type error in
  `packages/shared/src/schemas/common.ts`; a Turf `MultiPolygon` handling
  bug in `apps/web/lib/geo.ts`; and a real `.gitignore` bug that left the
  generated Prisma client, including a native binary, untracked but
  unignored (actual `output` path is `packages/database/generated`, not
  `packages/database/prisma/generated`).
- **`services/ingestor/Dockerfile` verified end-to-end**: `docker build`
  succeeds, and `docker run schoolscope-ingestor:local --help` shows the
  expected CLI (`discover-gias`, `import-gias`, `import-trusts`,
  `import-scotland`, `import-wales`, `import-northern-ireland`,
  `import-statistics`, `import-catchments`, `import-admissions`,
  `refresh-metrics`, `verify`, `cleanup`, `run`). The local test image was
  removed after verification; nothing was pushed anywhere.
- **`services/ingestor`** full check suite still passes: `ruff check .`,
  `mypy src` (15 files), `pytest -q` (76 tests).

## Unfinished

- **England and Wales now have real performance metrics; Scotland has
  none, and confirmed not to have a viable public source right now** (see
  "Completed and verified" above for both). Scotland's position could
  change if the Improvement Service's Insight tool, or an equivalent, is
  ever opened up as public data - worth rechecking periodically rather
  than assumed permanently closed. The original LA-level EES publications
  (school-capacity, pupil-absence x2, school-workforce) are still unusable
  for `SchoolMetric` as designed (no per-school rows) and remain
  resolved-but-not-imported by `import-statistics`; a schema change (e.g.
  a local-authority-level metrics table) would be needed to use them at
  all, and has not been attempted.
- **Catchment area performance scoring covers Sheffield and Powys's
  secondary catchments (135 of 2,122 areas) right now** - not a bug, a
  direct consequence of current catchment coverage: Scotland has no
  performance metrics at all, so none of its 19 councils' catchments
  score, even though catchment coverage there is now the largest part
  of the dataset. As catchment coverage or performance-metric coverage
  grows, re-running `refresh-catchment-scores` will pick up
  newly-scorable areas automatically with no code change needed - it
  was written generically against the nation/phase metric-candidate
  table, not hardcoded to any one council.
- **`SchoolCatchmentArea` (linking a catchment polygon to the school it
  covers) is entirely unimplemented, and confirmed not solvable by name-
  matching for most sources.** Sheffield's features carry no name at all;
  Aberdeen's `NAME` field is a place/zone name with no textual
  relationship to any school name. Edinburgh's is the one real exception
  found so far: its `EST_NAME` field carries the actual school name
  (verified live, e.g. "Abbeyhill Primary School"), a genuine candidate
  for this if pursued. Until this exists generally, a matched catchment
  on `/admissions` correctly shows the area name but an empty
  served-schools list - degraded, not wrong.
- **Catchment coverage is 21 local authorities out of ~200+ across Great
  Britain** (Sheffield/England; Aberdeen City, City of Edinburgh, Glasgow
  City, Fife, North Lanarkshire, Highland, Dundee City, Perth and
  Kinross, North Ayrshire, South Ayrshire, Angus, Clackmannanshire,
  Aberdeenshire, Orkney Islands, Stirling, Argyll and Bute, Moray,
  Dumfries and Galloway, Renfrewshire, East Renfrewshire/Scotland;
  Powys, Pembrokeshire/Wales) - but every one of Scotland's 32 councils
  and every one of Wales's 22 councils has now been individually
  investigated, not just the ones that yielded real data, so this is
  close to as complete as this project can currently make it without
  new data being published. Spatial Hub Scotland's original catalog
  (13 of 13) is fully exhausted; 6 further Scottish councils were found
  individually via ArcGIS Online item-metadata verification instead
  (Stirling, Argyll and Bute, Moray, Dumfries and Galloway,
  Renfrewshire, East Renfrewshire). Real data with no usable licence
  evidence was found for 3 more (Midlothian, West Lothian, South
  Lanarkshire) and real, well-licensed data for one more was blocked by
  the council's own server having an expired TLS certificate (East
  Dunbartonshire) - all documented as `candidates:` entries in
  `catchment-sources.yml` rather than silently dropped, so they can be
  revisited without a fresh search. West Dunbartonshire has real data
  under an explicitly redistribution-prohibiting Ordnance Survey
  licence and is deliberately excluded. Falkirk, Scottish Borders, East
  Ayrshire, Inverclyde, East Lothian, Na h-Eileanan an Iar and Shetland
  Islands are confirmed genuine dead ends (PDF/text/proprietary-viewer
  only, or a platform-level access block) - every one of Scotland's 32
  councils is now accounted for, either with real imported data or a
  documented reason it does not have any. A genuine national aggregate
  (Spatial Hub Scotland / Improvement Service, covering all of Scotland
  in one WFS with per-feature local-authority fields) was found but
  could not be reached from this session's environment (403, see the
  `catchment-sources.yml` candidate entry) - worth retrying from a
  different network origin, though it would now mostly be a
  consolidation rather than unlocking new coverage. Wales now has two
  real sources (Powys, Pembrokeshire); every one of the other 20 Welsh
  councils was individually checked this session and found to have only
  interactive address-lookup tools or PDF maps, a genuine structural
  gap rather than a search gap. Both nations are now at a natural
  stopping point for this technique - further coverage would mean
  either new data being published by a currently-empty council, the
  Improvement Service aggregate becoming reachable, or East
  Dunbartonshire's certificate being fixed, not more searching.
- **Denominational (ND/RC) catchment splits (Edinburgh, Glasgow, Fife,
  North Lanarkshire, Dundee, Perth and Kinross) are map-overlay-only, not
  reachable via `/admissions`.** See "Completed and verified" above for
  why (geographic overlap between denominations). The checker would need
  to ask "which denomination" before this can extend to Scotland's
  `/admissions` results; not attempted.
- **Playwright end-to-end tests do not exist yet** (`playwright.config.ts`
  is present but there is no `tests/e2e/` content). Not attempted this
  session; would need a running app and, for full coverage, real data.

## Completed and verified: frontend polish pass, including the map

Screenshotted the live production site (light and dark mode, every major
page) with an ad-hoc Playwright script to find real issues rather than
guessing from code. Found and fixed:

- **Production `/map` was rendering as a blank rectangle with zero
  basemap detail (no coastlines, roads, labels) the entire time this
  project has been live.** Root cause: `NEXT_PUBLIC_MAP_STYLE_URL` was
  never actually set in Vercel, so the app silently fell back to its own
  hardcoded default of MapLibre's own `demotiles.maplibre.org` style - an
  intentionally bare demo style (country-level shapes only), not a real
  basemap. Fixed by switching the default (and Vercel Production/Preview
  env vars, and both `.env.example`/`.env.local` templates) to
  OpenFreeMap (`tiles.openfreemap.org/styles/liberty`) - free, no API
  key, no rate limit. Verified live in production after deploy: real
  terrain shading, coastlines, and correct GB geography now render.
- **`searchSchools`/`searchTrusts`/`searchLocalAuthorities` all compute a
  real `nextCursor`, but no page ever rendered a "next page" control** -
  a genuine functional gap, not cosmetic, since the default page size
  means results beyond the first page were unreachable. Added
  `trustFiltersToSearchParams`/`localAuthorityFiltersToSearchParams`
  (mirroring the existing `schoolFiltersToSearchParams`) and wired a
  "Next page" link into all three search pages.
- The `/map` catchment-areas checkbox still hardcoded "Sheffield,
  Aberdeen City pilots only" as its label, stale since coverage grew to
  12 local authorities; reworded to "where published".

## Known failing tests

None. Every test suite that was run passed: `packages/shared` (45),
`apps/web` (29), `services/ingestor` (100).

## Exact next steps, in order

1. Wales performance metrics are done and Scotland has been investigated
   and closed (no viable public source right now, see "Completed and
   verified" above) - periodically recheck Scotland in case Insight or an
   equivalent ever becomes public.
2. Spatial Hub Scotland's catalog is now exhausted (13 of 13 individual
   councils imported); its national aggregate WFS is still worth trying
   again from a different network origin (403 from this session's
   environment) mainly as a consolidation/cross-check, not to unlock new
   coverage. Further Scottish expansion means checking councils
   individually outside that catalog (not yet attempted, no discovery
   mechanism established for it yet). Separately, check more Welsh
   councils beyond Cardiff (ruled out) - Wales now has real performance
   metrics but zero catchment sources, so adding even one Welsh
   catchment source would immediately extend the map's colour-grading
   feature there too, not just add coverage.
3. Get explicit go-ahead, informed by `scripts/calibration-report.md`,
   before further catchment-geometry expansion at scale (that report
   predates both the full-national GIAS import and the performance-
   metrics addition, so its storage projections should be re-checked
   against real current console figures rather than assumed still
   accurate). The report's own recommendation: national schools/trusts/
   local-authorities data (now including performance metrics) looks
   cheap; catchment geometry is the dominant storage cost and should be
   rolled out one local authority at a time with real console figures
   checked after each addition, not assumed to scale linearly from the
   single Sheffield sample.
4. Optional polish: `SchoolCatchmentArea` per-source research (see
   "Unfinished" above - Edinburgh's `EST_NAME` field is the most
   promising real starting point), a denomination-aware `/admissions`
   flow for Scotland's ND/RC catchment splits, Playwright e2e coverage
   for the golden paths (search a school, check a postcode, view the map
   with the catchment overlay on). A `/schools` search-results column or
   filter for a headline performance metric would also make the new
   data more discoverable than only showing on each school's own page.
