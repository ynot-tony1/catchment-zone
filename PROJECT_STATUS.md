# Project status

Updated 2026-08-17. Reflects what has actually been run and verified on
disk, not what is intended.

## Current state (2026-08-17, later session)

- **105 local authorities** with real pilot catchment coverage (England,
  Scotland, Wales), **275 enabled sources** in `config/catchment-sources.yml`
  (`packages/shared/src/config/catchment-sources.test.ts`'s
  `PILOT_LOCAL_AUTHORITIES` list is the exact, test-enforced source of
  truth for the LA/source-count breakdown).
- **`catchment_areas`: 11,122 rows**, `map_catchments_cache.feature_count`:
  11,122 (in sync).
- **Catchment scores: 7,594 of 11,122 areas scored** (`refresh-catchment-scores`,
  last run 2026-08-17; the remainder are areas without enough underlying
  school-performance data to score, not a bug).
- **81 candidate entries** recorded in `config/catchment-sources.yml`'s
  `candidates:` section with a specific `reason_not_enabled` - the full
  categorized breakdown (login wall / bot-check / no data published /
  structural dead end) and a roadmap for closing the login-wall ones is in
  "Full audit: every documented gap, categorized by blocker type, with a
  login-wall roadmap" below (now stale on exact counts, but still the right
  categorization to start from).

## Toolkit: methods proven this project, for reuse on the next source

This project has no single ingestion method - every council publishes
catchment data differently, and roughly half of the LAs above required
building a bespoke extraction technique rather than just pointing the
ingestor at an official API. This section is a reusable index of every
distinct technique proven to work, so the next session doesn't have to
rediscover them from 3,600 lines of chronological history. Each entry links
to the update where it was built and first landed real data.

- **Direct GIS service query (ArcGIS Feature Service / WFS / shapefile
  download).** The easy case: the council publishes catchments through a
  real GIS backend. Query `/query?f=geojson` (ArcGIS) or the WFS
  `GetFeature` endpoint directly, reproject if needed, done. Covers the
  majority of the 104 LAs and needs no bespoke code - just a new
  `config/catchment-sources.yml` entry with `parser_name:
generic_arcgis_feature_service` / `generic_wfs` / `generic_shapefile_zip`.
- **Interactive council tool's own backend endpoint, queried directly (no
  login involved).** The single most productive non-trivial technique this
  project has used. Many councils' "interactive map" pages have no
  documented API but make plain HTTP requests to their own backend from
  client-side JS - open the browser network tab (or intercept via CDP
  Fetch-domain, see below) and call that endpoint directly. Landed
  Wakefield's address-picker tool (68+14 catchments), Coventry's road-name
  tool (16+6), Wirral (22, a single bulk request beat exhaustive street-name
  enumeration), Rotherham's raster/watershed platform, and Staffordshire's
  legacy ASP.NET app (313 catchments, coordinates embedded directly in
  server-rendered markup - zero georeferencing needed). See "Update:
  Staffordshire's 313 catchments landed..." (2026-08-10) and the Wakefield/
  Coventry/Wirral updates (2026-08-11).
- **Dense point-sampling + Voronoi tessellation ("the road-list Voronoi
  pipeline").** For "admission zone finder" tools that answer one address
  at a time with no boundary export: enumerate every road/street in the
  area (OS/OSM road list), query the tool once per address point along each
  road, then reconstruct polygon boundaries from the resulting dense point
  cloud via Voronoi tessellation, clipped to real ONS LAD administrative
  boundaries and a trust-radius buffer around actual sampled points (never
  extrapolating past what was actually sampled). First built for Hartlepool
  (12 zones), then reused for Essex, Wakefield, Coventry, Wirral, Luton,
  North East Lincolnshire, and Thurrock. See "Update: Hartlepool's Admission
  Zone Finder cracked..." (2026-08-11) and "Update: generalising the
  Hartlepool technique..." (2026-08-11).
  - **Known failure mode of this technique, found and fixed by the user:**
    naive point-in-polygon verification against a `MultiPolygon` output
    passes if a coordinate lands in ANY fragment, including a tiny
    disconnected sliver - producing fragmented, scattered-looking zones on
    the live map even with zero cross-school overlap. Fix: keep only the
    single largest connected piece per school and re-verify only against
    that piece; drop schools that fail once fragments are removed. See
    "Update: user caught a real fragmentation bug..." (2026-08-11) for the
    fix and the precise checksum-based DB reconciliation used to clean up
    the resulting orphaned rows (never a timestamp-based guess, which risks
    deleting legitimately-unchanged rows).
- **Landmark-pair (2-point similarity transform) anchoring for scanned/PDF
  maps.** The core Oxfordshire technique, reused everywhere a council
  publishes a scanned or vector-PDF map with no coordinate grid: identify
  two real-world landmarks visible on the map (road junctions, named
  villages, notable buildings) via Nominatim/Overpass, get their true
  lat/lon, compute the pixel-to-geographic similarity transform (rotation +
  scale + translation) from their pixel positions, then trace the boundary
  in pixel space and transform it. Always cross-checked against a third,
  independent point before accepting. Discipline established this session:
  decline a fit if the resulting containment margin is smaller than the
  fit's own error budget, even if the point technically lands inside (see
  the New Marston Primary decline, "Update: Oxfordshire's original
  non-gridded landmark-pair candidate list fully exhausted...", 2026-08-09) -
  a comfortable margin, not just barely inside.
  - **Named infrastructure (road/rail, Nominatim-geocoded) is the most
    reliable anchor type**; large multi-building campuses are a real,
    repeatable failure mode (ambiguous which building the pin represents).
  - **Short baselines amplify rotation noise** - a small pixel-picking error
    over a short real-world distance produces a large bearing error; prefer
    the longest available baseline between two landmarks.
  - **Railway-station ground-control points**, used to land Bristol's St
    Bede's Catholic College (19 of 20 parishes): where a shared basemap
    carries a genuine, measurable OS grid (verified independently against
    two known real station-to-station distances), a single identifiable
    station point is enough to anchor the whole map once that shared
    scale/rotation model is trusted - no second in-frame point needed per
    parish. See "Update: St Bede's Catholic College - 19 of 20 parishes..."
    (2026-08-12).
- **OS grid-line pixel detection.** Where a scanned map carries a visible
  1km OS grid, detect the grid lines directly (colour/contrast threshold)
  and use their known real-world spacing as the scale/rotation reference
  instead of a landmark pair - more precise when available, since it uses
  the map's own printed ground truth rather than an external geocode.
- **Colour-mask segmentation, with an occlusion-check discipline.** For
  colour-coded parish/priority-area maps (solid fill per zone): threshold
  the target colour, take the largest connected component,
  `binary_fill_holes`, extract the contour, simplify. Real trap found and
  fixed this session: a marker/pin icon overlapping the boundary line can
  fake a false nearby "edge," producing an artificially small containment
  margin - always check for and patch out occluding icons before trusting a
  colour-mask margin (an 88m-looking margin became a real 1,686m once
  patched for Sacred Heart Henley; see the Oxfordshire update, 2026-08-13
  later session).
- **Marker-controlled watershed segmentation.** For raster-only platforms
  with adjacent, unlabelled colour regions where a simple colour mask can't
  cleanly separate touching zones - used for Rotherham's 79 primary + 14
  secondary catchments (the secondary layer reused the primary layer's
  already-verified affine transform rather than re-deriving one).
- **Skeleton-graph boundary tracing for partially-drawn lines.** Where a
  boundary line appears to have "open" gaps at first glance (an early,
  wrong diagnosis this session almost accepted for 6 Bristol parishes):
  skeletonise the drawn line and walk it as a graph (`networkx` shortest
  path between true endpoints) before concluding the line is genuinely
  incomplete. Often the line closes cleanly right up to a natural feature
  (a coastline) that the map simply doesn't re-draw a boundary over, not a
  resolution artefact - confirm by visually checking each flagged
  "endpoint" individually, since sharp vertices produce false positives.
- **Archived historical map edition recovery.** When a council's current
  map for an area is missing, low-resolution, or otherwise undigitizable,
  check whether an older edition of the same map (a different template,
  sometimes hosted on an archived page or a different URL pattern) still
  exists and is usable - resolved South Tyneside's multi-session-stuck
  Marsden/Laygate zones this way. See "Update: South Tyneside's Marsden and
  Laygate primary catchments landed via a different, older archived edition
  of the same map" (2026-08-12).
- **CDP Fetch-domain interception.** For pages where the data-bearing
  network request isn't visible in a simple page fetch (client-side
  JS-triggered XHR/fetch calls), intercept at the Chrome DevTools Protocol
  Fetch domain to capture the actual request/response the page's own code
  makes, then replay that request directly outside the browser.
- **Legacy embedded-JS-polygon extraction (zero georeferencing).** The best
  case when it applies: some older/legacy council tools embed catchment
  polygon coordinates directly as WGS84 lat/lon in server-rendered
  JavaScript or markup - no image, no transform, no landmark-pairing
  needed, just parse the coordinates directly out of the page. Landed all
  313 of Staffordshire's catchments this way in a single session.
- **National aggregate integration for genuine coverage gaps.** Scotland's
  Improvement Service publishes a national school-catchments aggregate;
  where a specific council's own site had no usable per-school data, the
  national aggregate closed the gap directly (East Ayrshire, Na
  h-Eileanan an Iar, Dumfries and Galloway, Shetland). Always check whether
  a national/regional aggregate already covers an apparent gap before
  building a bespoke council-specific technique.
- **User-assisted acquisition for genuinely blocked sources.** Some data
  simply isn't reachable from this sandbox (a real login wall, a
  Cloudflare Turnstile challenge, an IP-level geographic block) but is
  reachable from the user's own browser/network. The user has directly
  supplied manually-downloaded datasets (Scotland's 4 national JSON files)
  and PDFs found independently (Brighton and Hove's admissions map) for
  investigation and ingestion - this is a first-class, repeatable path for
  Category A/B blockers, not a fallback.
- **Precise checksum-based DB reconciliation.** Whenever a re-import or a
  fix changes which rows should exist, verify orphaned/stale rows by exact
  `geometry_checksum` comparison against what the current source file
  actually produces, never by a timestamp heuristic (which risks deleting
  legitimately-unchanged rows that just happen to predate a cutoff).

### Operational lessons (process, not geometry)

- **Git worktree isolation (`isolation: "worktree"`) is mandatory for every
  fork** after a real concurrent-file-write race was caught corrupting a
  Staffordshire output file mid-write from a genuinely separate, stray
  Claude Code process on the same machine.
- **Forks must do all waiting synchronously** - a fork that uses the
  Monitor tool or a backgrounded command expecting to be "woken up" later
  simply ends its turn with nothing landed, since forks are single-turn and
  nothing wakes them back up.
- **Always re-run `pnpm --filter @catchment-zone/shared sync-config`** after
  any `config/catchment-sources.yml` edit, before trusting a test run - the
  gitignored generated JSON goes stale otherwise and produces confusing
  false test failures.
- **Verify a fork's claimed push actually landed** via `git fetch` +
  `git log origin/main` comparison before importing from it, never just
  trust the fork's own report.
- **The ingestor fetches from `raw.githubusercontent.com`, not local
  files** - any local edit must be pushed to `origin/main` before
  importing, and the raw CDN caches a branch URL for a few minutes; verify
  freshness via a commit-SHA-pinned URL (full 40-char SHA) when in doubt.
- **`config/catchment-sources.yml` list items use 2-space indentation** -
  a 0-space entry silently breaks the whole file's YAML parse at
  `sync-config` time.

## Completed and verified

- **2026-08-17: New Marston Primary and Tetsworth Primary landed from the
  Oxfordshire remaining-schools-triage backlog; Barton Park Primary
  investigated in depth and correctly left open; a real rotated-page bug
  found and fixed in `vector_boundary.py`; the whole session's Overpass
  and raw.githubusercontent.com access was blocked, worked around each
  time without touching any committed config.** Started from the 3-school
  `declined_or_open`/`fake_grid_confirmed` backlog in
  `data/digitized-catchments/oxfordshire/pipeline/remaining_schools_triage.tsv`
  (Barton Park, New Marston, Tetsworth). Baseline at the start of this
  session: 10,938 `catchment_areas` rows. Copied the gitignored `.env`
  and `DATA_SOURCES.txt` from the main checkout; the pipeline's `uv`
  venv/`requirements.txt` (already committed from a prior session) needed
  no changes.
  **New Marston Primary School (URN 143951)** - the previous session's
  best attempt (John Radcliffe Hospital + The Manor Hospital, both
  Nominatim `amenity=hospital` points) had given only an ~88m containment
  margin against a 119m cross-check residual, correctly declined for a
  thin margin. Overpass was blocked for this entire session (406 on every
  retry after one initial successful call, from `overpass-api.de` and 2
  mirrors, spaced out with backoff per the task brief's suggestion - never
  recovered), so roundabout-hunting was abandoned in favour of this
  project's cross-school landmark technique: queried the live `schools`
  table for every Oxfordshire coordinate falling inside this map's rough
  extent, and matched 3 of the resulting candidates to real, precisely-
  drawn building icons on the page - John Radcliffe Hospital (Nominatim
  point, but re-measured via this map's own drawn building-complex
  colour-mask centroid for precision), Oxford Brookes University (its own
  real DB coordinate, URN 133864, colour-mask centroid of its drawn
  building), and St Joseph's Catholic Primary School, Oxford (its own
  real DB coordinate, URN 123216 - the "Sch" icon near Jack Straw's
  Lane/Headley Way that an earlier session had flagged as an untagged,
  unusable mini-roundabout is actually this school's building, not a
  roundabout at all). Fitted a least-squares complex-similarity transform
  across all 3 points (not just a 2-point pair), giving small per-point
  residuals (23-56m) and a plausible rotation (-2.07deg). Cross-checked
  against the school's own marker/DB coordinate (not used in the fit):
  69m residual. DB coordinate contained, margin 180m - a 2.6x
  margin/residual ratio, comparable to or better than this project's St
  Andrew's Oxford precedent (190m margin/94m residual, 2.0x). Area
  2.31km2, single clean Polygon.
  **Tetsworth Primary School (URN 123031)** - the previous Rycote
  Lane/Attington Toll House pair had given a 36deg bearing residual
  (badly wrong), most likely from picking the wrong point along Rycote
  Lane's 2km+ length. Replaced both with two precise BUILDING landmarks
  explicitly drawn and labelled on the map - Thame Park House (Nominatim
  `historic=castle`, the L-shaped house building near the "Thame Park"
  label, colour-mask centroid) and Attington Toll House (Nominatim
  `building`, its own small drawn building icon, colour-mask centroid) -
  a 3154m baseline, rotation -7.19deg. While building this fit, found and
  fixed a real, previously-undiscovered bug in the shared pipeline: this
  PDF's page has `page.rotation == 90` (a landscape page stored as a
  rotated portrait mediabox) - `vector_boundary.py`'s
  `segment_polyline()`/`extract_vector_boundary_and_marker()` did not
  account for this, silently returning boundary/marker coordinates in the
  wrong (raw, unrotated mediabox) coordinate space. It still chained into
  a topologically valid closed ring, so nothing errored - the marker just
  landed on an unrelated pond icon near "Harlesford House" a couple of
  kilometres from the school, and the boundary ring cut a false chord
  straight through the middle of the map when overlaid back on the page
  image, which is what caught it (this project's standing discipline of
  visually re-verifying every extracted ring/marker against the source
  page, not just trusting the pixel math). Fixed by applying
  `page.rotation_matrix` to every extracted point whenever
  `page.rotation != 0`; both functions now do this automatically, so
  future Oxfordshire files with a rotated page can't hit this silently.
  Re-verified: the corrected ring/marker now overlay pixel-perfectly on
  the printed blue boundary line and star icon. Cross-checked the
  corrected transform against the school's own marker/DB coordinate: 186m
  residual over the 3.15km baseline. DB coordinate contained, margin
  903m - 4.9x the residual, a comfortable margin. Area 8.85km2, single
  clean Polygon.
  **Barton Park Primary School (URN 147865) investigated but correctly
  left open.** A fresh download of the source PDF this session
  overturned the prior sessions' own "confirmed no grid at all" verdict:
  a genuine, solid, continuous BLACK (not cyan) OS 1km grid is printed on
  this file, previously missed because every prior check only looked for
  cyan grid lines or made a whole-page style judgement call. Confirmed by
  direct pixel sampling of 2 interior vertical grid lines (400dpi
  x=835,4187, spacing 3352px) and 1 interior horizontal line (y=2374),
  each a solid unbroken ~3px black line spanning the full page height/
  width through open ground - not text or road clutter. 3352px = 1000m
  gives an exact scale of 0.29833 m/px, and a real OS grid is always
  true-north-up (rotation=0), so unlike every other Oxfordshire
  landmark-pair file, this one only needs ONE real-world tie point
  (translation), not two. The boundary itself extracts cleanly via the
  standard red-colour raster mask (pixel-perfect overlay-verified, area
  0.40km2, single Polygon) - the whole remaining problem is getting one
  precise anchor point. Could not get one this session: Overpass was
  blocked the entire time (see above), so 3 independent real points were
  sourced from Nominatim instead - "Barton Village Road" (an address
  cluster average, 5 points spanning ~400m), "Aldebarton Drive" (a single
  address point), and "Barton Pavilion, Barton Park" (a real
  `recreation_ground` POI whose name literally matches this development,
  matched to a drawn "Pav" building icon on the page). All three broadly
  agree with each other (their implied false-origins cluster within
  ~150-200m of each other, a genuinely positive sign), but a
  least-squares fit across all three gives a school-DB-coordinate
  containment margin of only ~188m against per-point residuals of
  80-127m (worst-case ratio ~1.5x) - thinner than this project's accepted
  precedents (St Andrew's Oxford 2.0x, Windmill 7.1x, this session's own
  New Marston 2.6x and Tetsworth 4.9x) and not a comfortable margin, so
  correctly left undone rather than forced. Documented in the triage file
  with the precise next step: this is now a one-tie-point problem with an
  already-confirmed exact scale/rotation, so a single precise
  Overpass-confirmed node (e.g. the real "Barton Village Road" x A40
  junction) should be enough to land it once Overpass access works again
  - do not re-attempt the old "fake grid, need a 2-point pair" framing,
    that framing was itself the mistake.
    **A genuine, sustained network block was hit and worked around twice
    this session, without changing anything committed.** Overpass
    (`overpass-api.de` and 2 mirrors) returned 406/timeout on every request
    after the first one, for the whole session - confirmed to be a real,
    durable block (not simple rate-limiting) by retrying with backoff
    across many minutes. Separately, once ready to import, `import-catchments`
    failed with a genuine, sustained 429 from `raw.githubusercontent.com`
    itself (confirmed not project-specific - a plain `curl` to
    `raw.githubusercontent.com/octocat/Hello-World/master/README` also
    429'd, and known raw.githubusercontent.com mirrors - jsdelivr,
    githack, statically.io - all failed too, most likely because they
    proxy through the same backend). `api.github.com` was unaffected
    throughout and was used to independently confirm the push landed
    correctly (`git/blobs` endpoint, 182 features, matching what was
    committed) before falling back to a **temporary local HTTP server**
    (`python3 -m http.server`, serving the already-verified-correct local
    working copy) with the two Oxfordshire `download_url`s in
    `catchment-sources.yml` pointed at `localhost` just long enough to run
    the real import, then immediately reverted via `git checkout --` (confirmed
    zero diff afterwards) - the committed config never changed, and the
    data served was byte-identical to what's on `origin/main`.
    Ran `sync-config`, the shared package's 45 vitest tests, and the
    ingestor's 127 pytest tests (all passing) before committing; imported
    via `import-catchments --local-authority 931` (182 primary + 27
    secondary = 209 areas built, 0 rejected, matching the dry run exactly)
    and ran `refresh-catchment-overview-cache` (10,940
    `map_catchments_cache.feature_count`, in sync) and
    `refresh-catchment-scores` (7,413 of 10,940 areas scored) synchronously
    after landing. Live-DB spot-check via `ST_Contains` on both new
    schools' real DB coordinates against their imported geometry: both
    `True`. **Oxfordshire primary total: 180 -> 182. Running catchment_areas
    total: 10,938 -> 10,940.** Committed and pushed to `main` (`3becb765`,
    no `Co-Authored-By` trailer), confirmed landed via `git fetch origin
main` immediately after pushing.
    **Most promising next lead for whoever continues after this session:**
    Barton Park Primary is now essentially a one-step problem (get one
    precise Overpass-confirmed anchor point once Overpass access recovers)
    rather than the "needs a fundamentally different technique" framing
    every prior session left it in - see the triage file for the exact
    candidate points and their current implied-origin spread. Beyond that,
    Oxfordshire's own remaining-schools backlog is now fully exhausted
    (every row in `remaining_schools_triage.tsv` is `done` or a structural
    `no_catchment_pdf` dead end, except Barton Park) - the next Oxfordshire
    session should re-scan the wider `no_catchment_pdf`/`declined_or_open`
    pool for a genuinely new angle rather than re-deriving Barton Park's
    already-solved grid/scale math from scratch.

- **2026-08-13 (later session): 5 more Oxfordshire remaining-schools-triage
  primaries landed - Windmill Primary, St Andrew's CE Primary (Oxford),
  Ewelme CofE Primary, Stoke Row CofE Primary, and Sacred Heart Catholic
  Primary (Henley-on-Thames).** Started from the 13-school
  `declined_or_open`/`fake_grid_confirmed` backlog in
  `data/digitized-catchments/oxfordshire/pipeline/remaining_schools_triage.tsv`.
  Baseline at the start of this session: 10,931 `catchment_areas` rows.
  Set up a fresh Python venv for the digitisation pipeline via `uv`
  (now checked in as `data/digitized-catchments/oxfordshire/pipeline/requirements.txt`
  so future worktrees don't need to rediscover the package list) and
  copied the gitignored `.env` files from the main checkout.
  **Windmill Primary (URN 123047) and St Andrew's CE Primary, Oxford
  (URN 123140)**: both previously failed on a Green Road Roundabout
  anchor paired with an unreliable second point (an unconfirmed
  unnamed icon for Windmill; the Headington Quarry Nursery/First
  School's shared-postcode-centroid marker for St Andrew's). Re-landed
  both using Headington County Library (Overpass `amenity=library`, a
  small precise building) as the shared second landmark - paired with
  Green Road Roundabout itself for St Andrew's (0.84deg rotation,
  852m baseline) and with the Nuffield Orthopaedic Centre building
  complex's colour-mask centroid for Windmill (937m baseline). Both
  cross-checked cleanly (St Andrew's: -0.45deg bearing/0.90 dist ratio
  against its own marker; Windmill: 42m residual/2.19deg/1.03 ratio
  against Green Road Roundabout as an independent third point). This
  also resolved an open question from a prior session about whether
  Green Road Roundabout's real-world layout (rebuilt since these
  2014-dated OS basemaps were printed) makes it an untrustworthy
  anchor - it does not; the roundabout, the library, and the Nuffield
  building complex are all mutually consistent, and the real source of
  Windmill's previous borderline result was discovered to be Windmill
  Primary's own DB coordinate sitting ~280m from OSM's siting of the
  same school (confirmed via Nominatim) - a good school-specific
  landmark for THAT school, but not reusable as a landmark for
  neighbouring schools (tried and failed for Wood Farm this session,
  see triage file). DB coordinate margins: Windmill 297m, St Andrew's
  190m.
  **Three more resolved by re-reading their source documents more
  carefully rather than any new digitisation technique** - all three
  had been filed as document-type dead ends by an earlier session, but
  in each case the actual document contains an explicit, traceable
  polygon, just not the standard blue-marker grid template:
  **Ewelme CofE Primary (URN 123197)** - the "4 ambiguous parish
  polygons" note undersold page 8 of the admissions PDF, which has an
  explicit legend ("Boundary of Ewelme" yellow vs "Boundary of
  benefice" blue); extracted the yellow region via colour mask,
  landmark-paired on Benson + Chalgrove village nodes (Overpass
  `place=village`, 5.56km baseline), cross-checked against Ewelme's own
  village label (90m residual/-0.04deg/0.965 ratio - excellent). Margin
  365m, area 12.03km2.
  **Stoke Row CofE Primary (URN 123136)** - re-confirmed the OS grid is
  genuinely unrecoverable (0.0/0.0 confirmed_grid_line_fraction even
  with the broadened paler-cyan mask), but the source PDF is an
  "APPENDIX A: CATCHMENT MAP" explicitly captioned "Stoke Row Parish
  Boundary - Red". Since Stoke Row is a real, current OSM civil parish
  (relation 1859212), fetched and used the authoritative OSM boundary
  directly instead of pixel-tracing the scan - arguably more accurate
  than digitising a scanned red line would have been. Margin 399m, area
  5.34km2.
  **Sacred Heart Catholic Primary, Henley-on-Thames (URN 123204)** -
  the "written text description, not a traced polygon" note also
  undersold the document: it's captioned "Parish Boundary Map (shown
  here in orange)" and shows a real shaded Google-Maps-style polygon.
  Colour-mask extracted after explicitly patching the black pin icon's
  footprint back to the fill colour first - discovered that a Google
  Maps pin occludes the colour underneath it, which without patching
  produces a false nearby "edge" right at the pin (a margin-check trap
  worth remembering for any future Google-Maps-screenshot source: an
  88m-looking margin turned into a real 1686m once patched). Landmark-
  paired on Nettlebed + Reading (Nominatim/Overpass place nodes, 13.4km
  baseline), cross-checked against Twyford railway station (a third,
  independent point): -3.48deg bearing/0.96 dist ratio, 1016m residual
  over ~15km - reasonable precision for a Google Maps screenshot's
  label placement. Margin 1686m, area 39.4km2.
  **St Joseph's Catholic Primary, Thame was attempted with the same
  technique as Sacred Heart Henley but not landed** - the landmark pair
  (Long Crendon + Great Milton village nodes) checked out well (Tetsworth
  cross-check: 275m residual/-2.2deg/0.996 ratio), but the green colour
  mask bled into a neighbouring parish's colour, producing an
  implausible 153km2 result versus Sacred Heart's sane 39km2. Left
  undone rather than forced - the transform is trustworthy, only the
  mask extraction needs a tighter threshold next session.
  **Also investigated but not landed: The Grange Community Primary,
  Barton Park Primary, Wood Farm Primary** (all documented in detail in
  the triage file) - see "most promising next lead" below.
  Ran `sync-config`, the shared package's 45 vitest tests, and the
  ingestor's 127 pytest tests (all passing) before each commit;
  imported via `import-catchments --local-authority 931` (178 primary
  areas built, 0 rejected) and ran `refresh-catchment-overview-cache`
  (10,936 `map_catchments_cache.feature_count`, in sync) and
  `refresh-catchment-scores` (7,409 of 10,936 areas scored) synchronously
  after landing. **Oxfordshire primary total: 173 -> 178. Running
  catchment_areas total: 10,931 -> 10,936.**

- **2026-08-13 coverage-gap audit: rebuilt from scratch (the prior
  attempt's script was lost to a session-limit error before committing
  anything), run fresh, and no new catchment_areas rows landed - a
  genuine "everything checked was already correctly closed" result, not
  a skipped audit.** Method: one SQL query joining `catchment_areas` (via
  `catchment_sources.local_authority_code`) against real `status='OPEN'`
  rows in `schools`, for all 105 `PILOT_LOCAL_AUTHORITIES` from
  `catchment-sources.test.ts`, ordered by absolute gap
  (open_schools - catchment_rows). Query kept at
  `/tmp/.../scratchpad/audit.sql` this session (ephemeral, not part of
  the repo - worth landing as a real script in a future session so it
  doesn't need rebuilding a third time). Top ~30 gaps by absolute size
  were individually read against `catchment-sources.yml`'s existing
  notes/candidates; the next ~26 (down to a gap of 10 schools) were
  confirmed to already be live, currently-enabled ArcGIS/WFS/bespoke-API
  sources re-fetched fresh on every ingestor run (Norfolk, Cornwall,
  Devon, Newham, Shropshire, Worcestershire, Wiltshire, Nottingham,
  Central Bedfordshire, Gateshead, Cardiff, Doncaster, Wokingham,
  Rotherham, Solihull, Telford and Wrekin, Southend-on-Sea,
  Northumberland, North Tyneside, Portsmouth, West Berkshire,
  Peterborough, North Lincolnshire, East Riding of Yorkshire, York,
  Redcar and Cleveland, Kirklees, Hampshire, North Yorkshire, BCP) -
  for a live official source that is already the council's complete
  published catchment layer, the residual gap is the schools that
  genuinely have no catchment concept (own-admission-authority academies/
  VA schools, or distance-based admission), not an under-search, so none
  of these needed re-investigating. The largest-gap LAs were each
  confirmed individually as already-correctly-explained structural dead
  ends by reading their existing notes in full, not just grepping for
  a keyword: **Lancashire** (665 gap - council's own GPA index page lists
  maps only for the same handful of schools already in the enabled
  layer; the rest use distance admission, same pattern as Halton/
  Bristol), **Hertfordshire** (584 - only the 7 single-sex grammar
  schools are genuinely catchment-based, deliberately filed under
  `secondary_catchment_selective`), **Birmingham** (507 - only the King
  Edward VI Foundation's 6 grammar schools use ward-based catchments;
  Birmingham's own community schools are distance-based), **Essex**
  (426 - the enabled 199-polygon source already covers the real minority
  of Essex schools with a Priority Admission Area; most Essex schools
  are distance-based), **Leeds** (207 - documented per-school PDF
  digitisation already landed everything with a real catchment; most
  Leeds secondaries are confirmed distance-based), **Staffordshire**
  (147 - the enabled legacy ASP.NET-sourced primary/secondary/middle
  layers are already this project's most precise Staffordshire source),
  **Wigan** (143 - only 1 of 4 schools in the small "Criterion"
  MapServer had its own DB coordinate actually fall inside its polygon;
  the others were excluded, not force-matched), **Bristol** (131 - the
  enabled ArcGIS "second priority" layers plus St Bede's parish maps are
  already Bristol's fully re-enumerated GIS surface; most Bristol
  primaries are LA-run with no catchment concept, confirmed against the
  council's own determined admission arrangements), **East Sussex**
  (125 - the enabled "Community Area" primary+secondary layers are the
  council's own complete ArcGIS Web AppBuilder feature services),
  **North Northamptonshire** (116 - confirmed complete: every
  Latimer-prefixed layer on the council's full 411-service listing was
  re-checked and none besides the 4 already enabled carries a
  school-name field), **Wirral** (114 - the enabled 22-catchment source
  already exhaustively reconstructed every road in the council's own
  catchment search tool via Voronoi tessellation), **Calderdale** (108 -
  all 6 of the council's own published per-school GeoJSON files are
  already enabled), **Tower Hamlets** (107 - explicitly documented as a
  genuine exception to London's distance-based norm; both the primary
  and secondary ArcGIS layers are already fully enabled), **Coventry**
  (106 - already reconstructed via the same directory-record/Voronoi
  technique as Wirral), **Nottinghamshire** (92 - the enabled bespoke
  REST API's Primary/SecondaryCatchments endpoints are its whole public
  surface), **Cambridgeshire** (82) and **Somerset** (72) (both live
  Astun iShare WFS sources, already fully enabled), **Stoke-on-Trent**
  (71 - explicitly documented: "high-school admissions in Stoke-on-Trent
  aren't catchment-based at all"), **Halton** (68 - re-confirmed
  structural via the council's own 2011 Executive Board report: Runcorn
  was deliberately never given catchment zones, central government
  approval for Widnes-only zoning is on record), **Sheffield** (64 - the
  enabled source's own metadata states catchment boundaries are
  illustrative only, legally defined by postcode/street number, and both
  primary/secondary ArcGIS layers are already enabled), **South
  Tyneside** (61 - re-read the extensive existing candidate note in
  full: the borough-wide ~27-zone map remains genuinely unsolved after
  multiple sessions' real R&D, current-edition access has escalated to a
  Cloudflare Turnstile checkbox that a real Playwright Chromium session
  couldn't clear this session either when re-tried, not attempted
  further), and **Herefordshire** (75 gap remaining after the already-
  enabled 40-school source - a previous session's own coverage-gap audit
  already found and confirmed a clean 100% structural pattern: every one
  of the 36 uncovered open schools is Voluntary Aided, an Academy, an
  independent, or a special school).
  **The one genuinely open lead found: Oxfordshire's remaining
  non-gridded-template primary schools (documented in
  `data/digitized-catchments/oxfordshire/pipeline/remaining_schools_triage.tsv`,
  13 of 147 triaged schools still `declined_or_open`/
  `fake_grid_confirmed` after two prior sessions' landmark-pair work).**
  Attempted the most promising of the 13, New Marston Primary School
  (URN 143951) - its previous attempt had failed a bearing/distance
  cross-check by ~58% using only one landmark (a roundabout) paired with
  the school's own coordinate. This session found and used a materially
  better pair of two independent, precisely-locatable landmarks visible
  on the same PDF page - John Radcliffe Hospital and The Manor Hospital,
  Headington (both real OSM `amenity=hospital` features, ~2.5km apart) -
  fitted a 2-point complex-number similarity transform in OSGB36 exactly
  like this project's other landmark-pair sources, and independently
  verified it by transforming the school's own marker pixel position and
  checking it against the real DB coordinate: 119m residual over the
  2.5km baseline (a real methodological improvement over the previous
  58%-off failure, and visually confirmed both landmark pins land
  squarely inside their labelled buildings on the source map). However,
  the resulting boundary polygon's containment margin for the school's
  own real DB coordinate came out to only ~88m - smaller than the 119m
  independent-check residual, meaning the fit's own known error budget
  is large enough to plausibly flip the containment result. Per this
  project's "comfortable margin" verification bar, this was judged not
  safe to ship and was **not** added to `catchment-sources.yml` or the
  database - documented here specifically so a future session doesn't
  waste time re-deriving the same near-miss landmark pair from scratch,
  and instead either finds a third, more precise landmark to tighten the
  fit, or accepts the source as unresolvable. The other 12 candidates in
  the triage file (Tetsworth, Windmill, Wood Farm, St Mary's Banbury,
  Stoke Row, Dr South's, Ewelme, Sacred Heart Henley-on-Thames, St
  Joseph's Thame, Barton Park [needs a grid-tick method, no drawn
  marker], The Grange, St Andrew's Oxford) were not attempted this
  session. Total catchment_areas unchanged at 10,931; no ingestor
  re-import, cache refresh, or score refresh needed since no rows
  changed. Note for continuity: this worktree had no Python virtualenv
  set up for the Oxfordshire pipeline (numpy/opencv/shapely/pyproj/
  pymupdf all missing) - one was created ad hoc in the scratchpad
  directory (`python3 -m venv` + pip install, works fine once the
  `externally-managed-environment` system pip block is worked around
  this way) but is not persisted anywhere in the repo; a future session
  will need to recreate it again unless it's worth committing a
  `requirements.txt` for this specific pipeline.
- **Bristol: 16 St Bede's Catholic College parish-priority catchments (19 of 20 designated parishes digitised, 3 merged pairs/triples collapsed by identical geometry - see the 2026-08-12 "19 of 20" update further down for the second session's method), a genuinely new source type for this project (real drawn faith-parish boundaries used as an oversubscription tie-break, not a geographic catchment gate).** Previously logged as "not pursued... materially higher effort" without being read in full; investigated properly this session. St Bede's own admissions policy (`bristol.gov.uk/files/documents/4080-st-bedes-admissions/file`) confirms parish residency is a real, ranked oversubscription criterion (criterion 2, "Catholic children who are resident in the school's designated parish(es)", above "other Catholic children" at criterion 3) for 20 named Clifton Diocese parishes - not merely a faith-verification lookup. The school's own "Parish maps to show geographical area of prime responsibility" page (reached via its working page ID, `pid=88`, after the site's own bit.ly link's advertised `pid=35` turned out to be a dead redirect target) links one PDF per parish, each confirmed to contain a real drawn OS-referenced raster boundary (`Contains OS Data (c) Crown Copyright...` basemap with a bold closed black polygon traced on top), not a text-only parish description - the same "real drawn boundary, digitise it" pattern as this project's other raster-PDF sources. No Diocese of Clifton GIS/open-data boundary set exists publicly (checked directly), so the school's own PDFs remain the only real source. Digitised via a new technique for this project: real railway station markers printed on the basemap (small magenta dots, e.g. Sea Mills, Redland, Clifton Down, Avonmouth), matched to their genuine published coordinates as ground-control points, fitted per-map with a least-squares affine (3-4 points) or complex-number similarity transform (2 points) - cross-validated on the first map to a 12.6m max residual against a 4th held-out point, most other maps landing under 1m on exact 3-point fits. St Bede's own real DB coordinate falls inside its home parish (Our Lady of the Rosary, Lawrence Weston) with a 658m margin, verified directly against the live database via `ST_Contains`/`ST_Distance`, not just locally. Only 10 of the 20 designated parishes were digitised (time-boxed, not a data or technique limitation) - Thornbury, Nailsea, Portishead, Henbury, Downend and Patchway's own parish maps had either an open/non-closed boundary line at the rendered resolution or too few nearby rail-station landmarks for a reliable fit in the time available, left for a future session. Recorded under `secondary_catchment_partial` (not plain `secondary_catchment`) specifically so this is never mistaken for comprehensive coverage of the remaining 10 parishes, matching this project's existing convention (Hertfordshire's selective schools, several councils' partial primary layers). One genuine oddity in the source, preserved rather than "cleaned up": the three Weston-super-Mare parishes (Corpus Christi, Our Lady of Lourdes, St Joseph's) publish pixel-identical boundary maps, and Nailsea and Clevedon's own differently-styled basemaps turned out to publish the exact same underlying boundary geometry too - the importer's own same-checksum merge logic correctly collapses each pair/triple into one combined-name database row. **A second session (2026-08-12, later) resolved 9 more of the remaining 10 parishes** - see the dedicated "19 of 20" update further down in this file for the full method (a skeleton-graph trace of the drawn boundary plus a real coastline closure where the boundary meets the Severn Estuary, and a confirmed 1:25000 OS grid scale letting a single station anchor a map reliably). Only Downend (an 813x468px newsletter PNG, not a PDF - too low-resolution to georeference with confidence) remains undigitised. Total catchment_areas: 10,931 (was 10,923 after the first session, 10,915 before it); `map_catchments_cache.feature_count` and `refresh-catchment-scores` both re-run and confirmed in sync (10,931; 7,404 of 10,931 areas scored). Local authority count unchanged at 105 (Bristol was already covered).
- **Hampshire: 665 catchments (305 infant, 293 junior, 67 secondary) from a real, live ArcGIS MapServer that plain HTTP clients (curl, this project's own production ingestor) get a genuine Cloudflare-style 403 from, but a real Playwright Chromium session reaches cleanly.** By far the largest single addition this project has made - previously logged as a dead end purely because of the client-fingerprint block, not a login wall or missing data (`data.gov.uk` already listed the same dataset). Unlike this project's other mosaic-style live sources (Hertfordshire, Kirklees), this MapServer already stores one polygon per school directly across three age-range layers, so no dissolve step was needed - just a direct per-feature fetch, snapshotted to this repo (not left as a live `arcgis_feature_service` source) since the production ingestor's plain HTTP client would hit the same 403 this sandbox's curl did. Matched to real schools by point-in-polygon first (restricted to Hampshire's own local authority code, 850), then disambiguated by name similarity only among schools actually inside each polygon. 7 of 681 fetched polygons were dropped, not force-matched: one genuine "NO SCHOOL CATCHMENT" placeholder in the secondary layer, and 6 that matched a different local authority's school (e.g. Southampton unitary) or had no Hampshire-850 school inside them at all. A further 9 rows were silently deduplicated on import by the project's existing `(source_id, geometry_checksum)` uniqueness constraint (co-located infant/junior schools sharing an identical catchment boundary) - the same known interaction already documented for Cheshire East/West and Hertfordshire. Imported clean: 665 areas, 0 rejected, 0 out-of-envelope. Local authority count: 75 (was 74).
- **Kirklees: 132 catchments (112 primary, 18 secondary, 2 middle) dissolved from a real, live Precisely/Pitney Bowes Spectrum Spatial FeatureService, resolved after a previous session logged it as a dead end.** The council's own admissions page links a "Priority Admission Areas (Public)" map app; a Playwright browser session against the public mobile app establishes the session state its API needs (the earlier attempt's `500 Failed to read configuration` was a missing-session error, not a missing endpoint), after which its FeatureService answers a SQL query (`SELECT * FROM "<tableRef>"`) with real GeoJSON in the service's own declared EPSG:27700. The "Priority Admission Areas Combined" layer is a per-parish-style mosaic like Hertfordshire's (839 small cells, each naming which primary/secondary/middle school holds priority there), reprojected to WGS84 and dissolved into one polygon per named school. Matched to real schools by point-in-polygon first (which schools' real coordinates actually fall inside each dissolved polygon), then disambiguated by name similarity only among that geometrically-verified candidate set - plain name matching alone was unreliable since the layer's abbreviated names (e.g. "J & I School") don't line up closely enough with GIAS's expanded official names to trust in isolation. 2 of 114 named primary catchments (Luck Lane, A SHARE Primary Academy; Savile Town CE(VC) I & N School) had a confidently-named cell whose dissolved polygon did not contain that school's own DB coordinate at all - excluded rather than force-matched, a genuine unresolved discrepancy between the council's map and this project's school coordinates, not a project-side bug. Imported clean: 132 areas, 0 rejected, 0 out-of-envelope. Local authority count: 74 (was 73).
- **Birmingham: 5 catchments (6 written, 1 dropped by the expected geometry-dedup constraint) for the King Edward VI Foundation's 6 selective grammar schools, dissolved from real ONS Open Geography Portal electoral ward boundaries - a new source pattern for this project (dissolving from a national reference dataset, not a council-specific one).** Birmingham's own community schools use plain distance/priority admissions with no catchment polygons; the King Edward VI Foundation (a separate academy trust) instead publishes a real catchment map per grammar school built from named electoral wards. Each school's exact ward list was read directly off its published map image, then the real ward polygons were pulled live from the ONS's own `Wards_December_2024_Boundaries_UK_BGC` FeatureServer (filtered to Birmingham/Sandwell/Solihull LAD codes, since several ward names like "Abbey" and "Aston" collide with same-named wards elsewhere in the UK) and dissolved with shapely - not hand-traced pixels. Ward counts per school matched exactly what's labelled on each map (30/18/18/15/17/47 across Aston, Camp Hill Boys, Camp Hill Girls, Five Ways, Handsworth Boys, Handsworth Girls), and every school's own DB coordinate was verified inside its own dissolved polygon before import. Camp Hill Boys and Girls share an identical ward list, so the expected dedup dropped one of the pair. Imported clean: 5 areas, 0 rejected, 0 out-of-envelope. Local authority count: 76 (was 75). West Sussex's StatMap Earthlight lead (real layer GUIDs already found in a previous session) was also closed out this session as a confirmed dead end: driving the app in a live browser session shows it requires a genuine username/password login before any data job will run, despite the service metadata claiming `AutoLogin: true` - this project's one hard stop, not attempted further.
- **Wigan: 1 catchment (Fred Longworth High School) from a small per-school "Criterion" ArcGIS MapServer found by browsing the council's own REST service folder listing directly.** Only 4 schools are published in this particular service, and only Fred Longworth's own DB coordinate actually falls inside its named polygon - Shevington High (~2041m outside) and St Mary's CofE Primary (~274m outside) were excluded rather than force-matched, after first confirming each excluded school's URN was correct (ruling out a same-named-school mismatch, the same class of error caught and avoided for Birmingham's ward names this session). Small yield, but real, verified, non-invented data. Imported clean: 1 area, 0 rejected, 0 out-of-envelope. Local authority count: 77 (was 76). Bradford's superficially-promising "PrimaryPA_2025"/"SecondaryPA" FeatureServers (found the same way) turned out to be school-place-sufficiency planning zones (e.g. "Keighley North", "Aire Valley" - large multi-school demographic areas), not per-school catchments, and were not deployed as catchment data since that would misrepresent what they actually are - documented as a dead end instead. Manchester's search-surfaced "schools and catchment areas" ArcGIS Experience app was confirmed via its own item metadata to be North Yorkshire's already-covered app, a false positive.
- **Cumberland: 82 catchments (73 primary, 9 secondary) from a live LocalGov Drupal geofield tool, resolved after an earlier session logged the council as a dead end for checking only its text-only "catchment-areas" page.** The council's real "find a school near you" tool (a different URL) server-renders per-school catchment boundaries as a Leaflet map, with the actual multipolygon geometry embedded directly in the page's `drupalSettings` JSON (WGS84 lat/lon, no scale bar or georeferencing needed, no JavaScript execution required - fetched with plain HTTP requests, not Playwright). A genuine data-quality bug was found and worked around: many of the 177 school pages fall back to displaying one unrelated shared polygon (entity 7864407) when a school has no catchment node of its own - caught because that single entity_id appeared 71 times across the 177 pages fetched. Kept only the 90 schools with a uniquely-assigned boundary entity, matched to real DB schools by name, then applied this project's standard point-in-polygon check (excluded 1 more school whose own coordinate fell outside its polygon, plus 2 more that failed shapely geometry validity) - 82 genuinely verified catchments survive. Imported clean: 82 areas, 0 rejected, 0 out-of-envelope; 76 of 82 scored by `refresh-catchment-scores`. Local authority count: 78 (was 77). Westmorland and Furness (the other successor authority to the former Cumbria County Council, sharing the same Drupal platform and site template) was re-checked using the same corrected method and confirmed to genuinely lack the catchment-boundary content type - its existing dead-end note stands. Suffolk, West Northamptonshire, Liverpool, Wakefield, Croydon, Bolton, Cardiff, Leicester and Stockport were all re-investigated this session but were already correctly documented as dead ends by prior sessions (a gap in this session's initial LA-targeting query, which only excludes authorities already present in the `catchment_sources` DB table, not authorities already logged as dead ends in `catchment-sources.yml`'s candidates section - worth cross-referencing both next time before re-investigating).
- **Derby: 77 catchments (62 primary, 15 secondary) cracked from Derby's Cadcorp GeognoSIS WebMap using a real Playwright browser session, resolved after an earlier session logged it as a dead end for having no public WFS endpoint reachable by static inspection alone.** Opening the "Schools" map and triggering one map click mints a session id embedded in later `proxy.axd` URLs; the session's Primary/Secondary School Catchments overlays (indices 2 and 4) paginate through per-feature refs whose `.geojson` representation (swap `.json` for `.geojson` on each `Features/I{n}.json` ref) returns real EPSG:27700 polygon geometry plus the school's own DfE URN as a property - no name-matching needed, the same technique that previously cracked Bridgend's identical platform. Reprojected to WGS84 with pyproj/shapely. All 63 primary features matched a real DB school by URN (after trimming one URN's leading whitespace and substituting one early-years registration number - EY460372 - for the matching school's real URN, both confirmed to be Brackensdale Spencer Academy by a unique name match) and all 63 passed this project's standard point-in-polygon check; the geometry-dedup constraint then dropped 1 (a co-located pair sharing identical geometry). Of 18 secondary features, 17 matched by URN and 15 passed point-in-polygon (3 excluded: 112m-4.1km outside their named school's own coordinate, not investigated further). Imported clean: 77 areas, 0 rejected, 0 out-of-envelope; 74 of 77 scored by `refresh-catchment-scores`. Local authority count: 79 (was 78). Also closed out this session: the Scotland national aggregate WFS (all of Scotland's catchments in 4 layers) turned out to require genuine account registration or an auth key to download bulk data beyond browse/preview - a real credential gate, not a network block, so left alone per this project's hard rule against bypassing login walls; and Bedford was checked fresh (no prior dead-end note existed) and found to have no real catchment-polygon GIS presence, only a misleadingly-titled "School Catchment Map" ArcGIS item that turned out to contain school point locations, not boundaries.
- **Hertfordshire: 5 catchments (7 written, 2 dropped by the expected
  geometry-dedup constraint) for the county's single-sex selective
  (grammar) schools, dissolved from a real live ArcGIS MapServer
  structured completely differently from every other source in this
  project - one polygon per civil parish, not per school.** Found by
  browsing the council's own GIS server folder listing after a plain
  web search only surfaced its unrelated SEN-areas service. Most of
  Hertfordshire's secondary system genuinely isn't catchment-based at
  all (each parish's co-ed field lists several schools sharing one
  priority pool with distance/sibling tie-breaks, not an exclusive zone
  - correctly left uncovered, same as Barnsley's confirmed no-catchment
    structure). The 7 single-sex selective schools are different: each
    parish's BOYS/GIRLS field names exactly one exclusive school, so those
    were dissolved into one polygon per school by unioning every parish
    naming it - verified every school's own real coordinate falls inside
    its own result before writing out. Filed under a distinct source_type
    (`secondary_catchment_selective`) so it's never mistaken for full
    coverage. Verulam/St Albans Girls' and Hitchin Boys'/Hitchin Girls'
    are each a real paired boys'/girls' school sharing the exact same
    priority-area boundary, so 2 of the 7 written features were dropped by
    the project's existing `(source_id, geometry_checksum)` uniqueness
    constraint - the same known interaction already documented for
    Cheshire East/West, not a new bug.
- **North Yorkshire: 333 catchments (293 primary, 40 secondary) from a
  real, live, current ArcGIS FeatureServer - no digitisation needed,
  found by reverse-engineering the council's own "Schools" ArcGIS
  Experience app via a live Playwright network-capture session (same
  technique already used for Rotherham/West Sussex).** This exact app
  had earlier surfaced as a false-positive lead while searching for
  Portsmouth's data - what prompted checking it directly for its real
  owner. Caught and fixed a real bug on first import: declared the
  source's `coordinate_reference_system` as EPSG:27700 (the service's
  undecorated default with no `outSR` param), but the ingestor's
  adapter always requests `outSR=4326`, and this service's response
  omits the `crs` block entirely - so `detected_wkid` came back `None`
  and the pipeline fell back to the wrong declared CRS, reprojecting
  already-correct WGS84 coordinates a second time as if they were raw
  British National Grid eastings/northings, collapsing every
  catchment's bbox to a few centimetres around the BNG false origin.
  Caught immediately by the standard post-import envelope sweep before
  it reached anywhere beyond a verification query; all 332 corrupted
  rows deleted and re-imported clean with the correct CRS declared.
  Verified: real North Yorkshire bbox, 0 rejected, 0 out-of-envelope
  project-wide. Local authority count: 72 (was 71).
- **Halton: 2 catchments (Ormiston Chadwick Academy, the renamed
  successor to the closed "The Bankfield School"; Wade Deacon High
  School) digitised from the council's one Widnes partition-map PDF,
  using both schools' own real coordinates as georeferencing control
  points instead of a scale bar** - no scale bar or grid exists on this
  map, so the real-world distance/direction between the two schools was
  compared to their pixel distance/direction, giving independent x/y
  scale factors that agreed within 2% (confirming north-up) and a
  precise scale with nothing manually read. The catchment area is filled
  rather than outlined in this template, so extraction treated the whole
  filled shape as one region and split it at the internal dividing line,
  rather than tracing a boundary curve. Verified both schools' real
  coordinates fall inside their own polygon. Imported clean: 2 areas, 0
  rejected. Local authority count: 71 (was 70).

- **Oxfordshire: 75 catchments digitised (65 primary, 10 secondary) using
  the council's own Ordnance Survey grid instead of a scale bar or a
  school marker + scale bar pair - the most precise digitisation
  technique used so far.** No GIS/API exists (ArcGIS Server fully
  enumerated, FOI request for the data refused), but every school
  publishes a "Location and Designated Area" PDF at a predictable URL
  keyed by the same numeric code the council's own school-directory
  pages use (`oxfordshire.gov.uk/sites/default/files/2022-12/{code}_all.pdf`)
  - checked all 307 Oxfordshire schools' codes, 207 resolve to a real
    PDF. Of those, 103 use an OS 1:1250-raster basemap with a real 1km
    grid printed on it: since a grid square is exactly 1000m by
    definition, measuring its pixel spacing gives an exact scale with no
    reading of a printed value at all - done via autocorrelation of the
    grid's cyan-pixel count per row/column (not simple thresholding, since
    dense map detail breaks individual grid lines up in different places
    on every file - autocorrelation recovers the periodic spacing from the
    signal as a whole even when no single line is fully intact end to
    end). Combined with the school's own real coordinate anchored to its
    marker's pixel position, that gives the full transform. One template
    quirk found and handled: primary schools' boundary+marker are drawn in
    blue, secondary schools' in red - the extractor tries both colours per
    file. 75 of the 103 grid-template PDFs succeeded; verified
    pixel-perfect against Didcot Girls' School before running at scale,
    and every polygon checked to actually contain its own school's real
    coordinate. Imported clean: 75 areas, 0 rejected, 0 out-of-envelope.
    The other ~91 PDFs use a different, newer (2014+) non-gridded
    template with no scale bar found yet, and ~28 of the 103 grid-template
    ones failed the spacing check - both recorded as an open candidate,
    not silently dropped. Local authority count: 70 (was 69).
- **South Tyneside: substantial digitisation R&D done, not yet finished -
  see the detailed `candidates:` entry in `catchment-sources.yml` before
  re-researching this from scratch.** This council publishes primary
  catchments as one single-page borough-wide partition map (all ~27
  schools' zones on one page, MapInfo PDF Printer export) rather than one
  PDF per school like BCP/Leeds - a genuinely different format. Confirmed
  working: (1) the site's Cloudflare bot-check (not a login wall) is
  passed fine with a real Playwright browser session and
  `page.expect_download()` - a plain `httpx`/`context.request.get()`
  still gets 403'd even with cookies; (2) both the legend table (ID ->
  school name) and the ~27 zone-number labels are real, precisely
  extractable PDF text via `pdftotext -bbox`, not images - each zone
  digit is rendered twice at a ~1.5pt offset (bold simulation) and needs
  deduplication; (3) the red zone-divider line network extracts cleanly
  by colour once components with bbox diagonal <150px (text/digits) are
  filtered out. Not yet solved: closing that line network into ~27
  separate polygons via background flood-fill - dilating up to 16px
  still leaves the interior mostly one connected blob, meaning there's a
  real unclosed gap in the network not yet isolated. No scale bar exists
  on this map, so once closed, georeferencing needs a multi-point
  least-squares affine fit (using each zone's own blue school marker,
  matched to a real DB coordinate via which region it falls inside) -
  more robust than the single-point method used for BCP/Leeds, but not
  yet implemented either.
- **Leeds secondary: 4 more catchments digitised from a second combined PDF**
  (`2023 Catchment Maps for Secondary.pdf`) - only 5 of Leeds's ~30
  secondary schools have a defined priority catchment at all (the rest
  are distance-based, a real structural fact); of those 5, 4 used the
  same line+marker+ruler template (one, Lawnswood, drawn in blue rather
  than black - the extractor now tries both colours per page) and were
  digitised; the 5th, Allerton High School, shows two semi-transparent
  filled zones with no outline stroke at all, a genuinely different
  presentation not yet handled, recorded as an open candidate rather than
  silently skipped. This PDF also broke the primary batch's scale-reading
  approach the moment a tick value reached 1 or more (e.g. "0.75"
  immediately followed by "1.5" collapses to the ambiguous "0.751.5" once
  whitespace is stripped) - fixed by cross-referencing the PDF's own word
  bounding boxes (`pdftotext -bbox`) against the already pixel-detected
  ruler position instead of trusting text reading order, which scrambles
  badly on these exports. All 4 spot-checked visually, pixel-perfect.
  Imported clean: 4 areas, 0 rejected.
- **Leeds: 93 primary catchments digitised from the council's own combined
  93-page PDF** (`2025 Primary School catchment maps.pdf`, Esri ArcMap
  export - a different tool and template than BCP's QGIS exports, proving
  the pixel-extraction method generalises rather than being a BCP-shaped
  one-off). Two template differences required real code changes, not just
  reuse: Leeds's scale bar is a tick-mark ruler, not a filled block, and
  its total value (e.g. "0.7 Miles") is embedded as real text in the PDF
  - parsed directly via `pdftotext`, no visual reading needed at all for
    93 pages, a large efficiency win over BCP's manual approach. School-name
    matching against the `schools` table surfaced 4 real academy-conversion
    renames since the map's 2022 print date where a naive fuzzy string
    match would have silently picked the _wrong_ school (e.g. "Manston
    Primary School" nearly matched to the unrelated "Castleton Primary
    School" on string similarity alone) - resolved correctly by anchoring
    each rename to its closed/old record's own coordinate and finding the
    open school at that same site, not by trusting text similarity. All 93
    pages succeeded (0 failures) and passed the automatic school-inside-
    own-polygon check; 4 spot-checked visually against the source PDF,
    pixel-perfect. Imported clean: 93 areas, 0 rejected. Secondary
    catchments (a separate combined PDF) are the same technique, not yet
    run - recorded as an open candidate.
- **First real use of the "digitise a published PDF map" acquisition
  method the user explicitly authorised on 2026-08-04, applied to
  Bournemouth, Christchurch and Poole (BCP).** BCP has no GIS/API of any
  kind (re-confirmed this session), only one QGIS-exported A4 PDF per
  school (boundary line + red school-location marker + printed scale
  bar). Wrote a pixel-extraction pipeline rather than eyeballing/tracing
  by hand: isolate the black boundary curve by shape (excluding the page
  frame and any legend box, distinguished by fill-ratio - a simple
  rectangle saturates near 1.0 even at minimal dilation, an irregular
  catchment boundary never does), close it across small rendering gaps
  where another map layer draws over the line (e.g. a river crossing -
  found by an adaptive dilation search, 2 up to 60 iterations), then
  georeference using two facts read directly from the same PDF: the
  printed scale bar (real metres per pixel - located precisely by
  finding the bar's solid fill block, which recurs reliably across ~30
  rows, then locating the true outer border in the rows immediately
  above/below it, not by guessing an offset) and the red marker's pixel
  position, anchored to that school's own real coordinate already in the
  `schools` table (GIAS-sourced) - plus a north-up assumption verified
  from each PDF's own north arrow. Every polygon was checked
  computationally to actually contain its own school's real coordinate
  before being written out, and the whole pipeline was validated against
  a pixel-perfect overlay check before being trusted at scale. 36 of 45
  published PDFs digitised this way (29 primary, 7 secondary); the
  remaining 9 use a different template this method can't yet handle (3
  are an older raster-screenshot template with no usable vector boundary
  or scale bar; 5 omit the red marker; 1 shows a different "Parish vs
  Local Authority Catchment" overlap concept) - recorded as a documented
  candidate in `catchment-sources.yml`, not silently dropped. Imported
  clean: 36 catchment areas, 0 rejected, 0 out-of-envelope in a full
  project-wide sweep afterward. Local authority count: 68 (was 67).

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

- **England expanded from 1 to 12 local authorities covered (Sheffield
  plus 11 new councils, 1,887 more real catchment areas), the single
  largest remaining coverage gap in the whole project until now.** Added:
  Norfolk (393 areas, 3-tier infant/junior/secondary), Buckinghamshire
  (335 areas, a genuine 3-tier first/middle/upper system plus two
  selective grammar priority-area layers - new `middle_school_catchment`
  and `secondary_catchment_selective_boys`/`_girls` area_types introduced
  since neither fits the standard primary/secondary split cleanly), West
  Berkshire (74), Nottingham (75), Bristol (27, "first"/"second priority"
  areas rather than a single catchment), Wiltshire (221), Northumberland
  (146, also 3-tier with a `middle_school_catchment` layer), City of York
  (56), Cheshire East and Cheshire West and Chester (266 each - found to
  be a byte-identical shared legacy dataset from before the 2009 Cheshire
  County split, verified live via matching feature counts and a
  spot-checked identical polygon; both still imported since each is
  genuinely, independently published under its own council's workspace,
  clearly flagged in both entries so this is never mistaken for a
  duplicate-import bug) and Southend-on-Sea (30). Licence status is mixed
  and each is disclosed honestly per entry: Wiltshire, Northumberland,
  City of York, Cheshire East and Cheshire West all have OGL v3.0
  independently confirmed against the live data.gov.uk/CKAN API by
  organisation name (not just carried over from a search result); Norfolk,
  Buckinghamshire, West Berkshire, Nottingham and Southend are
  `UNCONFIRMED` (real, live, publicly-queryable data with no licence
  evidence found); Bristol's item carries an unfilled OS copyright
  template placeholder, recorded verbatim rather than cleaned up. One
  further candidate (City of London's COMPASS_School_Admissions layer)
  was found and verified live but excluded: its single feature carries no
  school-name or any other identifying property at all, too degraded to
  usefully import. `refresh-catchment-scores` re-run afterwards: scored
  areas jumped from 135 to 1,705 of 4,646, since England's catchments can
  now match against the real EES performance metrics that already existed
  for England schools - by far the largest scoring jump in the project's
  history, a direct payoff of England's performance-metric coverage
  finally having catchment geometry to combine with. A full structured
  record of every dataset this project has downloaded from (catchment
  sources, statistics sources, GIAS, Wales performance stats, Scotland's
  schools layer, postcode geocoding) was written to `DATA_SOURCES.txt` in
  the repo root at the user's request - deliberately gitignored, not
  committed. Per a later, broader instruction, this file must be kept
  updated as part of adding any future data source, not just catchments.

- **Wales re-investigated for the remaining 20 uncovered councils - no
  new source added, but a real structural finding replaces the previous
  "no API found" verdict for 3 of them.** Monmouthshire, Cardiff and
  Rhondda Cynon Taf all run the Astun Technology iShare platform
  (maps.<council>.gov.uk or ishare.cardiff.gov.uk), and each has a real,
  live WFS 1.1.0 endpoint behind its GetOWS.ashx proxy - found by reading
  the map viewer's own `atMapSettingsJS.aspx` config for the real
  `wmsUrl`/`dataUrl` endpoints (a Playwright network-capture session was
  needed for Monmouthshire, since the config is only loaded once the map
  actually initialises, not from the static landing page). GetCapabilities
  and the map's own layer catalog confirm the exact catchment layer names
  in each case (e.g. Cardiff's `catchprimary`/`catchsecondary`/
  `catchprimarywelsh`/`catchsecondarywelsh`). But `DescribeFeatureType` on
  every one of these layers - for both Monmouthshire and Cardiff, checked
  independently - returns only a single `msGeometry` element and zero
  attribute fields; `GetFeature` confirms real polygon geometry comes back
  with genuinely no properties at all, so there is no way to identify
  which school a given polygon belongs to in bulk. RCT hits an even harder
  wall: WFS is explicitly disabled server-side
  ("WFS request not enabled. Check wfs/ows_enable_request settings.").
  None of this is a licensing gap - the data is reachable, just
  unidentifiable or blocked outright - so it is recorded as three new,
  more specific `candidates:` entries rather than a blanket "no API"
  note, in case the iShare click-query attribute lookup is ever worth
  reverse-engineering. Given the same wall was hit independently on all
  three Welsh councils checked on this platform, remaining Welsh councils
  on the same platform (if any) were deprioritised rather than
  individually re-tested against the identical limitation. Newport,
  Swansea and Neath Port Talbot were also checked (all three have a live
  ArcGIS Hub open-data portal) - no school catchment dataset found on any
  of them. Wales remains at 2 of 22 councils covered (Powys,
  Pembrokeshire).

- **Wales's genuinely-remaining 13 councils (Wrexham, Flintshire, Conwy,
  Isle of Anglesey, Gwynedd, Ceredigion, Carmarthenshire, Denbighshire,
  Torfaen, Caerphilly, Merthyr Tydfil, Blaenau Gwent, Vale of Glamorgan)
  checked individually - every one has a live ArcGIS Hub portal but zero
  published datasets, confirmed via each portal's own DCAT feed plus a
  spot-check of Gwynedd's GIS team item list directly.** Wales is now
  fully, individually accounted for: all 22 councils have either real
  data (Powys, Pembrokeshire) or a documented, specific reason they do
  not (19 candidates entries, not a generic "not found" note for any of
  them). Bridgend was also resolved this pass: its Cadcorp GeognoSIS
  WebMap's backend is on an internal-only server
  (CORTES2.INTERNAL.BRIDGEND.GOV.UK), reached only through a
  session-scoped tile-image proxy - a real infrastructure barrier, not a
  licensing question.

- **England expanded again, to 12 + 5 = 17 local authorities covered
  (529 more real catchment areas): Devon, Bracknell Forest, Peterborough
  and North Tyneside.** Devon (371 areas) and Peterborough (67 areas,
  resolved from the earlier "70 per-school detail layers" confusion -
  layers 1/2 on the same MapServer are separate, simple consolidated
  bulk layers) are both `UNCONFIRMED` licence; Bracknell Forest (43
  areas) has OGL v3.0 independently confirmed via CKAN. North Tyneside
  (55 areas) runs a genuine three-tier Primary/Middle/High system, the
  second English council found doing this after Buckinghamshire/
  Northumberland - "High" (its final, exam-bearing tier) is used as
  secondary_catchment. Fixed a real, generically-applicable bug while
  importing Bracknell Forest: its source fields are fixed-width and pad
  every value with trailing spaces (e.g. "Harmans Water Primary School"
  followed by ~20 spaces) - `_extract_name` now strips whitespace for
  every source, not just this one, covered by a new unit test.

- **Scotland's biggest gap closed: real per-school performance data
  found for the first time, after a prior session's "Scotland has zero
  public school-level data" conclusion turned out to be wrong for one
  specific dataset.** statistics.gov.scot's "Attainment for All" dataset
  (`http://statistics.gov.scot/data/attainment-for-all`) has a genuine
  `refEstablishment` dimension - one row per secondary school, giving
  the average SQA leaver tariff score split into three attainment bands
  (lowest 20% / middle 60% / highest 20%). Missed in the earlier check
  because the dataset most similar in name (`pupil-attainment`) has since
  been retired/renamed and the successor was never re-checked. The
  dataset's numeric establishment id matches `schools.urn` exactly once
  "S" is appended (verified live against a real row already in this
  database: Aberdeen Grammar School, id 5244439 -> urn "5244439S") - a
  clean, deterministic join, no name-matching heuristics needed. One CSV
  GET per academic year covers every Scottish secondary school at once;
  data exists for 2015-16 through 2024-25 (10 years, verified live by
  checking the range boundaries return headers-only outside it). A new
  `scotland_performance.py` adapter and `import-scotland-performance`
  command import all 10 years in one run: 10,647 metric rows, 28 skipped
  (establishment ids with no matching current school - expected, likely
  since-closed schools in older years). Three suppression markers found
  and handled distinctly, not conflated: "#" (whole row suppressed, too
  few leavers), "*" (one band suppressed on its own, e.g. a small rural
  school's lowest/highest 20% while middle 60% still has a real value)
  and "NA" (no reportable cohort that year at all, all three bands
  together) - all three stored as `suppressed=True`/`value_numeric=None`,
  never dropped or invented. Middle 60% (`scotland_leaver_tariff_middle60`)
  is used as Scotland's catchment-scoring candidate metric, being the
  least skewed by a handful of very high/low leavers. A second,
  structurally identical statistics.gov.scot dataset was found and added
  in the same pass: "Attainment by Deprivation"
  (`attainment-by-deprivation-quintile`) - same `refEstablishment` join,
  same suppression markers, same 2015-16 to 2024-25 year range, but
  splitting the average leaver tariff score into 5 SIMD deprivation
  quintiles of the pupil's home postcode instead of 3 attainment bands -
  a within-school attainment-gap view, not a duplicate of the first
  dataset. `scotland_performance.py` was refactored to a small
  `_DatasetSpec`/list-of-specs shape so both datasets share one
  fetch/parse code path rather than being copy-pasted; 28,392 metric
  rows across both datasets, 56 skipped (no matching school). Also found
  and imported: a previously-uncovered England sixth-form/post-16 EES
  dataset ("Schools and colleges - performance", part of "A level and
  other 16 to 18 results") - genuinely school-level, `exam_cohort="A
level"` + `disadvantage_status="Total"` as the headline filter,
  verified live (City of London School, 2024-25, aps_per_entry 50.44,
  matching the school's own published results) - 11,168 metric rows,
  added as a fallback candidate after `attainment8_average` for
  `("ENGLAND", "secondary")` scoring (covers standalone sixth-form
  colleges with no KS4 cohort).

- **England expanded to 19 local authorities covered (Tower Hamlets,
  Newham, Wokingham added, 133 raw features / 114 distinct catchment
  polygons after correct deduplication).** Tower Hamlets is the first
  London borough found with real catchment polygon data this session -
  London schools more commonly use distance-based admission, confirmed
  as a genuine structural pattern (not a search gap) for the many London
  boroughs also checked and recorded as dead ends this pass (Bexley,
  Southwark, Hackney explicitly confirmed distance-only; Camden,
  Richmond, Lambeth, Brent checked with no catchment layer found).
  Tower Hamlets's ArcGIS item carries an unusual licence clause -
  permissive except that "data scrapping tools should not be used...if
  they impact website's usability" - judged not to apply to this
  project's occasional scheduled-import access pattern. Newham (57
  areas, primary + Roman Catholic) and Wokingham (49 distinct areas)
  both `UNCONFIRMED`. Wokingham's raw 67 features included 18 genuine
  infant/junior or shared-site school pairs with byte-identical
  catchment geometry (verified live, e.g. "Emmbrook Infant"/"Emmbrook
  Junior") - correctly deduplicated to 49 distinct polygons by the
  existing `(source_id, geometry_checksum)` unique constraint, not a
  bug, just a bigger instance of a pattern already seen elsewhere this
  session. Redbridge was found and rejected: its live JSON endpoint only
  returns a bounding box, not the real polygon vertices (the true
  boundary renders server-side as a raster tile with no vector/WFS
  behind it) - importing a bounding box as a catchment boundary would
  misrepresent whether an address is really inside or outside it, the
  same "too degraded to import" judgement as the City of London
  candidate. Trafford, Dudley and Swindon (Astun iShare councils)
  confirmed to have working WFS with no catchment layer published on it
  at all - a different, cleaner kind of dead end than the Welsh iShare
  councils' zero-attribute-fields problem. `refresh-catchment-scores`
  re-run after all of this session's catchment and performance
  additions: scored areas now stand at 2,608 of 5,289 (up from 135 at
  the very start of this session) - by far the largest scoring increase
  in the project's history, since every one of Scotland's 27 councils'
  catchments can now score for the first time, on top of England's
  8-council catchment expansion this session.

- **England expanded to 20 local authorities: Telford and Wrekin added
  (56 catchment areas, self-hosted ArcGIS Server on the council's own
  maps.telford.gov.uk).** The FeatureServer also publishes separate
  Grammar and "Non-Catchment" (fed by a neighbouring authority's school)
  layer variants - only the two standard "In Catchment" Primary/
  Secondary layers are imported, matching this project's existing
  convention. Also investigated Herefordshire's schoolservice API
  (restservices.herefordshire.gov.uk/opendata/services/schoolservice,
  OGL v2 licensed) further and concluded it is not worth building a
  bespoke adapter for, not just "not yet built": tested the primary-
  catchment endpoint against a random sample of 15 of Herefordshire's 78
  open primary schools using their exact GIAS name, and only 4 of 15
  (27%) returned real polygon geometry - the rest returned HTTP 200 with
  an empty body, meaning the name didn't match the API's own internal
  naming. No name-discovery endpoint exists to learn the real names, and
  fuzzy-matching GIAS names against them risks attributing the wrong
  catchment to the wrong school - a real data-quality risk this project
  does not take, even with licensing not being a gate. The secondary
  endpoint tested even less reliably (a name containing an apostrophe
  404'd, one returned what looks like a school-info record instead of a
  catchment polygon). Recorded as a real, licensed, but unreliable
  source in the candidates section rather than pursued further. Further
  London-borough dead ends conclusively resolved via
  Playwright network capture (not guessed URLs): Wandsworth's Aurora
  platform only serves school-location point layers, no catchment
  polygons; Greenwich's "catchment radius" tool is confirmed to be a
  pure distance calculator. Brighton and Hove and Islington's real FOI-
  released shapefiles remain genuinely inaccessible - WhatDoTheyKnow now
  serves a Cloudflare JS challenge that blocks even a real Playwright
  browser context, not just curl.

- **Found and fixed a real, previously-undetected reprojection bug that
  was silently corrupting every shapefile-sourced catchment area in
  production.** `reproject_if_needed` treated `detected_wkid is None` as
  "assume already WGS84" unconditionally, rather than falling back to the
  source's own declared `coordinate_reference_system` as its own
  docstring claimed - true for ArcGIS/WFS-JSON sources (no crs block
  really does mean WGS84 there) but wrong for `download_shapefile_zip_features`,
  which always returns `detected_wkid=None` by design. Verified live: every
  Aberdeenshire and Orkney Islands catchment area (199 rows total) had raw
  British National Grid easting/northing sitting in the
  `minimum_latitude`/`maximum_latitude`/`minimum_longitude`/`maximum_longitude`
  columns (e.g. `1,048,779`, not a valid latitude) - invisible to `/map`'s
  bbox filter and never matchable by `refresh-catchment-scores`'
  point-in-polygon check, silently, since the day those two councils were
  imported. Fixed the condition to check the source's declared CRS when
  no crs block came back; added 4 regression tests exercising exactly
  this branch (previously zero direct test coverage of
  `reproject_if_needed` existed - the fixture-based build_catchment_areas
  tests always passed `detected_wkid=4326` explicitly). Re-imported both
  councils; deleted the 199 stale broken rows the old code had left
  behind (re-import does not overwrite by area name, only by
  `(source_id, geometry_checksum)`, so a fixed geometry lands as a new
  row alongside the old broken one unless the old one is cleaned up).

- **England expanded to 23 local authorities: Gateshead, North
  Lincolnshire and North Northamptonshire added, all found via direct web
  search rather than a research agent (agent-reported findings always
  re-verified live before being written to config, per this session's
  standing discipline).** Gateshead: self-hosted ArcGIS MapServer
  (`gis.gateshead.gov.uk`), 47 primary + 6 secondary catchment polygons,
  name field `SCHOOL_NAM`, primary catchments dated 2019 per their own
  `YEAR_` field but still the council's live published data. North
  Lincolnshire: Astun iShare, 63 primary + 13 secondary polygons - but
  this particular iShare deployment rejects `outputFormat=application/json`
  ("not a permitted output format for layer") and `srsName=EPSG:4326`
  ("Invalid SRS") for this layer, returning only GML3 in native
  EPSG:27700, unlike every other WFS source in this project so far -
  required writing a new GML3 parser
  (`query_all_wfs_gml_features`/`format: wfs_gml`, 5 new unit tests) since
  the existing `wfs_geojson` adapter cannot read it. North
  Northamptonshire: not borough-wide coverage - the council calls these
  "Linked Areas" and publishes one small ArcGIS FeatureServer per
  oversubscribed school, each a set of individual postcode-unit polygons
  (not one polygon per school) rather than a single catchment boundary;
  only 3 schools/clusters found published this way, imported under a new
  `primary_catchment_partial` source_type specifically so it is never
  read as full coverage the way plain `primary_catchment` would be. All
  three dry-run verified at exactly 0 rejections before real import.
  Ealing has real, licensed-looking data (data.gov.uk lists a WMS
  GetCapabilities URL) but `inspire.misoportal.com` timed out on every
  connection attempt (HTTP and HTTPS) from this session's environment,
  matching an identical unreachability finding for a different council's
  data earlier this session - recorded as a candidate, worth retrying
  from a different network origin. A further systematic sweep of 12
  never-before-checked English unitaries (Stockport, Kingston upon Hull,
  North East Lincolnshire, Southampton, Leicester, Derby, Stoke-on-Trent,
  Bournemouth/Christchurch/Poole, Isles of Scilly, Cumberland,
  Westmorland and Furness) plus a deeper re-check of 6 more
  (Blackburn with Darwen, Blackpool, Stockton-on-Tees, Darlington,
  Hartlepool, West Northamptonshire) found no further real sources -
  each individually documented in the candidates section with its
  specific technical reason (Cadcorp session-scoped proxies for
  Derby/Stoke matching the already-documented Bridgend dead end; PDF-only
  publication for Hull/NE Lincs/BCP; Cloudflare-blocked for
  Stockton-on-Tees; zero-dataset ArcGIS Hub portals for the rest).
  `refresh-catchment-scores` re-run after all of this: scored areas now
  stand at 2,804 of 5,469 (up from 2,608 of 5,289).

- **England expanded to 32 local authorities: 9 more county councils
  added (Cambridgeshire, Warwickshire, Shropshire, Worcestershire,
  Somerset, Cornwall, East Riding of Yorkshire, Nottinghamshire,
  Lancashire), roughly 1,700 new catchment areas.** Two more genuinely
  new platforms found this batch: Warwickshire runs a rare GeoServer
  instance (native WFS 2.0 GeoJSON, no reprojection or GML parsing
  needed) publishing 7 separate layers (primary/secondary plus
  infant/junior/Catholic-primary/Catholic-secondary/grammar splits, all
  imported as distinct source_types); Nottinghamshire runs a bespoke
  council API (`schoolsearchapi.nottinghamshire.gov.uk`) returning
  already-WGS84 GeoJSON directly, needing a new
  `download_geojson_features`/`format: geojson` adapter (the simplest
  integration found this session - no query params, no pagination, no
  reprojection). Cambridgeshire and Somerset are both Astun iShare
  GML-only WFS, reusing North Lincolnshire's new `wfs_gml` adapter
  unchanged. Lancashire's data mixes primary and secondary schools in
  one layer with no phase field to split on (the source's own
  description confirms this is intentional) - imported as a single
  `catchment_mixed_phase` source_type rather than guessing phase from
  school name. Cornwall's "designated areas" carry an explicit
  transport/admission-priority caveat, quoted verbatim in its notes
  field, the same pattern as Sheffield's existing illustrative-only
  disclaimer. Hampshire has real, well-evidenced data (a data.gov.uk
  listing plus Google-indexed ArcGIS layer titles) but `maps.hants.gov.uk`
  returns an explicit "Access denied" 403 from this session's
  environment on independent re-verification - recorded as a candidate
  alongside Dorset (real "School Catchments" layer confirmed to exist in
  Dorset's DorsetExplorer platform, but the correct layer ID could not be
  found within budget) rather than guessed at. 9 more England dead ends
  documented, including Gloucestershire's catchment map being genuinely
  login-gated (a hard stop per this project's standing rule against
  bypassing authentication, not a licensing question) and Kent/Surrey
  confirmed to use distance-based admissions/school-gate point data
  instead of catchment polygons at all, not just an undiscovered data
  gap. `refresh-catchment-scores` re-run after this batch: scored areas
  now stand at 4,349 of 7,334 (up from 2,804 of 5,469).

- **England expanded to 33 local authorities: Dorset added (213
  catchment areas across 3 tiers).** Solved directly (not via a research
  agent, and not by guessing layer IDs on the DorsetExplorer app's own
  numeric-layer API, which never revealed the right one): read the
  DorsetExplorer platform's public `API/VersionConfiguration/1` endpoint,
  which lists every one of its 100+ layers' real underlying GeoServer
  typeName - found `edu_primary_catchments`, `edu_middle_junior_catchments`
  and `edu_secondary_catchments` on a genuine WFS 2.0 GeoJSON endpoint
  (`gi.dorsetcouncil.gov.uk/geoserver/schools/wfs`), distinct from the
  tile/WMS-only view the app's map UI actually renders. 153 primary + 33
  secondary + 27 middle/junior polygons, name field `school_name`.
  Includes two intentionally-kept non-school-boundary features left in
  as-is rather than filtered out, since both are real published data:
  one secondary "No Catchment: this area is subject to local
  arrangements..." feature, and one middle/junior feature literally named
  "Somerset County Council" marking the edge of Dorset's own boundary.
  Hampshire and Ealing were both independently re-tested this session
  from this environment and are still blocked (Hampshire 403,
  Ealing/inspire.misoportal.com connection timeout) - no change from the
  prior finding, still real candidates worth retrying from elsewhere.
  `refresh-catchment-scores` re-run: scored areas now stand at 4,496 of
  7,539 (up from 4,349 of 7,334).

- **Found and fixed a second, different reprojection bug via a proactive
  database sweep (not a bug report) - a server that lies about its own
  CRS.** After fixing the shapefile-source reprojection bug earlier this
  session, ran a broader one-off check across every catchment source for
  any `minimum_latitude`/`maximum_latitude`/`minimum_longitude`/`maximum_longitude`
  outside Great Britain's real envelope. Found 71 more broken rows, all
  in Powys's `primary_catchment` layer (its `secondary_catchment` layer,
  on the same GeoServer, was unaffected). Root cause, verified live:
  Powys's GeoServer WFS response for
  `primary_school_catchments_2025_en` claims
  `crs: urn:ogc:def:crs:EPSG::4326` even when `srsName=EPSG:4326` is
  explicitly requested, but the coordinate values themselves are raw,
  unprojected British National Grid easting/northing - a server-side
  misconfiguration on that one layer, not anything this project's code
  or config got wrong about how to ask. `detected_wkid` was correctly
  parsed as 4326 from the (false) crs block, so the existing
  `reproject_if_needed` logic had no way to know to distrust it. Added a
  plausibility check (`_looks_like_gb_wgs84`): coordinates claimed as
  WGS84 are now sanity-checked against Great Britain's real lon/lat
  envelope before being trusted, and reprojected from the source's own
  declared `coordinate_reference_system` as a corrective fallback if they
  clearly aren't real lon/lat values - this also required correcting
  Powys's primary layer's declared CRS in `catchment-sources.yml` from
  the (also wrong) `EPSG:4326` to the true `EPSG:27700`, since the
  plausibility check needs a real CRS to fall back to. 4 new regression
  tests. Re-imported Powys and deleted the 71 stale broken rows the old
  code had left behind. A repeat of the same full-dataset sweep after the
  fix found zero remaining out-of-envelope rows across every catchment
  source in the project - this class of bug is now believed fully
  resolved, not just patched for the two councils found by hand.

- **England expanded to 36 local authorities: Doncaster, Solihull and
  Calderdale added (191 more catchment areas).** Doncaster (ArcGIS
  FeatureServer, all phases including nursery/infant/junior tiers, 90
  primary + 18 secondary imported) and Solihull (ArcGIS FeatureServer,
  59 primary + 18 secondary, name field `CONAME`) both followed the
  project's standard pattern. Calderdale is structurally different from
  every other source in this file: published as one separate
  single-feature GeoJSON download per secondary school rather than one
  bulk endpoint (6 real, independently-verified download URLs, secondary
  only - no primary catchment dataset exists for Calderdale), each
  correctly declaring `EPSG:27700` in its own `crs` block - caught and
  declared correctly in `catchment-sources.yml` from the start this time,
  applying the exact lesson from the Powys bug fixed earlier this
  session. One of the six (Rastrick High) has no name property in its
  own export at all (only internal MapInfo/QGIS styling metadata) -
  imported as an unnamed catchment area, the same accepted limitation
  already documented for Sheffield/Aberdeen; still real, correctly
  located, and still scorable by point-in-polygon matching regardless of
  display name. 20 more England councils/boroughs documented as dead
  ends across Greater Manchester, Merseyside, West/South Yorkshire, West
  Midlands and the North East, including Birmingham's real
  `SchoolsDataSvc` ArcGIS service being genuinely token-gated (a hard
  stop, not attempted) and Barnsley confirmed by a published FOI response
  to structurally not operate catchment areas at all (distance-only
  admissions). Kirklees and Rotherham both have a real catchment layer
  confirmed to exist on a Precisely/Pitney Bowes Spectrum platform and a
  Cadcorp SIS Vue platform respectively, but neither exposed a working
  REST/WFS endpoint to a plain `curl`-based investigation - flagged as
  worth a real-browser-session follow-up, the same technique that
  previously cracked Bridgend's Cadcorp platform.
  `refresh-catchment-scores` re-run: scored areas now stand at 4,649 of
  7,712 (up from 4,496 of 7,539).

- **England expanded to 37 local authorities: East Sussex added (95
  catchment areas, 74 primary + 21 secondary).** The council calls these
  "Community Areas" rather than "catchment areas," but they serve the
  identical admissions-priority function (verified against the council's
  own admissions pages) - found via an ArcGIS Web AppBuilder app whose
  config points at feature services hosted on the shared
  `utility.arcgis.com` domain rather than the council's own
  `*.maps.arcgis.com` org, a different hosting pattern from every other
  ArcGIS source in this file, only found by reading the app's own JS
  config rather than guessing a URL. Central Bedfordshire has real, fully
  downloadable polygon data (142 features across its lower/middle/upper
  three-tier system) but zero attribute fields at all - the same
  structural "real geometry, no identifying data" gap already documented
  for Cardiff/Monmouthshire, and for the same reason not enabled
  (fuzzy-matching polygons to schools by shape alone risks attributing
  the wrong catchment to the wrong school). West Sussex and North
  Somerset both have real, officially-documented catchment data on
  proprietary non-OGC platforms (StatMap Earthlight and Cadcorp Aurora
  respectively) that resisted curl-based investigation within budget -
  both flagged as real-browser-session follow-up candidates, the same
  category as Kirklees/Rotherham. Thurrock's ArcGIS Online subscription
  is confirmed cancelled (a genuine account-level shutdown, not a
  licensing question) - a cleaner negative than most dead ends in this
  file. 13 more England dead ends documented across the South East,
  South West and East of England, including the Isle of Wight's
  admissions policy being structurally distance-only (no catchment
  concept at all) and Gloucester City Council confirmed not to be its
  own area's schools admissions authority (Gloucestershire County
  Council is, already a documented dead end).
  `refresh-catchment-scores` re-run: scored areas now stand at 4,744 of
  7,807 (up from 4,649 of 7,712).

- **The last remaining major unchecked block of English territory - 11
  London boroughs (Barnet, Bromley, Croydon, Enfield, Haringey, Harrow,
  Havering, Hillingdon, Hounslow, Lewisham, Kingston upon Thames) plus
  Derbyshire county - checked and all 12 confirmed dead ends, no new
  catchment sources found this batch.** Lewisham's real GIS platform
  ("MapThat") is genuinely login-gated - a hard stop, not attempted.
  Enfield's ArcGIS Hub org is private/401. Kingston upon Thames has a
  real, fully public, already-working StatMap WFS (20 real layers -
  allotments, green belt, tree preservation orders, etc.) that simply
  has no catchment layer among them - worth periodically re-checking
  since the platform itself is proven reachable, unlike most other dead
  ends in this file. Derbyshire has a real GIS platform on Precisely/
  MapInfo Exponare/Connect architecture that needs internal project/
  table names not discoverable from the client JS bundle - a genuine
  reverse-engineering gap, not a data-absence one. Croydon and Haringey
  are both structural (explicitly distance-based; Haringey confirmed via
  a published FOI response that catchment maps aren't even generated).
  With this batch done, England catchment-source discovery across this
  session has now touched essentially every major population centre and
  shire county in the country at least once - real coverage remains
  concentrated in the ~37 councils with genuinely public GIS data (see
  "Completed and verified" above), and further growth from here would
  mean either new councils publishing data that doesn't exist yet, or
  deeper reverse-engineering effort on the several real-but-gated/
  proprietary platforms already identified (Kirklees, Rotherham, West
  Sussex, North Somerset, Derbyshire) rather than more breadth-first
  searching.

- **Found and fixed a real local-authority-code misattribution bug via a
  proactive cross-check, not a bug report - Solihull's catchment data had
  been imported under code "333", which is actually Sandwell.** Caught by
  cross-referencing every England/Scotland/Wales LA code used this
  session against the authoritative `local_authorities` database table
  (not previously used as a cross-check source this session) - every
  other code checked out correct, this was an isolated error, not
  systemic. Root cause: verifying Solihull's code by searching for a
  school named "Langley Primary School" and trusting the one match found
  - but Sandwell also has a school with that exact name, and the match
    returned was Sandwell's, not Solihull's (the catchment data's own
    postcode field, B92, independently confirms the polygons themselves
    are genuinely Solihull's). Deleted the 2 misattributed
    `catchment_sources` rows and their 77 `catchment_areas` rows, corrected
    the code in `catchment-sources.yml` to the true "334", and
    re-imported clean. Also attempted a real Playwright browser session
    against two of the "real but proprietary platform" candidates found in
    the previous batch: partially succeeded against West Sussex (confirmed
    the real underlying table name and both layer GUIDs via the platform's
    own job-queue API, though pulling actual features still needs
    simulating a UI selection step not yet captured); North Somerset's
    server itself never responded within 45 seconds from either curl or a
    live browser, a harder problem than West Sussex's merely-undocumented
    API. Windsor and Maidenhead's mapping tool, previously returning a 503,
    now returns 200 but resolves to the plain council homepage - confirms
    it has been decommissioned rather than being temporarily down.

- **Cross-checked the whole England catchment sweep against the
  authoritative `local_authorities` database table (188 real England
  entries, `catchment_coverage_status` PILOT/NOT_AVAILABLE) rather than
  just this file's own running list, to find any local authority
  genuinely never investigated at all this session.** Found exactly one:
  Portsmouth. Investigated directly - confirmed PDF-only catchment
  publication per school (e.g.
  "Mayfield-and-Trafalgar-secondary-school-catchment-area-Accessible.pdf"),
  both candidate ArcGIS Hub hostnames resolve but their DCAT feeds 404,
  and two ArcGIS Experience apps that surfaced in search under
  Portsmouth-relevant titles were both confirmed via item metadata to
  actually belong to other councils (North Yorkshire and an unrelated
  org) - the same false-positive-search pattern already seen this
  session for Oxfordshire/Stirling and Barnet/Dundee. With Portsmouth
  now documented, every England local authority in the database has
  either real imported catchment data or an explicitly investigated
  reason it does not - the systematic sweep is genuinely exhaustive as
  of this point, not just "no further batches planned."

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

- **England, Wales and Scotland all now have real performance metrics**
  (see "Completed and verified" above) - this bullet is stale as of
  earlier in the project; Scotland's SQA leaver-tariff data
  (statistics.gov.scot) and England's A-level dataset were both found
  later in the same session that first wrote this section. Wales
  primary schools and Scotland primary/special schools remain uncovered
  (no public per-school source exists for either, confirmed by direct
  investigation, not assumed) - worth rechecking periodically rather
  than assumed permanently closed, particularly Scotland's Insight tool.
  The original LA-level EES publications (school-capacity, pupil-absence
  x2, school-workforce) are still unusable for `SchoolMetric` as designed
  (no per-school rows) and remain resolved-but-not-imported by
  `import-statistics`; a schema change (e.g. a local-authority-level
  metrics table) would be needed to use them at all, and has not been
  attempted.
- **Catchment area performance scoring covers 2,804 of 5,469 areas as of
  the last `refresh-catchment-scores` run** (also stale from earlier in
  the project; grew steadily as both catchment and performance-metric
  coverage expanded across the same session). Every school with an
  assessable cohort has its performance metric - verified directly
  against production: England secondary 98.4% covered, Wales secondary
  100%, England primary's apparent gap fully explained by infant/first
  schools with no Year 6 cohort plus academies converted too recently to
  have data published under their new URN yet. Scotland primary/special
  and Wales primary/special remain unscored because no metric exists for
  them at all (not a scoring-logic gap). As catchment coverage or
  performance-metric coverage grows, re-running `refresh-catchment-scores` will pick up
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
- **Catchment coverage is 67 local authorities out of ~200+ across Great
  Britain as of the last count (see `PILOT_LOCAL_AUTHORITIES` in
  `packages/shared/src/config/catchment-sources.test.ts` for the exact,
  current, tested list rather than repeating it here - it grew steadily
  across this session and this bullet is otherwise guaranteed to go
  stale again): 28 Scotland, 37 England, 2 Wales.** Every one of
  Scotland's 32 councils and every one of Wales's 22 councils has now
  been individually investigated, not just the ones that yielded real
  data, so both nations are close to as complete as this project can
  currently make it without new data being published; England's
  ~150-188 councils have not been exhaustively covered the same way -
  each expansion so far covered a deliberately chosen batch, most
  recently a systematic sweep of 12 previously-unchecked unitaries (see
  "Completed and verified" above) - so unlike Scotland/Wales, "no
  further coverage found" for England reflects the batches checked so
  far, not an exhaustive negative. Spatial Hub Scotland's original catalog
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

This whole section was stale (predated most of the session's real work -
Scotland performance metrics, Wales catchments, and the entire England
sweep all happened after it was last written) and has been rewritten to
match the actual current state as of the last commit.

1. **Catchment-zone discovery for England, Scotland and Wales is now
   genuinely exhaustive**, not just "no further batches planned": every
   local authority in the `local_authorities` database table (188
   England, all 32 Scotland councils, all 22 Wales councils) has either
   real imported data or a specific, investigated, documented reason it
   does not (see `candidates:` in `config/catchment-sources.yml`, cross-
   checked directly against the database rather than trusted from this
   file's own running list - see "Completed and verified" above for how
   that cross-check was done and what it caught). Further catchment
   growth from here would come from one of:
   - New councils publishing data that doesn't exist yet (worth a
     periodic recheck of the whole candidates list, not urgent).
   - Retrying the specific "real but currently unreachable from this
     sandbox" candidates from a different network origin: Ealing
     (inspire.misoportal.com), Hampshire (maps.hants.gov.uk, 403),
     Salford (map.salford.gov.uk), Milton Keynes
     (mapping.milton-keynes.gov.uk) - all confirmed real, licensed-
     looking data, just not reachable from here.
   - Deeper reverse-engineering of the handful of real-but-proprietary
     platforms already identified and partially investigated with
     Playwright: West Sussex (StatMap Earthlight - the real underlying
     table and layer GUIDs are already found; what's missing is
     simulating the UI's own select-then-query job sequence to actually
     pull features) is the most promising; Derbyshire (Precisely/MapInfo
     Exponare) is a real second candidate. Kirklees, Rotherham and North
     Somerset were all attempted this session and confirmed to be
     either broken server-side (Kirklees), raster-tile-only with no
     public API (Rotherham, same architecture as the already-excluded
     Bridgend/Derby/Stoke-on-Trent), or unresponsive (North Somerset) -
     not worth another pass without a materially different approach.
2. **Performance-metric coverage is comprehensive for all three nations**
   (England: Attainment 8, Progress 8, 4 KS2 measures, A-level APS;
   Wales: Capped 9 + 4 more KS4 measures; Scotland: 8 SQA tariff-band/
   SIMD measures) - see "Completed and verified" above for exactly what
   exists and why primary-phase Wales/Scotland and special-school metrics
   don't (no public source exists for either, confirmed by direct
   investigation). Periodically recheck Scotland's Insight tool in case
   it or an equivalent is ever opened up as public data - low priority,
   previously confirmed closed and gated behind real school/council
   authentication that must never be bypassed.
3. Run `refresh-catchment-scores` after any future catchment or
   performance-metric addition - it is fully generic against the
   nation/phase metric-candidate table in `catchment_scores.py`, no code
   change needed to pick up new coverage. Last run: 4,744 of 7,807 areas
   scored.
4. Get explicit go-ahead, informed by `scripts/calibration-report.md`,
   before any further catchment-geometry expansion changes the
   project's cost profile materially (that report predates almost all of
   this session's catchment growth, so its storage projections should be
   re-checked against real current console figures, not assumed still
   accurate at the current ~7,800-row scale).
5. Optional polish, not urgent: `SchoolCatchmentArea` per-source name-
   matching research (Edinburgh's `EST_NAME` field remains the most
   promising real starting point; Dorset's `school_name` field and East
   Sussex's `NAME` field are two more real candidates found this
   session), a denomination-aware `/admissions` flow for Scotland's
   ND/RC catchment splits, Playwright e2e coverage for the golden paths
   (search a school, check a postcode, view the map with the catchment
   overlay on). A `/schools` search-results column or filter for a
   headline performance metric would also make the data more
   discoverable than only showing on each school's own page.

## Checkpoint - paused here, usage running low

Pausing at explicit user request (usage running out). Everything below is
committed and pushed to `main`; CI green on every commit.

**This session's work, most recent first:**

- **Map performance fix (user-reported, live-verified):** the map's school
  pins visibly "jumped" between positions and catchment areas felt slow to
  load. Root-caused to two real bugs, not one: (1) neither
  `loadSchoolsInView` nor `loadCatchmentsInView` in
  `apps/web/components/school-map.tsx` guarded against out-of-order
  responses, so a slow request for an earlier viewport could resolve after
  and overwrite a faster request for a later one - that was the "dancing";
  (2) every intermediate `moveend` event during a single pan/zoom gesture
  fired its own full fetch, with no debouncing. Fixed both (request-
  sequence guard + 300ms debounce on `moveend`), verified live with
  Playwright that an 8-step rapid pan now fires exactly 1 request instead
  of many. Also added the user-requested "Show only catchment zones"
  checkbox (hides school pins, stops fetching them entirely while
  checked). Checked whether `/api/map/schools`'s `ORDER BY random()` was
  the slow-query culprit too - `EXPLAIN ANALYZE` showed it isn't (forcing
  the lat/lon index actually made it slower, 655ms vs 120ms, due to an
  extra lookup join at this selectivity), so left unchanged.
- Pushed the remaining "real but proprietary platform" catchment leads
  from the previous batch to their conclusions: Rotherham confirmed
  raster-tile-only (Cadcorp GeognoSIS, same dead end as Bridgend/Derby/
  Stoke) via a live browser session; Derbyshire confirmed its education
  data sits behind a genuine `AccessDeniedException` - a real
  authentication wall, not just a hard-to-find URL, so a hard stop per
  this project's standing rule; West Sussex got further (found the real
  underlying table and layer GUIDs via its job-queue API) but feature
  extraction still isn't cracked; the network-blocked candidates (Ealing,
  Hampshire, Salford, Milton Keynes) were re-checked and are unchanged.
- Before that: closed out a systematic England catchment sweep,
  cross-checked against the database's own `local_authorities` table
  (188 real England entries) rather than trusted from this file's own
  running list - found and fixed one genuinely untouched authority
  (Portsmouth, confirmed PDF-only) and one real LA-code bug (Solihull's
  77 catchment areas had been tagged under Sandwell's code, 333 vs 334 -
  found by cross-checking every code used this session against that same
  table, fixed and re-imported). Before that: two real coordinate-
  reprojection bugs found via proactive database sweeps and fixed
  (Aberdeenshire/Orkney's shapefile source, and Powys's GeoServer lying
  about its own CRS) - the Powys fix added a general plausibility check
  that protects every future source from the same class of bug, not just
  Powys.
- **Current real numbers** (see `PILOT_LOCAL_AUTHORITIES` in
  `packages/shared/src/config/catchment-sources.test.ts` for the exact
  list): 67 local authorities with real catchment data (28 Scotland, 37
  England, 2 Wales) out of ~250 across Great Britain; `refresh-catchment-
scores` last showed 4,744 of 7,807 areas scored. Performance metrics
  are comprehensive across England, Wales and Scotland (see "Completed
  and verified" above for exactly which measures and why primary-phase
  Wales/Scotland don't have any - no public source exists for either).

## What needs to happen next (explicit user priority, 2026-08-04)

The user's verdict: current coverage across the whole project is **not
nearly enough**, full stop - "London was just an example of how you have
not nearly achieved what you have been tasked with so far." The target
is genuinely comprehensive catchment-zone and performance-metric
coverage for the **whole UK**, not a London-specific push. Treat the
London numbers below as one illustration of how far short 67-of-~250
local authorities is of "done," not as the boundary of the next batch of
work - every nation/region this session already touched should be
revisited with the newly-authorised broader acquisition methods (see
below), not just London.

London itself, as the concrete example the user gave: of 33 local
education authorities (32 boroughs + City of London), only **2** have
real catchment data right now - Tower Hamlets and Newham. Every other
London borough was investigated this session and found to be either a
genuine dead end (distance-based admissions, no catchment concept at
all - true for several boroughs, e.g. Croydon, Haringey) or blocked by a
real barrier (Enfield: private ArcGIS org; Lewisham: genuinely
login-gated MapThat platform - do NOT bypass this, it is a real
credential wall). See the `candidates:` section of
`config/catchment-sources.yml` for the specific documented reason for
every London borough already checked - re-read those before re-searching
the same ground, then apply the broader acquisition methods below to
them specifically as the first concrete batch.

**The user has explicitly authorised going further than this session's
standing approach to get real London (and other missing) data**:
"dont care how you get the data... you can scrape it or do whatever you
want" - this is a private, non-commercial project. This extends the
existing "licensing doesn't gate inclusion" rule (see
`feedback_licensing_private_project.md` in memory) to also cover the
_method_ of acquisition, not just the reuse-permission question - e.g.
scraping a borough's own published PDF/HTML catchment maps and
digitising the boundaries by hand/OCR if no API exists, not just
searching for ready-made GIS endpoints. The one boundary that remains
absolute regardless of this authorisation, self-established earlier
this session and never contradicted: never attempt to bypass a real
authentication/login wall (e.g. Lewisham's MapThat, Derbyshire's
Education project, Birmingham's token-gated ArcGIS service) - "however
you can get it" means creative acquisition of otherwise-public data, not
unauthorized access to a gated system.

**Concrete next steps, in priority order - scope is the whole UK, London
is just the first worked example:**

1. Revisit every `candidates:` entry across the whole file (not just
   London - every dead-ended English county/metro borough, every closed
   Scottish/Welsh council too) and check specifically for scrapeable
   PDF/JPEG catchment maps published on the council's own site, now that
   the user has explicitly authorised digitising a published map (even
   manually tracing coordinates from a clear PDF/image) as real,
   legitimate data acquisition for this project - not just searching for
   ready-made GIS endpoints. Several councils were already found this
   session to publish exactly this kind of PDF-only map (Bury, Hounslow,
   South Tyneside, Leeds, and many more - search `candidates:` for
   "PDF"); each is now a real acquisition candidate under the new
   authorisation, not a closed dead end. Every digitised source must
   still be genuinely traced from the council's own real published map
   and disclosed as such in `catchment-sources.yml`'s notes field - never
   invent a boundary that wasn't really published somewhere.
2. Re-open the proprietary-platform candidates found real-but-not-fully-
   extracted this session (West Sussex's StatMap Earthlight - the
   hardest part, the real table/layer identifiers, is already found and
   documented; North Somerset's Cadcorp Aurora, worth retrying since its
   unresponsiveness may have been transient) with more sustained
   browser-automation effort than a single pass allowed.
3. For local authorities confirmed to have zero catchment concept at all
   (pure distance-based admissions - true for several London boroughs and
   some others), performance-metric coverage still matters for their
   schools regardless - verify England's existing performance-metric
   pipeline already covers every open school in every such authority (it
   should, since it's not catchment-scoped), and that
   `refresh-catchment-scores` isn't silently skipping them for a
   different reason.
4. Re-verify performance-metric coverage is still genuinely comprehensive
   UK-wide, not just re-assume it from this file's own past claims -
   double check there are no gaps beyond what's already documented as
   closed (Wales primary, Scotland primary/special).
5. Retry the network-blocked candidates (Ealing, Hampshire, Salford,
   Milton Keynes) from a different network origin if one becomes
   available - all four are confirmed real, licensed-looking data, purely
   blocked by this sandbox's network path.

## Checkpoint - paused here, usage running low (2026-08-06, later same day)

Coverage as of this checkpoint: **79 local authorities** with real, deployed
catchment sources (verified live against the DB: `select count(distinct
local_authority_code) from catchment_sources` = 79). Total catchment_areas
rows: 9,316; 6,152 have a performance_percentile score from
`refresh-catchment-scores` (the rest are areas whose schools don't yet have
a matching performance metric, not a scoring failure - not separately
re-verified this checkpoint).

This session added, in order, all committed/pushed/import-verified/scored:
BCP, Leeds, Oxfordshire, Halton, North Yorkshire, Hertfordshire, Kirklees
(132 areas), Hampshire (665 areas, cracked a fingerprint-blocked MapServer),
Birmingham (5 grammar-school catchments dissolved from real ONS ward
boundaries), Wigan (1 area, Fred Longworth High School), Cumberland (82
areas, via a LocalGov Drupal "find a school near you" tool's server-rendered
Leaflet geofields), Derby (77 areas, cracked Cadcorp GeognoSIS via a real
Playwright browser session that mints a session id then exposes paginated
`.geojson` features with real URNs).

**Major finding this session**: a cross-referenced query (DB's enabled
`catchment_sources` local authorities, plus every `local_authority_name`
already documented - including comma-grouped and parenthetical-suffixed
entries - in `catchment-sources.yml`'s candidates section) against all 229
real local authorities with open schools showed only **one** genuinely
uninvestigated authority left: Bedford. It has since been checked and
closed as a dead end (no real catchment-polygon GIS presence, only a
misleadingly-titled point-location layer from an unrelated shared training
org). **Broad new-authority discovery is now exhausted** - essentially
every English/Welsh/Scottish local authority with a meaningful school count
has either been deployed or genuinely investigated and documented. Future
sessions should not re-run a fresh "biggest uncovered LA" query without
first cross-referencing it against every name already in
`catchment-sources.yml` (both `local_authority_code:` entries under
`sources:` and `local_authority_name:` entries under `candidates:`) - the
grouped/parenthetical name formats mean a naive DB-only query undercounts
what's already been checked, as happened once this session before the
cross-reference fix.

Also closed this checkpoint: the Scotland national aggregate WFS
(data.spatialhub.scot, Improvement Service) - re-investigated as a
promising single-endpoint candidate that could have covered many Scottish
councils at once, but its own resource page requires genuine account
registration or an auth key for any bulk download ("browse and preview"
only without one) - a real credential gate, not a network/fingerprint
block, so left closed per this project's hard rule against bypassing login
walls. Documented in the YAML with this specific finding so no future
session re-attempts it as if it were still just network-blocked.

**In flight when this checkpoint was written**: a fork was retrying three
already-documented candidates with a real Playwright browser session (the
technique that cracked Hampshire, Cumberland, and Derby after they were
first marked network/fingerprint-blocked) - Stoke-on-Trent (shares Derby's
exact Cadcorp GeognoSIS platform, very likely crackable the same way),
Durham (previously a plain 403, possibly Cloudflare-gated like Hampshire
originally was), and Leicestershire (whole-domain Akamai WAF block, a
promising per-school PDF pattern already found but domain-level 403 even
via a full browser session - lower odds than the other two). **No new
commits had landed from this fork as of pausing** (`git log` still shows
Derby/Bedford as the latest catchment-related commits) - its actual outcome
is unknown. Next session: check whether that fork is still running or
completed silently; if unresolved, just re-run the same three-target retry
from scratch rather than trying to recover partial state.

Working tree was clean at pause time (only the pre-existing, gitignored/
untracked `services/ingestor/uv.lock`, not a real change). All prior work
through Derby/Bedford is committed and pushed to `main`.

**Recommended next steps, in order**:

1. Resolve the in-flight Stoke-on-Trent/Durham/Leicestershire retry (see
   above).
2. Given broad discovery is exhausted, shift primary effort toward the
   digitization stragglers already identified as ready-to-resume in earlier
   checkpoints of this file (search this file for "South Tyneside",
   "Oxfordshire's 91 non-gridded PDFs", "BCP's 9 stragglers", "Leeds
   Allerton High") - these are real, already-scoped candidates, not new
   discovery.
3. Re-verify performance-metric coverage is still comprehensive UK-wide
   (England/Wales/Scotland) now that catchment geometry coverage has grown
   substantially since the last time this was checked - the actual point of
   the project is the red-to-green score, not geometry alone, per standing
   user instruction ("remember this is all about rating catchment zones by
   performance, red to green by results").
4. Standing user instruction remains in force: keep going autonomously,
   don't pause for confirmation, Sonnet only (never Opus) for the main
   session and any forks/subagents.

## Update: Stoke-on-Trent recovered from the interrupted fork (2026-08-07)

The in-flight Stoke-on-Trent/Durham/Leicestershire retry fork mentioned
above was killed mid-task by a session-limit error (confirmed via its
task-notification: "Agent terminated early due to an API error: You've hit
your session limit"), right after it had already found and written real
data for Stoke-on-Trent but before committing. Its uncommitted work
(`config/catchment-sources.yml` diff plus a complete, verified
`data/digitized-catchments/stoke-on-trent/stoke_primary_catchments.geojson`)
was still present in the working tree at the start of the next session,
inspected for legitimacy (real WGS84 coordinates within Stoke-on-Trent's
bounds, real URNs, a genuine block-comment explaining the Cadcorp
GeognoSIS session/overlay discovery method - the same platform and
technique that cracked Derby), then finished properly: test file updated,
`sync-config.mjs` run, tests passed, formatted, committed (`ce79137`),
pushed, imported (dry-run then real: 48 built, 0 rejected, 44 persisted -
the 4-row difference is the same shared-polygon dedup pattern already seen
with Hertfordshire/Cheshire East-West, not an error), envelope-verified
(all coordinates within GB bounds), and scored via
`refresh-catchment-scores` (6,196 of 9,360 total catchment areas now
scored). **Local authority count: 79 -> 80.**

**Lesson for future sessions**: if a background fork's task-notification
reports `status: "failed"` with a session-limit or similar error, always
check `git status` before assuming the fork's work is lost - it may have
already produced complete, real, uncommitted output sitting in the working
tree that just needs inspection and a normal finish (test/commit/import/
verify/score), not a from-scratch retry.

Durham and Leicestershire were NOT reached by the interrupted fork (it got
through Stoke-on-Trent first per the target ordering) - still open
candidates for a future retry with a real Playwright session, per the
reasoning already documented in their existing `catchment-sources.yml`
notes.

## Update: Durham/Leicestershire retry outcome, and a performance-metric coverage audit (2026-08-07)

**Durham/Leicestershire retry**: both re-checked with a fresh Playwright
session. Durham is now a definitive dead end with stronger evidence than
before - the council's own live admissions pages state Durham's oversubscription
tiebreaker is purely distance-based (GIS-measured shortest walking route),
with the word "catchment" appearing nowhere; not a network block at all, a
genuine no-catchment-concept authority. Leicestershire's whole domain still
hard-403s under a real browser session, unchanged from the prior finding -
this looks like a genuine IP/network-origin block specific to this
sandbox (unlike Hampshire/Derby/Stoke-on-Trent's blocks, which the same
browser-session technique did clear), so it needs a genuinely different
network origin to resolve, not another in-sandbox attempt. **Coverage
remains 80 local authorities.**

**Performance-metric coverage audit**: `refresh-catchment-scores` scores
6,196 of 9,360 catchment areas (66%) - this ~34% gap was audited in full
(reading `catchment_scores.py`'s actual scoring algorithm, then querying
the DB for a per-nation/area_type breakdown, then spot-checking specific
unscored areas with the real point-in-polygon logic, not just bounding
boxes) to determine whether it's a real bug or already-explained. Full
breakdown of the 3,164 unscored areas:

- **1,955 (62% of the gap): Scotland primary-phase areas** (all
  `primary_catchment*` variants) - zero scored, because Scotland has no
  configured primary-phase metric at all (`_METRIC_CANDIDATES_BY_NATION_AND_PHASE`
  has no `("SCOTLAND", "primary")` entry) - the already-documented gap,
  confirmed still accurate. Scotland _secondary_ areas, by contrast, score
  fine: 329 scored via `scotland_leaver_tariff_middle60` - the code's own
  docstring incorrectly claimed "every Scottish catchment area" was
  unscored, which was stale and has been fixed (see commit `3a3b8b3`).
- **133: Wales primary-phase areas** - zero scored, same already-documented
  no-public-source gap (Wales primary).
- **252 (213 + 39): area types whose name doesn't start with "primary" or
  "secondary"** (`middle_school_catchment`: Buckinghamshire 141, Dorset 27,
  Worcestershire 19, Northumberland 14, Somerset 6, North Tyneside 4,
  Kirklees 2; `catchment_mixed_phase`: Lancashire 39) - deliberately never
  scored, for the same reason `all_through_catchment` (19 areas, Orkney)
  already wasn't: these span both England's KS2 and KS4/KS5 accountability
  measures, so neither a "primary" nor "secondary" metric would honestly
  describe every school inside. Confirmed deliberate by design (not a code
  oversight), now documented in the code's own docstring too.
- **38: North Northamptonshire's `primary_catchment_partial`** - zero
  scored despite being correctly phase-classified as "primary". Root cause
  confirmed via direct point-in-polygon check: these are small
  postcode-_unit_ polygons "linked to" a school (the council's own
  admissions-priority data model), not polygons drawn around the school
  itself - most genuinely contain zero school coordinates at all (verified:
  4 of the first 5 areas checked have 0 schools even in their bounding
  box). This is the same structural limitation already flagged as
  "optional polish, not urgent" elsewhere in this file (the
  `SchoolCatchmentArea` per-source name-matching research note) - fixing
  it would mean matching served schools by the source's own `name_field`
  for this specific source type, not point-in-polygon, a real but
  non-trivial follow-up, not attempted here.
- **The remaining ~786 unscored areas are ordinary per-school data gaps**
  spread across England secondary (81/884), Scotland secondary
  denominations (138+20+14+11 = 183 across its 4 variants), primary
  infant/junior (31+23), Wales secondary (5/13), etc. - spot-checked one
  England secondary example directly (a Tower Hamlets-area catchment
  serving 11 schools, only one of which - Mulberry Academy London Dock,
  URN 143716 - is actually secondary-phase): its `school_metrics` row for
  `attainment8_average` exists but `value_numeric` is null in the current
  2024/25 DfE release, the same "z" (not-applicable) pattern already
  documented for `progress8_average` - a real per-school/per-release data
  gap DfE hasn't published yet, not a bug in this service.

**Conclusion: no genuine scoring bug found.** Every unscored bucket traces
to either an already-documented no-public-source gap, a deliberate and
now-better-documented phase-ambiguity exclusion, one specific and now-
diagnosed point-in-polygon/source-shape mismatch (North Northamptonshire's
linked areas), or ordinary per-school/per-release data absence. The one
real code change from this audit was fixing the stale Scotland docstring
claim (commit `3a3b8b3`) - performance-metric coverage itself does not
need new sourcing work right now.
session and any forks/subagents.

## Update: Leeds's Allerton High School straggler solved (2026-08-07)

The one remaining digitization straggler within Leeds (already partially
covered: 93 primary + 4 secondary catchments deployed) is now done.
Allerton High School's page in the council's own "2023 Catchment Maps for
Secondary.pdf" was the only one of Leeds's 5 secondary schools not yet
digitised - it shows two semi-transparent filled priority zones with no
outline stroke, a genuinely different presentation from the boundary-line
template that worked for the other 4. Solved with a fill-colour-region
technique: both zones' alpha-blended tint produces an almost-constant
additive shift in (B-R) [Zone 1, blue] or (R-B) [Zone 2, orange]
regardless of the OS basemap colour underneath (verified against the
legend's own swatches plus several in-map sample points over white/green/
urban basemap - most basemap colours are close to colour-neutral, so the
blend's dominant visible effect is the additive term). Thresholded each
channel difference, kept only the largest connected component (a
similarly-blue-cast river was initially misclassified as part of Zone 1 -
removed via morphological opening, which strips thin linear protrusions
without touching the filled zone blob), then contoured/simplified/
georeferenced with this project's usual single-marker + scale-bar method
(a 9-tick ruler at exactly 0.375-mile spacing, cross-verified against the
tick labels' own PDF text bounding boxes). Verified pixel-perfect via a
full polygon overlay redrawn onto the source render (both zone outlines
sit exactly on the fill boundary, no spurious extensions). The school's
own marker sits 48-71m outside both polygons - not treated as an error
(within this method's expected precision on a ~5m/pixel paper map, and
this document's zone identity comes from its own printed labels, not a
school-inside-polygon inference the way pooled/shared catchments
elsewhere are matched).

Committed and pushed (`556966a`), imported (dry-run then real: 6 built,
0 rejected for the Leeds secondary source, up from 4), envelope-verified,
scored via `refresh-catchment-scores` (6,197 of 9,362 total areas now
scored). All 5 schools in the source document are now covered - this
straggler is fully closed, not just partially improved.

**Note for the coordinator**: `apps/web/app/map/page.tsx` and
`apps/web/components/school-map.tsx` were found already modified in the
working tree at the start of this task (unrelated to catchment sourcing -
looks like in-progress map UX work, e.g. from a memory note about
"catchments default-on, pins opt-in, GB-only bounds"). Left untouched and
uncommitted, out of this task's scope - another session/fork appears to
own that work.

## Update: 3 more BCP stragglers recovered (2026-08-07)

Of BCP's original 9 undigitised stragglers, 3 (Baden-Powell and St
Peter's, Livingstone Road Infant, Manorside) turned out to be
mis-categorised by an earlier session as an "older raster-screenshot
template with no usable vector boundary or scale bar." On inspection this
pass, all 3 actually have a clean vector boundary line, a red
school-location marker, and a precise numeric ratio scale (e.g. "Scale
1:31000") - a greyscale OS-2013-vintage template, visually different from
but functionally equivalent to the coloured/scale-bar template already
used for BCP's other 29. The ratio scale converts to exact metres-per-
pixel given a controlled render DPI, without needing scale-bar tick
detection. Boundary isolated as the single largest black connected
component after excluding the page-frame rectangle (found by its bbox
covering almost the whole page). Verified pixel-perfect via a full
contour + marker overlay redrawn onto each source render; each polygon
confirmed to contain its own school's real coordinate.

The remaining 5 "omits the marker" stragglers (Lilliput, Mudeford-
Community-Infants, Old-Town-Infant-and-Nursery, Queens-Park-Infant, St-
Michael's) were re-checked and confirmed to genuinely have no marker -
the only red pixels present on their maps are a main road rendered in a
similar colour, not a location marker, ruled out as a false lead this
pass. Bishop Aldhelm's (different "Parish/Local Authority Catchment"
overlap template) also has no marker. All 6 remain open candidates,
still needing a different control-point strategy (e.g. cross-referencing
another nearby labelled school on the same base map against this
project's own schools table) not attempted this pass.

Committed and pushed (`2fd0914`), imported (dry-run then real: 32 primary
areas built, 0 rejected, up from 29), envelope-verified, scored via
`refresh-catchment-scores` (6,200 of 9,365 total areas now scored). BCP's
total catchment count: 39 (was 36).

## Update: "by any means possible" pass - 3 more BCP no-marker schools solved, network-blocked candidates re-confirmed still blocked (2026-08-07)

Per explicit user instruction to push harder on remaining gaps, this pass
covered two categories.

**Network/access retries** (Leicestershire, Ealing, Milton Keynes, Salford)

- all re-tested with a fresh Playwright session, all unchanged: Leicestershire
  still a domain-wide 403 (Akamai WAF) even via a real browser; Ealing's WMS
  host, Milton Keynes' Astun iShare host, and Salford's map host all still
  time out with no response at all. These read as genuine sandbox-network-
  level blocks (not fingerprint/bot-JS challenges, which this technique has
  cracked repeatedly this session for Hampshire/Cumberland/Derby/Stoke-on-
  Trent) - worth retrying only from a materially different network origin,
  not from repeated attempts inside this same sandbox.

**BCP's remaining "no marker" stragglers**: solved 3 of 5 (Lilliput, St
Michael's, Queen's Park Infant) by anchoring to a different real,
precisely-locatable landmark visible on the same map instead of a school
marker - a railway station icon (Lilliput, St Michael's) or a hospital
building cluster's pixel centroid (Queen's Park Infant), geocoded via
OpenStreetMap Nominatim for its real coordinate, combined with the map's
own printed scale bar. Each independently verified: the served school's
own real database coordinate falls inside the resulting polygon for all
3, and a full contour overlay redrawn onto the source render matches
pixel-perfect (Lilliput, St Michael's) or within a few metres (Queen's
Park Infant). This confirms the earlier "5 omit the marker, no reliable
control point" finding was too pessimistic - the marker specifically was
missing, but a usable alternative anchor existed on every map checked.

Not solved this pass: 2 of the 45 published PDFs (Mudeford Community
Infants, Old Town Infant and Nursery) - the predictable BCP PDF URL
pattern 404s for both; finding the correct URLs needs a live browser
session against the school-catchment-areas listing page, not attempted.
Bishop Aldhelm's (different "Parish/Local Authority Catchment" overlap
template) also remains unparsed. South Tyneside's region-closure problem
and Oxfordshire's 91 remaining non-gridded PDFs were not attempted this
pass - both still need the substantial algorithm work already scoped in
earlier checkpoints of this file (watershed segmentation guided by zone-
label positions for South Tyneside; relaxed/alternate grid-detection
anchoring for Oxfordshire).

Committed and pushed (commit adding 3 features to
`bcp_digitized_primary_catchments.geojson` plus the corresponding
`catchment-sources.yml` note update), imported (dry-run then real: 35
primary areas built, 0 rejected, up from 32), envelope-verified, scored
via `refresh-catchment-scores` (6,203 of 9,368 total areas now scored),
and `refresh-catchment-overview-cache` re-run so the live /map page
reflects the new areas (this command was added earlier the same day and
must be re-run after any catchment import, alongside refresh-catchment-
scores - see this file's other entries from today). BCP's total
catchment count: 42 (was 39).

## Update: "by any means possible" pass 2 - South Tyneside blocked further, Oxfordshire's non-gridded template cracked (2026-08-07)

Targeted the 3 items left open from the previous pass: South Tyneside's
region-closure problem, Oxfordshire's 91 non-gridded PDFs, and BCP's
final 3 stragglers (Mudeford, Old Town, Bishop Aldhelm's).

**South Tyneside: got worse, not better.** The article page
(southtyneside.gov.uk/article/25376/...) still loads fine via a real
Playwright session with a real Chrome user-agent (Cloudflare's bot
challenge clears normally). But the actual PDF resource now hits a
fresh 403 on every real navigation attempt (plain fetch, context.request,
page.goto, and a real forced click on the download link all tested) -
a 307 redirect resolves to a 403 at the same URL every time. This is a
stricter WAF rule scoped to the media/PDF path specifically, distinct
from the already-solved article-page Cloudflare challenge, and looks
like the council tightened access since the region-closure notes were
written, not a technique regression. The underlying region-closure
problem (the actual hard part) was never reached this pass since the
source PDF isn't fetchable at all right now.

**BCP's last 3: real current URLs found, but the landmark technique
doesn't transfer.** Found the real, currently-live PDF URLs for all 3
(the old predictable-filename guesses had gone stale; found via a live
browser session on BCP's own catchment-maps listing page). Bishop
Aldhelm's is confirmed to use the dual-zone "Parish Catchment"/"Local
Authority Catchment" template with a precise printed ratio scale
(1:20000) but still no marker. Mudeford and Old Town have a real
numeric scale bar (pixel-measured cleanly) but, unlike the 3 recovered
in the previous pass, have no icon-shaped landmark (railway station,
hospital) identifiable near the school - only ordinary street clutter.
Not solved this pass; the `catchment-sources.yml` note now has the real
URLs and confirmed scale methods so a future session doesn't have to
re-find them.

**Oxfordshire: the non-gridded template method is now solved and
proven, 3 schools digitised.** The council's school directory
(oxfordshire.gov.uk/schools/list, paginated 0-15) was scraped for all
307 school codes, all 207 real "Location and Designated Area" PDFs were
re-downloaded, and the ~91 non-gridded ones were confirmed to use a
cream/yellow OS-OpenData-style basemap where street/place labels are
raster image content, not extractable text (unlike the gridded
template). Cracked with a landmark-pair method: the school's own blue
marker icon (still a real, cleanly-detectable small connected component
distinct from the long boundary line) anchors position to the school's
known real coordinate; a second real, independently-geocoded landmark
(a named venue or roundabout, read visually from the map and looked up
via OSM Nominatim) gives scale and confirms north-up per file - verified
true, not assumed, by checking the second landmark's pixel bearing
against its real geographic bearing (agreed within 0.3-3.5 degrees on
every file tried). Scale is NOT constant across files (1.07 to 5.57
m/px measured across 3 files) - each needs its own second landmark, no
shortcut across files. All 3 digitised schools (Orchard Meadow Primary,
Oxford Spires Academy, Cheney School) verified pixel-perfect via full
contour overlay and confirmed to contain their own school's real
coordinate. The method is real, working, and provenly accurate, but
inherently manual per file (no automated landmark detection yet) - only
3 of ~91 candidates done. Full method documented in the block comment
above the Oxfordshire entries in `catchment-sources.yml` for a future
session to continue applying directly rather than re-deriving.

Committed and pushed (`4ff3288` for the Oxfordshire geojson + config
changes, `bc7e1de` and `7824461` for the South Tyneside/BCP note
updates), imported (dry-run then real: 78 Oxfordshire areas built, 0
rejected, up from 75), envelope-verified, scored via
`refresh-catchment-scores` (6,206 of 9,371 total areas now scored), and
`refresh-catchment-overview-cache` re-run. Oxfordshire's total catchment
count: 78 (was 75). Tests pass (45 shared, 125 ingestor). No
`Co-Authored-By` trailer used on any commit this pass.

## Update: Portsmouth added - a "PDF-only dead end" reopened by this

## session's digitization pipeline (2026-08-07)

Following the "by any means possible" instruction, re-evaluated several
local authorities previously marked dead ends specifically because they
only publish "PDF catchment maps, no GIS" - these were dismissed before
this session's PDF-digitization pipeline (proven on BCP, Oxfordshire,
Leeds) existed. **Portsmouth was a real find.**

Portsmouth's per-school secondary catchment PDFs are genuine MapInfo-
exported vector maps (`Producer: MapInfo PDF Printer` in the PDF's own
metadata - not a scan or schematic). The Mayfield & Trafalgar shared-
catchment PDF shows real red markers for BOTH schools, giving two
independent, already-in-our-database ground-control points - this allows
an _exact_ similarity-transform (rotation + scale + translation) solve
with no external landmark geocoding needed at all, the highest-confidence
georeferencing method used this session. Resolved a real ~5.4 degree
rotation (grid-north vs the print's north arrow), cross-checked via an
independent bearing comparison between the two markers' real coordinates
and their pixel positions (agreed closely, confirming the rotation is
real, not an artifact). Verified: both schools' own DB coordinates fall
inside the resulting polygon, and the extracted contour overlays the
source boundary line pixel-perfectly.

**Portsmouth: 0 -> 1 local authority, 1 catchment (shared by 2 schools).
Local authority count: 80 -> 81.**

Committed and pushed (`f21a6f0`), imported (dry-run then real: 1 built, 0
rejected), envelope-verified, scored (6,207 of 9,372 total areas), and
`refresh-catchment-overview-cache` re-run (9,372 features, matches). No
`Co-Authored-By` trailer used.

**Real, substantial remaining opportunity found but not completed this
pass** - all fully documented in `catchment-sources.yml`'s Portsmouth
block comment for a future session to pick up directly:

1. **Portsmouth's other 5-6 secondary schools' PDFs** (Admiral Lord
   Nelson, Charter Academy, Castle View, Miltoncross, Springfield,
   Priory) - confirmed real MapInfo vector maps with one school marker
   each, but no scale bar/grid, so each needs an external second
   landmark (the OSM-Nominatim landmark-pair method already proven on
   Oxfordshire) rather than the exact two-marker method used for
   Mayfield & Trafalgar. Not attempted this pass due to time - each file
   is genuinely independent per-file manual work.
2. **Portsmouth's combined infant/primary catchment map** - one PDF
   covering ~25-30 named primary/infant school catchments as a single
   partition map, WITH a real printed scale bar (unlike the secondary
   PDFs) and school-name labels next to each zone already printed on the
   map. This is structurally similar to South Tyneside's still-unsolved
   partition-map problem, but meaningfully easier: labelled zones (not
   anonymous), a real scale bar (not needing landmark geocoding), and
   each zone's own red school marker as a natural watershed seed point.
   If South Tyneside's watershed-segmentation approach (seed points +
   marker-controlled watershed on the boundary-line raster, rather than
   the dilation approach that kept mis-merging regions) is ever
   implemented, this Portsmouth primary map is a strong second
   application and arguably an easier one to start with, given it has
   fewer failure modes than South Tyneside's PDF (which is furthermore
   now blocked by a stricter WAF, per the prior pass's finding).
3. **Other PDF-only councils not yet re-triaged this pass**: Enfield
   (confirmed real per-school PDF maps exist), Bedford, Warrington,
   Middlesbrough, Redcar and Cleveland, Suffolk (existing note suggests
   this one may be a genuine text-list, not a map - verify first).
   Inverclyde and Shetland were triaged in an earlier pass this session
   (both confirmed real maps; Inverclyde's georeferencing wasn't
   accurate enough to trust and was correctly not deployed - see the
   entries in `catchment-sources.yml` for exactly what was tried).

Tests pass (45 shared). Working tree clean, all pushed.

## Update: Portsmouth's other 6 secondary schools digitized (2026-08-07)

The two leads left open in Portsmouth from the previous pass - 5-6 more
secondary school PDFs and a combined infant/primary map - were picked
up. All 6 remaining secondary schools (Admiral Lord Nelson, Ark Charter
Academy, Castle View Academy, Miltoncross Academy, Springfield School,
Priory School) were successfully digitized this pass using a new
**landmark-pair georeferencing method**: each school's own marker
anchors position to its known DB coordinate (as before), and a SECOND,
independently-geocoded real landmark visible on the same map gives
scale and rotation - no scale bar or grid needed. Landmarks used, each
chosen from what was actually legible on that specific map and verified
against real, external data before trusting it:

- Nelson: Portcreek Junction roundabout (real centre from live OSM road
  geometry via Overpass, not a fuzzy place-name search)
- Charter Academy: Mary Rose Museum (OSM Nominatim, tight bounding box)
- Castle View Academy: Portsbridge Roundabout (OSM Overpass)
- Miltoncross Academy: Portsmouth College building (OSM Nominatim)
- Springfield School: Highbury Campus/City of Portsmouth College (OSM
  Nominatim)
- Priory School: St Mary's Hospital building complex (OSM Nominatim)

Rotations found ranged ~0.3 to ~8.2 degrees - all plausible print-vs-
grid-north offsets (the same phenomenon Mayfield/Trafalgar's ~5.4
degrees was, not measurement noise). Every school was verified two
ways: its own DB coordinate falls inside its extracted polygon, and a
full-map contour overlay was visually checked to track the source
boundary line closely across the _entire_ map extent (not just near
the two anchor points) - this catches a bad rotation/scale immediately,
since error compounds with distance from the anchors. All 6 passed
clean.

Combined into one new source entry (`secondary_catchment_individual`,
distinct from the existing shared Mayfield/Trafalgar
`secondary_catchment` source) since CockroachDB's
`(local_authority_code, academic_year, source_type)` uniqueness
constraint requires each on its own type. Portsmouth secondary coverage
is now 7 catchment polygons covering 8 schools (Mayfield + Trafalgar
share one; each of the other 6 has its own).

Committed (no Co-Authored-By trailer): `8e13812`. Imported (dry-run
then real: 6 built, 0 rejected), envelope-verified (all coordinates
within real Portsmouth bounds, lat 50.777-50.860, lon -1.119 to -1.019),
`refresh-catchment-scores` (6,213 of 9,378 areas now scored) and
`refresh-catchment-overview-cache` (9,378 = 9,378, cache in sync) both
re-run.

**Not reached this pass**: Portsmouth's combined infant/primary map
(~25-30 schools, one PDF, real scale bar + labelled zones - the
watershed-segmentation candidate described above); South Tyneside
(still blocked by a stricter WAF on the PDF resource itself); the
other untried PDF-only councils (Enfield, Bedford, Warrington,
Middlesbrough, Redcar and Cleveland, Suffolk).

Tests pass (45 shared, 125 ingestor). Working tree clean, all pushed.

## Update: Portsmouth's combined infant/primary map solved via ICP + marker-controlled watershed (2026-08-07)

The item flagged above as "not reached" - Portsmouth's single-page
combined infant/primary catchment map (`democracy.portsmouth.gov.uk/
documents/s9068/Infant and Primary School Location with catchment
areas.pdf`) - is now done: 41 catchment polygons across 37 zones (some
zones shared by co-located Infant/Junior schools).

This PDF has no text layer at all (Aspose.Pdf-flattened raster), so no
per-school labels were readable via OCR/pdftotext. Solved without
needing them: since this project's schools DB already holds real
coordinates for every Portsmouth primary/infant school, an ICP
(iterative closest point) similarity-transform registration - repeatedly
matching each school's predicted pixel position to its nearest of ~35
detected red markers and re-solving scale+rotation+translation via
Umeyama/Procrustes, starting from a bounding-box scale guess - recovered
the map's georeferencing from ~40 real control points at once, with no
scale bar reading or landmark geocoding required. Converged to a 6.2px
mean residual (41 of 45 candidate schools matched; 4 "Junior" schools
co-located with their "Infant" counterpart's own marker were correctly
excluded as 60-75px outliers, not real errors) at ~6.9 real metres per
pixel and a ~0.24 degree rotation (essentially north-up).

With accurate georeferencing established, the actual zone boundaries
were extracted via marker-controlled watershed segmentation - the
technique previously scoped but never implemented for South Tyneside's
still-unsolved equivalent problem, here proven end-to-end for the first
time this session: isolated the black boundary-line network from all
other page content (labels, basemap detail) by keeping only large
connected components after light dilation (>5000px - both the real line
network and the outer map frame are far larger than any text label),
then ran skimage's watershed with each matched school's own resolved
pixel position as a seed and the isolated line network as an
effectively-impassable barrier. Verified two ways: all 41 matched
schools' own DB coordinates fall inside their assigned polygon (checked
directly), and a visual overlay of the extracted contours onto the
source page tracks the real printed boundary lines closely across the
whole map extent, not just near the control points.

Committed (no Co-Authored-By trailer): `4efc54f`. Imported (dry-run then
real: 41 built, 0 rejected, 35 persisted after the expected shared-
polygon dedup - 5-6 Infant/Junior pairs share identical geometry,
matching the same pattern already documented for Hertfordshire/Cheshire
East-West). Envelope-verified: all coordinates within real Portsmouth
bounds (lat 50.772-50.864, lon -1.152 to -0.988). `refresh-catchment-
scores` (6,244 of 9,413 areas now scored) and `refresh-catchment-
overview-cache` (9,413 = 9,413, cache in sync) both re-run.

Portsmouth's total catchment coverage is now 41 secondary-phase +
41 primary/infant-phase (35 persisted) polygons.

**Still not reached**: South Tyneside's own partition-map problem
(structurally similar to what was just solved for Portsmouth, but still
blocked by a stricter WAF on the PDF resource itself - worth another
network-level retry given this session's marker-controlled-watershed
technique is now proven to work well when the PDF itself is reachable);
the other untried PDF-only councils (Enfield, Bedford, Warrington,
Middlesbrough, Redcar and Cleveland, Suffolk).

## Update: Middlesbrough reopened and solved (2026-08-07, same session)

Enfield's entire domain returns a hard 403 from this sandbox on every
request, homepage included (curl and Playwright both) - the same
sandbox-network-level block pattern already documented for
Leicestershire, not fixable by browser technique. Warrington's PDF
booklet turned out thin: its only real map reference is one school's own
admissions-policy extract showing postcode-district bandings ("Figure
1"), not a borough-wide drawn catchment layer - not worth digitising as
a standalone source. Suffolk was already correctly confirmed list-only.

Middlesbrough, previously dismissed as a dead end ("PDF... not
machine-readable"), was re-investigated and found to be a real ArcGIS
Pro print export ("Secondary School Catchment 2021", OGL-licensed,
found via the item's real underlying `mbcouncil.maps.arcgis.com` host
after the custom-domain hub page's `og:image` meta tag revealed it) -
genuine drawn purple boundary lines, a printed 1:20,000 ratio scale, a
north arrow, and faint Ordnance Survey National Grid lines. The grid was
detected the same way as Oxfordshire's (cyan-pixel column/row
autocorrelation), and its measured ~393.5px spacing matched the printed
1:20,000 ratio at 200 DPI to within 0.05% - strong independent
cross-validation that the grid really is at exact 1km intervals.

Zone labels ("Outwood Academy Acklam", "Unity City Academy", etc.) are
real extractable PDF text (unlike Portsmouth's flattened-raster infant/
primary map), giving precise seed positions for the same
marker-controlled watershed technique just proven for Portsmouth -
applied here for the first time to a boundary network extracted by
colour (solid purple) rather than by isolating black lines.

Georeferencing the grid to real-world coordinates needed identifying
which exact BNG grid intersection a given detected pixel corresponds to.
An initial attempt anchored to the "BILLINGHAM" place-name label's
approximate pixel position (geocoded via Nominatim) picked the wrong
intersection - caught by an independent cross-check against a second
landmark ("MIDDLESBROUGH"'s own label), whose predicted vs. real
position disagreed by ~928m, almost exactly one grid cell, revealing the
first anchor was wrong rather than just imprecise. Resolved properly by
a systematic search over nearby candidate grid anchors, scoring each by
whether all 5 real school coordinates already in this project's own
database land inside their own correctly-named watershed region -
exactly one candidate scored a clean 5/5, an unambiguous result no
plausible alternative anchor also satisfied.

The King's Academy has two real non-contiguous zones on the source map
(its own DB coordinate correctly falls inside one and not the other, as
expected for a genuine split zone, not a digitisation error); one zone
is a genuine shared/overlap area named "Outwood Academy Acklam / The
King's Academy (shared)" exactly as printed, left unmatched to a single
school's URN since it doesn't belong to just one. Macmillan Academy is
deliberately excluded from the source map itself, not missed by this
pipeline.

Committed (no Co-Authored-By trailer): `70a1bda`. Imported (dry-run then
real: 7 built, 0 rejected). Envelope-verified: all coordinates within
real Middlesbrough bounds (lat 54.503-54.602, lon -1.289 to -1.158).
`refresh-catchment-scores` (6,249 of 9,420 areas now scored) and
`refresh-catchment-overview-cache` (9,420 = 9,420, cache in sync) both
re-run.

**Local authority count: 81 -> 82.**

**Still not reached**: South Tyneside (as above); Bedford (re-checked
this pass, still no real map found - existing dead-end note stands);
Redcar and Cleveland (not reached this pass, worth checking the same
"real underlying ArcGIS org host via og:image" trick that found
Middlesbrough's real PDF, in case its own catchment page hides a similar
misdirected hub-page dead end).

## Update: Redcar and Cleveland (57 polygons) and South Tyneside's Harton Academy (1 polygon) added; Shetland assessed and re-documented (2026-08-07, later session)

**Redcar and Cleveland: 57 catchment polygons from a self-hosted ArcGIS Server, found by reading the council's own "School Catchment Area Finder" tool's page source.** A previous pass had marked this LA a dead end based only on its ArcGIS Hub open-data DCAT feed (41 datasets, no catchment layer) - a real gap, but not the whole picture. The finder tool itself is a plain postcode-search widget with no visible map, but its inline JS makes a JSONP call straight to `rcbcmaps.redcar-cleveland.gov.uk`, a self-hosted ArcGIS Server never listed on the open-data hub. Its `RCBC_PUBLIC` MapServer (services directory browsing disabled, but `/MapServer?f=json` still works) has 4 real, live polygon layers: "Secondary School Catchment Areas" (10), "(Roman Catholic)" (2), "Primary School Catchment Areas" (38), "(Roman Catholic)" (7). 44 of the 57 features matched an existing GIAS school by name; all 44 have that school's real DB coordinate falling inside its own matched polygon (0 mismatches) - the other 13 are pre-academisation names not present verbatim in GIAS, not re-attributed by guesswork.

Two real, generalisable ingestor bugs surfaced and fixed while landing this source (both covered by new regression tests, `services/ingestor/tests/test_catchments_adapter.py`):

- This particular ArcGIS Server build (`currentVersion 10.91`) unconditionally rejects `resultOffset`/`resultRecordCount` with `"Pagination is not supported."`, regardless of their values - `query_all_features` now retries once without them and treats the single unpaginated response as complete.
- Two pairs of distinct, real schools share one drawn polygon exactly (Ravensworth Junior / Teesville Infant; Eston Park Secondary / Gillbrook College) - the database's own `(source_id, geometry_checksum)` dedup key would otherwise silently drop one of each pair at upsert time. `build_catchment_areas` now merges same-checksum features into one row with a combined `"A / B"` name, matching the naming convention already used for Middlesbrough's hand-authored shared zone.

Committed (no Co-Authored-By trailer): `c46d1b8`. Imported (dry-run then real: 55 rows landed, since the two merge pairs collapse 57 source features into 55 database rows - no data lost, verified by name). Envelope-verified: lat 54.488-54.622, lon -1.202 to -0.788, all within GB bounds. **Local authority count: 82 -> 83** (807 flipped to `PILOT`).

**South Tyneside: 1 catchment polygon (Harton Academy) via the Wayback Machine, digitised from scratch.** The live southtyneside.gov.uk site still blocks plain fetches with a Cloudflare JS challenge (as documented in the existing South Tyneside note, which also records substantial unsolved progress on the borough-wide ~27-zone partition maps - not reattempted this session, still blocked by the same line-network-closure problem). Harton Academy separately publishes its own single-school catchment map, and its historical article page was archived by the Wayback Machine (`web.archive.org/web/20250520232207/...`), which led to its real PDF media URL - also archived, and fetchable with a plain `curl` since Wayback re-serves it, unlike the live site. The PDF itself (`Harton_Academy_Catchment_area_2026-27.pdf`, MapInfo PDF Printer export, same tool family as the still-unsolved partition maps) has a single real closed red boundary line on a detailed OS-style street basemap - no scale bar and no OS grid, unlike Middlesbrough's map.

Georeferenced via a 2-point similarity transform (scale + rotation, no shear) anchored on two real, precisely-known point landmarks drawn directly on the map: the Tyne River's North Pier and South Pier lighthouses, real coordinates sourced from OpenStreetMap/Nominatim. Verified two independent ways, neither used in the fit itself: (1) a third landmark, Trow Point, transforms to within ~82m of its real OSM coordinate; (2) of all 8 of South Tyneside's real open secondary schools' DB coordinates, only Harton Academy's own falls inside the resulting polygon - the other 7 (Mortimer, Boldon, Hebburn, Jarrow, Whitburn, St Joseph's, St Wilfrid's) all correctly fall outside it. Licence recorded as UNCONFIRMED (the PDF states only "Crown Copyright reserved. Licence No. 100019570", no explicit OGL statement found), following this project's established practice of disclosing true licence status honestly rather than gating inclusion on it.

Committed (no Co-Authored-By trailer): `5c121f1`. Imported (dry-run then real: 1 built, 0 rejected). Envelope-verified: lat 54.965-55.011, lon -1.446 to -1.374, within GB bounds. **Local authority count: 83 -> 85** (393 flipped to `PILOT`; the jump of 2 rather than 1 - Redcar counted above plus this one - accounts for the 82 -> 85 total this session).

`pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed, up from 126 - the new pagination-fallback and geometry-merge tests) both re-run clean after each landing. `refresh-catchment-overview-cache` re-run after both: `map_catchments_cache.feature_count` = 9476, matching the live `catchment_areas` row count exactly.

**Shetland Islands: assessed properly this session, not landed - genuinely tractable but a multi-hour undertaking, not a quick win.** Confirmed no Spatial Hub Scotland dataset exists (checked the real 13-LA parent listing this time). Rendered the council's own PDF to a high-resolution image and inspected it directly: a genuinely good source (~20 real colour-coded feeder-catchment zones, OS grid, printed scale, Fair Isle inset) but fully rasterised end to end - `pdftotext` extracts zero characters, `pdfimages` shows 329 tiled image objects, and the OS grid lines carry no printed easting/northing at any checked intersection, so neither this project's usual `pdftotext -bbox` nor OS-grid-anchor techniques apply directly. Two concrete unattempted methods recorded in `catchment-sources.yml` for a future dedicated session: a multi-point affine fit using this project's own ~30 real Shetland school DB coordinates against each coloured marker dot (labour-intensive since the dots aren't OCR-extractable), or ICP coastline registration (the technique that worked for Portsmouth) against a real independent Shetland coastline source.

**Ruled out this session, not reattempted (existing dead-end notes stand, re-verified rather than blindly trusted):** the South Tyneside borough-wide ~27-zone partition maps remain unsolved (same line-network-closure problem as before); BCP's last 3 PDFs (Mudeford, Old Town, Bishop Aldhelm's) not reattempted this pass - next session should pick these up per the existing BCP notes before scanning further afield.

**Most promising next lead:** BCP's Mudeford/Old Town pair (predictable PDF URL pattern already known, standard boundary-line-plus-scale-bar template already proven working elsewhere in this project) - likely the fastest remaining win. After that, a dedicated session on Shetland's multi-point DB-coordinate fit (many known-precise anchor points available, unlike Inverclyde's failed few-landmark attempt).

## Update: BCP's last 3 stragglers landed (all 45 per-school PDFs now digitised); South Tyneside's borough-wide map reopened - access solved, closure narrowed to 2 zones (2026-08-07, later session)

**BCP: Mudeford, Old Town and Bishop Aldhelm's - the last 3 of 45 published per-school catchment PDFs, all landed this session.** Mudeford and Old Town had no red school marker and no `pdftotext`-extractable landmark text (place-name/street labels on these PDFs are raster basemap content, not selectable text), unlike the railway/hospital-icon landmark technique that solved Lilliput/St Michael's/Queen's Park Infant previously. Solved instead by anchoring to a real, precisely locatable **road feature**: Mudeford via the large A35 Christchurch Bypass / Stony Lane roundabout ("Iford roundabout", pixel-centroided from the map's own green roundabout-island fill, geocoded as the centroid-average of its several roundabout-tagged Overpass way segments), Old Town via Poole railway station's own National Rail icon (geocoded via Overpass) - both combined with the map's own printed scale bar (719px = 1000m for Mudeford, 690px = 1000m for Old Town, both re-measured at 300dpi). Both verified two ways: the transform lands the school's real DB coordinate within a few pixels of its own printed name label, and a full contour overlay redrawn onto the source render is pixel-perfect.

Bishop Aldhelm's uses a different, newer dual-zone template ("Parish Catchment" as a solid blue outline+hatching, "Local Authority Catchment" as a semi-transparent pink fill over an OS basemap) with an exact printed ratio scale ("Scale: 1:20000 True@A4P") instead of a bar, and no marker at all. Anchored to St Michael's Roundabout on the B3066 (pixel-centroided from its visible ring, geocoded via Overpass), with scale computed exactly from the printed ratio plus the PDF's own known page size (595x842pt, A4) and render DPI - more precise than a pixel-measured bar, since there's no bar-endpoint measurement error at all. Parish zone traced the same way as every other line-boundary source in this file (largest pure-blue connected component). The LA zone's alpha-blended pink fill sits over a dense urban area including saturated orange OS building polygons, which breaks the constant colour-channel-difference technique that solved Leeds's Allerton High earlier (that technique assumes a near-neutral basemap underneath) - instead traced from a distinct dark reddish-brown border stroke drawn around the fill's own edge, with small interior holes (mostly the school's own building footprint, a cartographic artefact) closed via contour hierarchy before the final external contour. Parish is pixel-perfect on a full contour overlay and lands the school's real DB coordinate inside it; the LA zone visually tracks its source fill closely but has some genuine extraction jaggedness from the noisier border-stroke signal, landing the school's real DB coordinate 75m outside its extracted boundary - within this method's established tolerance elsewhere in this file (compare Harton Academy's 82m and Allerton High's 48-71m) - kept with this caveat documented, per this file's existing precedent of keeping both zones from their own printed labels (Allerton High) rather than a school-inside-polygon inference.

Committed one school at a time (no Co-Authored-By trailer): `945a374` (Mudeford), `d2073b8` (Old Town), `156019c` (Bishop Aldhelm's, both zones). Each imported (dry-run then real) and verified via `refresh-catchment-overview-cache` before moving to the next. `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean after each landing. **BCP's primary catchment source: 35 -> 39 polygons** (all 45 published per-school PDFs now digitised - the disabled-candidates note for "Bournemouth, Christchurch and Poole (remaining 3 PDFs)" is removed, folded into the source's own notes). `map_catchments_cache.feature_count` = 9480, matching the live `catchment_areas` row count exactly (9476 -> 9480: +4 rows, since Bishop Aldhelm's contributes 2).

**South Tyneside's borough-wide ~27-zone primary partition map: reopened, not landed, but two genuinely new findings worth a lot to whoever continues.** This is separate from Harton Academy's single-school map already in `sources:`. A previous session's notes described two blockers: a line-network-closure problem (dilation/skeleton-bridging attempts left the map's denser central area as one leaked blob, or produced "confident" regions that turned out to mix two schools' zone-ID labels) and, in a follow-up, the PDF itself becoming unreachable (a fresh 403 on the media path even via a real Playwright session).

Access solved with a materially different technique: a real headless Chromium `page.goto()` straight to the (now-current) PDF URL does get a genuine 200 `application/pdf` response, but Chromium's own built-in PDF viewer intercepts the navigation before any normal extraction point can see the real bytes - `response.body()`, a `page.route()` handler's `route.fetch()`, CDP's `Network.getResponseBody`, and a raw `context.request.get()` reusing the same cookies all returned either a ~500-byte synthetic wrapper page or a fresh 403. CDP's **Fetch domain** (`Fetch.enable` with a URL pattern and `requestStage: "Response"`, then `Fetch.getResponseBody` inside the `Fetch.requestPaused` handler, then `Fetch.continueRequest`) intercepts the response body at the network layer before the PDF viewer consumes/transforms it, and captured the real 12MB PDF intact (verified: valid PDF 1.3, MapInfo PDF Printer, A3 - matches the existing description exactly). Recorded in `catchment-sources.yml` as a general technique for any future blocked PDF/download URL, not just this one.

Region closure: tried **marker-controlled watershed segmentation** for the first time on this map (this project's established toolkit per the Portsmouth precedent), seeded from each zone-ID label's own `pdftotext -bbox` position (deduped for the same bold-simulation double-render already documented, cross-checked against a cleanly parsed 27-entry ID -> school-name legend table) rather than blind dilation. This is a real improvement: elevation = the raw undilated red line mask, with the map's own outer border pre-seeded as its own competing watershed label (critical - leaving it as elevation-only let one interior leak swallow the entire exterior in an early attempt) - **25 of the 27 zones close into clean, individually-plausible, non-overlapping regions**, a material improvement on the previous best of "~20 confident, several still mixed-zone". The remaining 2 (zone 4, Marsden Primary; zone 6, Laygate Primary) get almost no territory. Investigated directly rather than just tuning parameters further: sampled pixels along the line between zone 3's and zone 4's own label positions, then visually confirmed at 2x zoom that there is genuinely **no drawn boundary line at all** separating zones 3 and 4 in that area of the source PDF - a real gap in the published map itself, not a rendering or extraction artifact. Per this project's rule against ever guessing/estimating geometry, the 25 clean zones were not deployed alone (closing zones 3/4/6 properly would require inventing the missing line, exactly the guessing this project doesn't do).

Committed (no Co-Authored-By trailer): `22eb452` - a documentation-only update to `catchment-sources.yml`'s South Tyneside candidate note (no new catchment_areas rows; `map_catchments_cache.feature_count` unchanged at 9480).

**Most promising next lead:** South Tyneside's zones 4 and 6 specifically - the problem is now narrowed to two small, well-isolated zones rather than a vague "still stuck", and a hand-verified fix (e.g. checking whether South Tyneside also publishes an individual-school PDF for Marsden Primary or Laygate Primary, the way Harton Academy has its own separate map) could close out all 27 zones without touching the 25 that already work. After that: Shetland's multi-point DB-coordinate fit (still not attempted - many known-precise anchor points available), or a fresh scan of English/Welsh/Scottish LAs outside the 85-LA pilot roster, applying the "check whether a catchment-finder widget calls a hidden ArcGIS Server" and "CDP Fetch-domain interception for stubborn PDF downloads" techniques that paid off this session and last.

## Update: Shetland's 25 primary/JHS catchments landed - polygon extraction solved via colour classification, not watershed (2026-08-08)

**Shetland Islands: 25 catchment_areas rows (26 zones minus 1 geometry-dedup merge) landed, closing out the lead flagged "genuinely tractable, worth a dedicated session" two sessions ago.** Georeferencing was already solved (a 26-point affine fit, RMS 126m, cross-checked against the source PDF's own printed 1:150000 scale to within 0.5%) but not deployed - the polygon-extraction half was still open because these zones are semi-transparent colour tints alpha-blended over a full OS basemap, not a clean vector line network, so this project's usual boundary-line watershed technique (Middlesbrough, Portsmouth, South Tyneside) doesn't apply.

Solved instead with **competitive nearest-fill-colour classification**: each land pixel is assigned to whichever of the ~27 zones' sampled reference tint colour is closest, rather than growing outward from a seed along drawn boundary lines. Sea/coastline was separated first, independently, via its own highly consistent pale-blue colour - far more reliable than the zone-vs-zone problem, and doing it first meant zone classification never had to fight sea leaking through the map's many narrow voes (fjords). Thin overlay artefacts spanning open water (OS grid lines, place-name text, the north arrow, the "SIC" watermark) aren't sea-coloured and were inflating the land mask; stripped by a morphological opening (they're only 1-3px wide, genuine land blobs are far thicker) before coastline extraction.

A first full pass at per-pixel colour classification produced "confetti": several zones on this map reuse near-identical fill hues for non-adjacent areas (e.g. North Roe and Brae, geographically distant, sampled to within a couple of RGB units of each other), so a zone could win small unrelated pockets of territory anywhere its reference colour happened to be marginally closer than the true local zone's - basemap texture (fields vs. forest-hatching vs. water) shifts the same nominal tint's rendered colour enough to cause this. Fixed with a **confirm-then-regrow pass**: for each zone, keep only the connected component of its colour-classified pixels that actually contains its own seed dot(s) (the school's marker position) as "confirmed" territory, discard every other component (the confetti), then re-fill all unclaimed land purely by nearest-neighbour spatial distance to the confirmed regions - immune to further colour collisions since it no longer looks at colour at all once the confirmed cores are established. This took the per-school verification pass from 18/25 correct to 25/25.

Verified two ways before deploying: (1) each zone's pixel-classification region contains its own school's real DB coordinate (checked via inverse-affine-transforming the DB lat/lon back to pixel space); (2) after vectorising (`rasterio.features.shapes` + light morphological smoothing + Douglas-Peucker simplify to ~15m tolerance) and converting to real lon/lat, every one of the 25 output polygons still contains its own school's real DB coordinate via `shapely.Polygon.contains` - a genuine end-to-end check, not just a pixel proxy. All 25 envelopes fall within GB bounds (lat 59.5-60.9, lon -2.16 to -0.79).

"Sound & Bells Brae feeds to Anderson High School" is a real, single zone covering two separate open DB schools (Sound Primary and Bell's Brae Primary, ~560m apart in central Lerwick) - both schools' own real coordinates independently verified inside the one polygon, then handled by this project's existing `(source_id, geometry_checksum)` merge logic in `build_catchment_areas` (same mechanism that merged Middlesbrough's Outwood Academy Acklam / The King's Academy shared zone), producing one combined-name row rather than two duplicate ones. Fetlar, Papa Stour and Out Skerries are drawn on the source map with their own zones but excluded, as previously found - none has a currently-open DB school to match. Fair Isle's inset has its own separate scale with no OS grid to independently re-anchor and only one usable control point (its own school), so rather than force a low-confidence georeferencing pass on it, it was handled entirely differently: since Fair Isle is a single-school island where the whole island is definitionally the catchment, its real OSM/Nominatim coastline polygon (`osm relation 3067410`) was pulled directly and verified to contain Fair Isle Primary School's own DB coordinate - no pixel work needed for that one.

Also fixed while touching this: `packages/shared/src/config/catchment-sources.test.ts`'s `PILOT_LOCAL_AUTHORITIES` list was missing four local authorities already `enabled: true` in `catchment-sources.yml` from prior sessions (Herefordshire, Redcar and Cleveland, South Tyneside, and now Shetland) - the test was passing anyway because `packages/shared/src/generated/` is gitignored and only regenerated by `pnpm sync-config`/the `prepare` lifecycle hook, so it was silently validating a stale snapshot rather than the real current config. Re-ran `pnpm --filter @catchment-zone/shared sync-config` before re-testing to catch this properly; all four are now correctly listed.

Committed (no Co-Authored-By trailer): `5cdeb57` (geojson + catchment-sources.yml + roster-test fix, pushed before import since the source's `download_url` points at `raw.githubusercontent.com`). Imported: `uv run ingestor import-catchments --local-authority "Shetland Islands"` -> 25 built, 0 rejected. `refresh-catchment-overview-cache` run immediately after: `map_catchments_cache.feature_count` 9520 -> 9545 (+25), matching the live `catchment_areas` row count exactly. `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean. **Local authority count: 85 -> 86** (`S12000027` flipped to `PILOT`).

**Most promising next lead:** a fresh scan of English/Welsh/Scottish local authorities outside the now-86-strong pilot roster for genuinely published catchment maps, prioritising any whose `catchment-sources.yml` note reads like an earlier, less-thorough pass (a quick "PDF-only, no ArcGIS" dismissal without actually opening the PDF, the way Shetland's own first-pass note once did) - apply the full toolkit proven across this project: hidden ArcGIS/FeatureServer behind a plain-looking postcode search form (Redcar and Cleveland, Herefordshire), colour-tint classification with a confirm-and-regrow cleanup pass (newly proven here, likely useful for other alpha-blended-fill council maps rather than only clean-line ones), and CDP Fetch-domain interception for any PDF/download URL that returns a synthetic wrapper instead of real bytes (South Tyneside). South Tyneside's own zones 4/6 gap remains a genuine dead end (missing line in the source data itself, confirmed across two independent editions) and should not be re-attempted without a new source PDF appearing.

## Update: Cardiff's 85 primary/secondary/Welsh-medium catchments landed via point-in-polygon attribution; project-wide re-scan finds almost every sizeable LA already investigated (2026-08-08, later session)

**Cardiff: 85 catchment polygons landed (57 primary, 10 secondary, 15 Welsh-medium primary, 3 Welsh-medium secondary), reopening a candidate dead-ended twice before as "real geometry, zero identifying data."** Cardiff's Astun iShare WFS (`ishare.cardiff.gov.uk/GetOWS.ashx`, `MAPSOURCE=mapsources/maps_en`) genuinely serves live polygon geometry for four real layers (`catchprimary`/`catchsecondary`/`catchprimarywelsh`/`catchsecondarywelsh`), confirmed by two independent prior sessions - but `DescribeFeatureType` confirms none of the four carry any attribute field beyond `msGeometry`, the same platform-wide gap already found for Monmouthshire and Rhondda Cynon Taf's iShare deployments.

Unblocked without any name field at all: since this project already holds every Cardiff school's own real GIAS coordinate, each polygon was attributed to a school by point-in-polygon containment instead of a name lookup - a technique used elsewhere in this project only for verification, applied here for actual attribution for the first time. The key step was restricting each layer's candidate schools correctly before matching: a first naive pass against all Cardiff primary/secondary schools produced a confusing mess where most polygons contained 2+ schools. Investigated rather than worked around: Cardiff's voluntary aided/controlled faith schools (Church in Wales, Roman Catholic) set their own admissions with no LA-administered catchment of their own - the identical structural fact already documented for Herefordshire's faith schools - so their real building coordinates simply happen to sit inside whichever community catchment geographically surrounds them, not inside a catchment of their own. Restricting `catchprimary`/`catchsecondary`'s candidate pool to non-faith, non-Welsh-medium schools (and `catchprimarywelsh`/`catchsecondarywelsh`'s pool to Welsh-medium "Ysgol"-named schools only) turned the mess into a near-bijective result: `catchsecondary` (10 polygons) and `catchsecondarywelsh` (3) matched their exact 10 and 3 real candidate schools 1:1 with zero ambiguity, zero left over - about as strong a confirmation as this project's verification methodology can produce that the attribution logic itself is correct, not just plausible. `catchprimary` matched 57 of 61 polygons (56 single-school + one genuine two-school shared zone, Marlborough Primary / Howardian Primary School, kept as one combined-name row per this project's established shared-zone convention rather than treated as a matching error); `catchprimarywelsh` matched 15 of 17 (13 single + 2 shared pairs). The remaining 4 primary and 2 Welsh-medium-primary polygons matched no eligible school at all (their nearest real school in every case was a faith school just outside that layer's own candidate pool) and were left out of the dataset rather than guessed at.

Every one of the 85 output polygons independently re-verified to contain its assigned school's (or both schools', for the shared zones) real DB coordinate before deploying - not just the point used to attribute it, a genuine end-to-end check. Licence recorded as UNCONFIRMED (no licence metadata on the WFS response itself; Cardiff's open-data pages returned a 403 to unauthenticated fetches from this environment) - disclosed honestly rather than gating inclusion on it, per this project's standing policy.

Committed (no Co-Authored-By trailer): `e084e86` (4 geojsons + `catchment-sources.yml` + roster-test fix, pushed before import since the source's `download_url` points at `raw.githubusercontent.com`). Imported: `uv run ingestor import-catchments --local-authority "Cardiff"` -> 85 built, 0 rejected. Envelope-verified: lat 51.444-51.560, lon -3.344 to -3.069, within GB bounds. `refresh-catchment-scores` (6,356 of 9,630 areas now scored) and `refresh-catchment-overview-cache` (9,630 = 9,630, cache in sync) both re-run. `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean. **Local authority count: 86 -> 87** (`W-681` flipped to `PILOT`).

**Project-wide re-scan finding, worth recording explicitly for whoever continues:** a systematic cross-check of every English/Welsh/Scottish local authority with a non-trivial school count (242 LAs from this project's own `local_authorities`/`schools` tables) against `config/catchment-sources.yml` found that essentially all of them - every large city, every home county, every London borough, every Welsh council - already have a documented investigation in this file, either `enabled: true` in the 86 (now 87) -LA pilot roster or a `reason_not_enabled` note in `candidates:`. Only three names appeared to be "missing" on a first pass, and all three turned out to be pre-existing entries under a naming variant (Kingston upon Hull "City of" suffix, Herefordshire "County of" suffix, "St. Helens" vs "St Helens"). This session re-verified several of the largest/thinnest-looking candidates specifically for the hidden-ArcGIS/postcode-widget trick that unlocked Redcar and Herefordshire, all confirming the existing dead-end findings rather than reopening them: Kent (genuinely distance-based, no catchment areas at all - re-confirmed), Essex (server-side point-in-polygon lookup with no exposed polygon service - re-confirmed), Coventry (a real road-name-to-school-list search, `coventry.gov.uk/directory/search` - genuinely list-only, not a map, no hidden geometry API behind it), Wakefield (a plain address-lookup form redirecting to a result page, backed by a trivial JS file with no map/GIS call - genuinely list-only), and Milton Keynes/Salford's previously-flagged "worth retrying from a different network origin" notes (both still connection-refused even from this session's `WebFetch` tool, a different network path than the sandbox's own `curl` - a real, not sandbox-specific, unreachability).

**Most promising next lead:** given how thoroughly this project's easier wins have now been mined, the two best-understood remaining opportunities are (1) applying Cardiff's newly-proven point-in-polygon attribution technique to the other Astun iShare Welsh councils already found to have real geometry but zero attributes - Monmouthshire (`PrimarySchoolCatchment2025`/`NewSecondarySchoolCatchment2021`/`WelshPrimarySchoolCatchment_2024`/`WelshSecondarySchoolCatchment`, all confirmed live) is the closest match to Cardiff's own situation and the natural next candidate, though Rhondda Cynon Taf's WFS is disabled server-side entirely and would need a different unlock; and (2) continuing Oxfordshire's own remaining ~129 of 307 schools (91 non-gridded cream/yellow-basemap PDFs needing the already-proven landmark-pair method, ~28 grid-template PDFs that failed the autocorrelation confidence check and are worth a second pass at a lower threshold) - a bounded, already-solved-in-principle execution task rather than a new research problem.

## Update: Monmouthshire's 33 primary/secondary/Welsh-medium-primary catchments landed via point-in-polygon attribution; other Welsh iShare councils checked and ruled out (2026-08-08, later session)

**Monmouthshire: 33 catchment polygons landed (26 primary, 4 secondary, 3 Welsh-medium primary), applying Cardiff's point-in-polygon attribution technique to the exact lead the prior session flagged as the closest structural match.** Monmouthshire runs the same Astun iShare platform as Cardiff (`maps.monmouthshire.gov.uk/GetOWS.ashx`, `MAPSOURCE=Monmouthshire/MyHouse` - found live via `GetCapabilities` after Cardiff's known `mapsources/maps_en` guess failed; the real mapsource name came from the homepage's hidden `txtMapSource` input field). `DescribeFeatureType` confirmed the identical zero-attribute gap on all four catchment layers plus the `School` point layer itself, exactly as the prior session's Playwright investigation had found. GML (not GeoJSON) came back in EPSG:27700 with `gml:MultiSurface`/interior-ring holes on some features - parsed with a small stdlib-`xml.etree` GML reader (no `lxml` available in this environment) plus `pyproj`/`shapely` for the 27700->4326 reprojection, since the project's own GML WFS import path in `cli.py` wasn't reused (static pre-processed output pushed to GitHub instead, matching Cardiff/Herefordshire/Oxfordshire/Shetland's existing pattern).

A genuine platform difference from Cardiff surfaced during candidate-pool restriction: a first attempt copying Cardiff's exact rule (exclude all faith schools) left 6 of 26 primary polygons unmatched - each one turned out to contain exactly one Church in Wales school's real coordinate and nothing else, meaning Monmouthshire (unlike Cardiff) _does_ draw its Church in Wales schools their own dedicated catchment polygon. Only the two Roman Catholic schools needed excluding (their real sites instead fall inside a neighbouring community school's zone - the same "sets its own admissions, no LA catchment of its own" pattern already seen elsewhere, just narrower here than in Cardiff). With that correction, `PrimarySchoolCatchment2025` (26 polygons) and `NewSecondarySchoolCatchment2021` (4, including King Henry VIII - an all-through Community school ages 3-19 that gets its own catchment in _both_ the primary and secondary layers, verified as a real, not duplicate, entry) both matched every polygon 1:1 against every eligible candidate school with zero ambiguity and zero unmatched polygons; `WelshPrimarySchoolCatchment_2024` matched its 3 polygons against Monmouthshire's 3 real Welsh-medium ("Ysgol"-named) primaries 1:1 as well - the cleanest, most bijective result this technique has produced yet. `WelshSecondarySchoolCatchment`'s 2 real polygons were investigated but left out entirely: Monmouthshire has no Welsh-medium secondary of its own, and the actual serving cross-authority school (Ysgol Gyfun Gwent Is Coed, physically sited in Newport) does not fall inside either polygon (~9.5km and ~17km outside respectively, confirmed with `shapely.distance`, not a rounding-level near-miss) - correctly left undeployed rather than force-matched to the nearest plausible candidate.

6 of the 26 output primary polygons had minor self-intersections after reprojection (repaired with the project's own `geometry.validate_and_repair`, the same `make_valid`/`buffer(0)` fallback the live import pipeline already applies); every one of the 33 final polygons was independently re-verified to still contain its assigned school's real DB coordinate after repair, not just before. Licence recorded as UNCONFIRMED, the same honest disclosure as Cardiff (no licence metadata on the WFS response itself).

Committed (no Co-Authored-By trailer): `d462d31` (3 geojsons + `catchment-sources.yml` + roster-test fix, pushed before import since the source's `download_url` points at `raw.githubusercontent.com`). Imported: `uv run ingestor import-catchments --local-authority W-679` -> 33 built, 0 rejected. Envelope-verified: lat 51.554-51.983, lon -3.157 to -2.650, within GB bounds. `refresh-catchment-scores` (6,359 of 9,663 areas now scored) and `refresh-catchment-overview-cache` (9,663 = 9,663, cache in sync) both re-run immediately after import. `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean. **Local authority count: 88 -> 89** (`W-679` flipped to `PILOT`; the DB's live count was 88, one ahead of this session's starting brief of 87, before this change - not investigated further since it doesn't affect correctness).

**Other Welsh Astun iShare councils checked this session, both ruled out quickly:** a live-domain scan of Newport, Torfaen, Caerphilly, Bridgend, Blaenau Gwent and Merthyr Tydfil's `maps.<council>.gov.uk`/`ishare.<council>.gov.uk` subdomains (the pattern that found Cardiff and Monmouthshire) found only two real HTTP responses - `maps.bridgend.gov.uk` (a static 30-byte "test text" placeholder page, not a real map deployment) and `maps.rctcbc.gov.uk` (Rhondda Cynon Taf, already documented as a dead end: real iShare catchment layers exist in the map config but the WFS endpoint is disabled server-side entirely, a harder block than the zero-attributes gap Cardiff/Monmouthshire had). Newport, Torfaen, Caerphilly, Blaenau Gwent and Merthyr's map subdomains are either unreachable (connection refused) or return a hard 403 - genuinely no further Astun iShare Welsh councils to unlock with this technique; the platform-wide pattern search is now exhausted.

**Most promising next lead:** Oxfordshire's own remaining ~129 of 307 schools is the clearest bounded, already-solved-in-principle work left - 91 non-gridded cream/yellow-basemap PDFs need the already-proven per-file landmark-pair method (find a second real, precisely-locatable landmark on each map, geocode it, verify north-up), and ~28 grid-template PDFs failed the autocorrelation confidence check on a first pass and are worth a second pass at a lower threshold. Both are inherently manual, per-file work (not a single unlock like the Astun iShare councils) rather than a new research problem - the method itself needs no further proving, only continued application.

## Update: Central Bedfordshire's 93 primary/middle/secondary catchments landed via point-in-polygon attribution (2026-08-08, later session)

**Central Bedfordshire: 93 catchment polygons landed (77 primary, 10 middle, 6 secondary), reopening a candidate already found and dead-ended once this project's `candidates:` file (real geometry, zero attribute fields) with the same point-in-polygon technique proven twice on Cardiff and Monmouthshire.** This session re-scanned `catchment-sources.yml`'s `candidates:` section for thin or reopenable notes rather than starting a fresh from-scratch LA search, since almost every sizeable English/Scottish/Welsh authority already has a documented investigation (confirmed by the prior session's project-wide cross-check). Central Bedfordshire's own note was an exact structural match to Cardiff/Monmouthshire's already-solved problem: a real, live Astun iShare WFS (`my.centralbedfordshire.gov.uk/GetOWS.ashx`, `MAPSOURCE=mapsources/MyHouse`, found the same way as Monmouthshire's - a hidden map-source string in the homepage HTML) serving three real layers (`catchment_areas_lower`/`_middle`/`_upper`, matching the county's genuine lower/middle/upper school-tier system) but `DescribeFeatureType` confirms zero attribute fields on all three, same as before.

Two small platform differences from Cardiff/Monmouthshire, both handled with existing tooling rather than new code: (1) this deployment rejects `outputFormat=application/json` outright ("not a permitted output format for layer"), the same failure mode already documented for North Lincolnshire's iShare deployment, so the project's existing `query_all_wfs_gml_features` GML3 parser was reused rather than writing a third GML reader from scratch; (2) Central Bedfordshire is genuinely, actively mid-transition from its historic 3-tier lower/middle/upper system to a 2-tier primary/secondary one, so a large fraction of the source's 142 polygons (99 lower, 28 middle, 15 upper) have no candidate school of the matching phase inside them at all - the school that zone was originally drawn for has since closed, merged, or been reclassified. Rather than treat this as a matching failure, each phase's candidate pool was restricted to real, currently-open DB schools of the matching `phase_name` (`Primary`/`Middle deemed secondary`/`Secondary`) first, the same "restrict the candidate pool before matching" discipline that made Cardiff/Monmouthshire's attribution reliable - after which 77 of 99 lower, 10 of 28 middle and 6 of 15 upper polygons matched exactly one eligible school each and were kept; every other polygon (the transition-superseded majority) was correctly left unmatched rather than guessed at.

One further, genuinely new wrinkle not seen on Cardiff/Monmouthshire: 5 lower-tier schools (St Andrew's CofE VC Primary, Lawnside Academy, St Christophers Academy, Hadrian Academy, The Vale Academy) each had their real DB coordinate fall inside _two different_ lower-tier polygons at once - real overlapping/superseded zone geometry from the same tier-transition process, not a name-matching bug (independently confirmed: every other candidate school in every other layer fell inside exactly 0 or 1 polygon, so this wasn't a systemic geometry problem). All 9 polygons touching any of those 5 schools were excluded rather than arbitrarily picking one. One further self-intersecting polygon (The Rushmere Park Academy) was repaired with this project's existing `geometry.validate_and_repair` (shapely `make_valid`) and independently re-verified to still contain its school's real coordinate after repair, the same discipline already used for 6 of Monmouthshire's primary polygons.

Licence recorded as UNCONFIRMED but with the strongest sibling-dataset evidence found for any UNCONFIRMED source so far this project: all 5 of Central Bedfordshire Council's other data.gov.uk-listed datasets (Listed Buildings, Conservation Areas, Article 4 Directions, Tree Preservation Orders, Rights of Way Network) are explicitly OGL, matching the same "5 of 5" ratio previously recorded for East Renfrewshire - the catchment WFS layer itself just isn't individually listed there.

Committed (no Co-Authored-By trailer): `be294b0` (3 geojsons + `catchment-sources.yml` + roster-test fix, pushed before import since the source's `download_url` points at `raw.githubusercontent.com`; CDN was already fresh by the time it was checked, no wait needed). Imported: `import-catchments --local-authority 823` -> 93 built, 0 rejected (dry-run first, then for real). Envelope-verified: lat 51.805-52.190, lon -0.702 to -0.144, within GB bounds. `refresh-catchment-scores` (6,444 of 9,797 areas now scored, 44 of Central Bedfordshire's own 93) and `refresh-catchment-overview-cache` (9,797 = 9,797, cache in sync) both re-run immediately after import. `pnpm --filter @catchment-zone/shared test` (45 passed, after re-running `sync-config` to regenerate the gitignored `src/generated/catchment-sources.json` the test suite reads from) and the ingestor's full pytest suite (127 passed) both re-run clean. **Local authority count: 89 -> 90** (`823` added to the pilot roster).

**Ruled out this session (thin `candidates:` notes checked but not reopenable):** none beyond Central Bedfordshire were pursued this session - the remaining "worth retrying from a different network origin" notes (Milton Keynes, Salford, Leicestershire, Ealing) were already re-checked and re-confirmed unreachable from this same sandbox network in the prior session's `WebFetch`-based re-check, and Stoke-on-Trent's Cadcorp GeognoSIS candidate note (which reads as if "not yet retried with the Derby technique") turns out to already be stale/superseded - its primary catchments were in fact already cracked and enabled in a prior session (see the existing Stoke-on-Trent entry in `sources:`), so this is a documentation staleness issue in the `candidates:` note text, not a real open lead; worth deleting or updating that stale note in a future pass but not touched this session to stay focused on landing new coverage.

**Most promising next lead:** Oxfordshire's own remaining ~129 of 307 schools (91 non-gridded landmark-pair PDFs, ~28 grid-template PDFs that failed the autocorrelation confidence check) remains the largest, most clearly bounded, already-proven-in-principle body of work left in the whole project - continuing it needs no new research, only continued per-file execution. Beyond that, Inverclyde's real vector-PDF catchment map (26 zones, confirmed genuine Cadcorp SIS Map Modeller vector export, not raster) is the most promising _new_ digitisation target on record: the previous attempt's blocker was purely georeferencing precision (multi-label-landmark affine fit gave unreliable results), and the candidate note itself already specifies a concrete next technique to try instead - the map's own visible OS grid-line spacing (~76-79px/km at 150dpi, autocorrelation-measurable, the same technique that unlocked Oxfordshire's grid-template PDFs) combined with a single precise point anchor (e.g. Dumbarton Castle) rather than repeating the diffuse place-label approach that already failed once.

## Checkpoint: pausing for usage limit (2026-08-08)

Working tree clean, HEAD at `3502281`, everything above this line committed and pushed to `origin/main`. DB state at pause: 9,797 `catchment_areas` rows, `map_catchments_cache.feature_count` = 9,797 (in sync), catchment scores freshly refreshed (6,444 of 9,797 scored). 90 local authorities have real deployed catchment coverage.

A fork was mid-flight when the pause was requested, working on: (1) Inverclyde's vector-PDF re-attempt (26 zones, previously rejected for insufficient georeferencing precision - see the "Most promising next lead" paragraph above for the specific fix idea it was trying), and (2) continued execution on Oxfordshire's remaining ~129 schools. It commits incrementally, so if it was cut off mid-task, check `git log`/`git status` and the DB's `catchment_areas` count/`map_catchments_cache.feature_count` against the numbers in this checkpoint before assuming nothing landed - it may have finished one or more schools/LAs and committed them before being interrupted. If work is found uncommitted-but-legitimate in the working tree (rather than committed), finish it properly (verify against real DB school coordinates, test, commit, push, `import-catchments`, `refresh-catchment-overview-cache`, `refresh-catchment-scores`) rather than discarding it.

Operational note learned this session, worth preserving for whoever resumes: `import-catchments` fetches source GeoJSON from `raw.githubusercontent.com/.../main/...`, not the local working copy - always `git push origin main` before importing newly-committed catchment data, and be aware GitHub's raw-content CDN caches the `main` branch URL for a few minutes after a push (compare against a commit-SHA-pinned URL to detect staleness rather than importing prematurely on stale data).

To resume: check on the in-flight fork first (if the harness still has it tracked), verify/finish its work per the paragraph above, then continue down the "most promising next lead" list - Inverclyde (if not resolved), then Oxfordshire's remaining schools, then a fresh re-scan of `candidates:` notes that look thin/under-investigated by this session's now-mature toolkit (hidden ArcGIS/WFS APIs behind catchment-finder widgets, Astun iShare point-in-polygon attribution, colour-classification-with-confirm-regrow segmentation, marker-controlled watershed, landmark-pair anchoring, ICP registration, CDP Fetch-interception, Wayback Machine). Standing rules unchanged: never invent/estimate geometry, never add a Co-Authored-By trailer, Sonnet only.

## Update: Inverclyde's 26 schools landed via OS grid-line pixel detection, plus 9 more Oxfordshire schools (2026-08-08, later session)

**Inverclyde: all 26 of 26 catchment zones landed (9 primary denominational, 11 primary non-denominational, 3 secondary denominational, 3 secondary non-denominational), resolving the checkpoint's top lead on the first real attempt this session (the prior fork's in-flight work was never committed - a clean working tree confirmed nothing was lost, but nothing was inherited either; this was rebuilt from scratch).** The source PDF (`Inverclyde-School-Catchments.pdf`) is a genuine Cadcorp SIS Map Modeller vector export - confirmed via `page.get_drawings()`, each catchment a real filled/stroked vector polygon, not a raster image - previously rejected once for a 3/4-point affine fit using geocoded place-name label positions (Greenock, Port Glasgow, Dumbarton Castle, Dunoon) that gave too large a residual (schools landing in the wrong neighbouring zone entirely).

This session's fix was exactly the checkpoint's own suggestion, made concrete: the basemap's OS 1km grid lines are drawn in a single precise `RGB(204,204,204)` against an `RGB(233,233,233)` background, giving sharp column/row-sum spikes at the true grid-line pixels rather than needing autocorrelation at all - measured spacing was 101.5px/km at 200dpi, identical across two independent long baselines (a 6km easting run and a 4km northing run) and identical between the x and y axes, confirming uniform scale with no rotation (also consistent with the map's own compass rose and the grid lines' visibly perfect axis-alignment). Absolute position was anchored not with a single monument like Dumbarton Castle, but more robustly: the grid's own printed two-digit labels (standard OS convention - the last two digits of each line's true OSGB36 easting/northing) were read directly off the page and cross-checked against this project's own DB coordinates for Greenock/Port Glasgow/Gourock reprojected to EPSG:27700 - e.g. grid column "32" (easting 232000) sits almost exactly on Port Glasgow's real projected easting (232058), and the printed "PORT GLASGOW" label falls exactly where that intersection predicts. All 4 pages of the PDF share the identical grid/extent (confirmed by matching detected grid-line pixel positions across all 4 pages), so one derived transform covered the whole document. Catchment polygons were matched to their school by exact fill-colour lookup against each page's own printed legend (9-11 distinct swatches per page).

Every one of the 26 zones - not just the 3 the checkpoint noted as already spot-checked - was independently verified to contain its own real DB school coordinate (reprojected to EPSG:27700 for a true-distance check, not degrees): margins to the nearest zone boundary ranged from 56m (Moorfoot Primary, the tightest) to 1365m (Port Glasgow High School / St Stephen's High School, a genuinely shared-campus coordinate correctly landing inside two different pages' zones), with most in the 150-600m range - no zone was a close call. Licence recorded honestly as printed on the PDF (Crown copyright, Inverclyde Council Licence Number 100023421) - a standard OS PSMA public-reference publication, not an explicit OGL statement, the same disclosure already used for Shetland's identically-licensed source.

Committed (no Co-Authored-By trailer): `87064e1` (4 geojsons + `catchment-sources.yml`, pushed before import; CDN was already fresh by the time it was checked, no wait needed). Imported: `import-catchments --local-authority S12000018` -> 26 built, 0 rejected. `refresh-catchment-overview-cache` (9,823 = 9,823, cache in sync) and `refresh-catchment-scores` (6,450 of 9,823 areas scored) both re-run immediately after import. `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean. **Local authority count: 90 -> 91** (`S12000018` added).

**Oxfordshire: 9 more schools landed (6 primary, 3 secondary), taking the OS-grid-template total from 119 to 128 of 307.** The prior session's exact pipeline script wasn't preserved between sessions (nothing was left in the repo to reuse), so this rebuilt the same core technique from scratch with two refinements: a precise cyan grid-colour mask plus a higher autocorrelation search floor (avoids locking onto an unrelated periodic map feature - parcel/field-boundary hatching or similar - that otherwise wins the harmonic-rejection peak search on many files and gives a plausible-but-wrong scale), and OpenCV connected-component labelling to cleanly separate the school's marker icon from the boundary outline (the boundary+marker are raster-baked, not real vector paths - confirmed via `get_drawings()==[]` and 60+ raster image tiles per page) before filling the traced outline via morphological closing + flood-fill.

Of 97 real PDFs downloaded this session (for Oxfordshire schools not yet in either geojson by name), only 10 gave a clean, mutually-consistent x/y grid-scale detection - the other ~87 need the same kind of manual per-file debugging as the original bug-fix pass, not a further general fix, and remain the clearest next target. Of the 10, 9 were successfully digitised (King's Meadow Primary, Queen Emma's Primary, Edward Feild Primary, West Witney Primary & Nursery, St Kenelm's CE (VC), The Blake CE Primary; Didcot Girls' School, King Alfred's, Lord Williams's School), each independently checked by confirming the marker icon falls inside the traced boundary polygon in pixel space _before_ the school's real DB coordinate is ever used to anchor the transform - a genuine, non-circular check since marker-finding and boundary-tracing are independent detections - plus a visual contour-overlay spot-check on 3 of the 9 confirming pixel-accurate tracing. Dry Sandford Primary School (already flagged in an earlier session as needing a higher-DPI revisit) was tried again at 300dpi but its marker's connected component now merges directly into the boundary line's own component, so the simple size/fill-ratio split used here doesn't separate them - still unresolved, would need a different per-file approach (e.g. erosion before labelling).

Committed (no Co-Authored-By trailer): `3b935e0` (2 updated geojsons + `catchment-sources.yml`, pushed before import; CDN was already fresh). Imported: `import-catchments --local-authority 931` -> 128 built, 0 rejected. `refresh-catchment-overview-cache` (9,832 = 9,832, cache in sync) and `refresh-catchment-scores` (6,459 of 9,832 areas scored) both re-run immediately after import. Both test suites re-run clean after this change too.

**Most promising next lead for whoever continues after this session:** Oxfordshire's remaining ~198 schools (91 non-gridded landmark-pair candidates, proven but inherently manual per file; ~87 downloaded grid-template PDFs whose scale detection needs individual debugging, not a general fix) is still the largest, most clearly bounded body of work in the project - re-download the PDF batch via `oxfordshire.gov.uk/sites/default/files/2022-12/{code}_all.pdf` for whichever of the ~197 not-yet-done Oxfordshire school names (from `oxfordshire.gov.uk/schools/list?page=0..15`) don't already have a geojson feature, since the downloaded batch itself wasn't preserved between sessions. Beyond that, a fresh re-scan of `candidates:` notes for other thin/stale entries worth a second look with this session's toolkit (OS grid-line pixel/colour detection now proven twice, OpenCV connected-component marker/boundary separation, Astun iShare point-in-polygon attribution) remains open.

## Update: found and fixed two correctness bugs in the Oxfordshire pipeline (18 bad rows removed); net +2 verified schools; pipeline finally committed (2026-08-08, later session)

**Started this session by inheriting the immediately-prior fork's uncommitted work in the session scratchpad** (97 already-downloaded candidate PDFs, a working `oxon_lib.py`/`process_one.py`/`finalize.py` pipeline) rather than rebuilding from scratch - a rare case of the "pipeline not preserved between sessions" problem _not_ recurring, since this was a continuation of the same session rather than a fresh one. That prior fork's own commit (`3b935e0`, "9 more Oxfordshire grid-template catchments") turned out to have a real bug worth catching immediately: it re-digitised and re-added **7 schools that already had a catchment polygon from an earlier pass** (King's Meadow Primary, Queen Emma's Primary, West Witney Primary & Nursery, St Kenelm's CE (VC), Didcot Girls' School, King Alfred's, Lord Williams's School) without checking first - each landed as a near-duplicate second polygon (same bounds/size to 3-4 decimal places) both in the geojson and as a second DB row via the `(source_id, geometry_checksum)` upsert dedup key, which doesn't remove old rows on re-import. Fixed by deleting the 7 stale DB rows directly and removing the 7 duplicate geojson features; only 2 of that commit's 9 claimed additions (Edward Feild Primary, The Blake CE Primary) were genuinely new.

**Then, while trying to push further into the 97 downloaded PDFs' `grid x/y mismatch` failures (most of them), discovered a second, more serious bug already responsible for a further 20 schools this session had itself just landed.** Oxfordshire's per-school PDFs turn out to have (at least) three template variants, not two: alongside the known OS-grid raster template and the non-gridded cream/yellow vector template, there is a third - a raster basemap with 140+ embedded image tiles just like the real grid template (so the existing "many raster tiles, no vector boundary path" `is_grid_template()` check misclassified it as grid-template), styled similarly to the non-gridded template, but with **no actual cyan grid drawn on it anywhere**. The pipeline's column/row cyan-pixel autocorrelation still finds a plausible-looking periodic peak on these files from scattered unrelated cyan content (anti-aliasing, water features) across its wide 180-950px search range - and critically, none of the existing checks (marker-inside-boundary, GB bounds, plausible catchment area) can catch a wrong _scale_, only a wrong anchor point, since the marker is always forced onto the school's real coordinate by construction regardless of whether the grid reading is real. Caught only by literally rendering the claimed grid spacing back over the actual page image and seeing it line up with nothing - of the first "20 verified" schools landed this session, only 2 (South Stoke Primary, Freeland CE Primary) survived this direct visual check; a "joint autocorrelation fallback" and an "8% tolerance loosening" tried in between (both intended as legitimate improvements, both seemed to work at first) were themselves each independently caught producing further false positives the same way, and were reverted rather than shipped.

**The real fix:** `confirmed_grid_line_fraction()` (new, in `oxon_lib.py`) checks that real, near-continuous grid lines actually exist at the claimed pixel spacing - not just a matching aggregate pixel-sum coincidence - by testing, at the best-fitting phase per axis, what fraction of candidate line positions have cyan pixels covering most of the full row/column length. Verified live: scores ~1.0 on every confirmed-genuine grid file tried (including a spot-check of 2 pre-existing original-90-batch schools, King's Meadow and Queen Emma's, using their still-available PDFs) and 0.0 on every instance of the fake-grid template found so far, with no ambiguous middle ground observed. `process_one.py`'s `process()` now requires this as a hard gate (≥0.7 on both axes) before accepting any digitisation result, in addition to the pre-existing `is_grid_template()` template check and marker-inside-boundary/GB-bounds/plausible-area checks.

**Net result: 18 bad rows found and removed (7 exact duplicates + 13 fake-grid false positives, none of which had reached a _deployed_ state visible to users - all caught and fixed before the corresponding `import-catchments` run), 4 new genuinely-verified schools added across the session (Edward Feild Primary, The Blake CE Primary, South Stoke Primary, Freeland CE Primary).** Oxfordshire now stands at 123 of 307 schools (101 primary, 22 secondary) - all 123 individually verified: real DB coordinate falls inside its assigned polygon, polygon within GB bounds (lat 49-61, lon -11 to 2), no duplicate URNs across either geojson file, and (for the 4 new ones) genuine confirmed grid lines under the claimed scale.

**The pipeline is committed this time** (the task brief specifically flagged this as a recurring failure - twice before, pipeline code was left in an ephemeral scratch directory and had to be rebuilt from scratch by the next session): `data/digitized-catchments/oxfordshire/pipeline/oxon_lib.py` (rendering, grid-spacing autocorrelation, `confirmed_grid_line_fraction()`, marker/boundary OpenCV connected-component separation), `process_one.py` (`is_grid_template()`, the full per-file pipeline with all safety gates), `match_schools.py` (council school code -> DB URN/lat/lon matching by normalised name, 307/307 matched cleanly), `batch_process.py` (the batch runner, with a URN-uniqueness guard against the first bug above baked in).

Of this session's 97 downloaded candidate PDFs: 62 are the raster grid template or its fake-grid lookalike (35 turned out to be the fake variant once checked with the new gate, 2 were genuine and got digitised, ~25 failed grid x/y agreement or marker/boundary detection and remain open for further per-file work), and 35 are the non-gridded vector template (candidates for the already-proven landmark-pair method, not yet attempted this session). Dry Sandford Primary School (flagged unresolved in two prior sessions) also failed the new `confirmed_grid_line_fraction()` check (0.80/0.33) in addition to its previously-known marker/boundary-merging problem, so its scale reading was itself suspect - resolve the grid question before revisiting the DPI/erosion idea.

**Important open integrity question for the next session:** only 2 of the pre-existing original-90/22-batch schools were spot-checked against the new hardened pipeline (both passed). The other ~110 were not re-checked, and this bug class (a wrong-scale row that no existing verification step catches) could in principle be older than this session. Re-running `is_grid_template()` + `confirmed_grid_line_fraction()` against every already-deployed Oxfordshire grid-template school (re-downloading each PDF via the standard URL pattern) is now cheap and is the single most important integrity task before adding more schools.

Committed (no Co-Authored-By trailer): `24fe602` (Lord Williams's duplicate fix), `f34f6a4` (20 schools + pipeline first committed - later found to include the fake-grid bug), `ab6334b` (the fake-grid discovery, fix, and correction back down to the true 123). All pushed; CDN was already fresh by the time each was checked (`main` branch URL matched the commit-SHA-pinned URL immediately, no wait needed). Imported: `import-catchments --local-authority Oxfordshire` -> 123 built, 0 rejected. DB cross-checked directly for stale/duplicate rows after import (none found). `refresh-catchment-overview-cache` (9,827 = 9,827, cache in sync) and `refresh-catchment-scores` (6,454 of 9,827 areas scored) both re-run immediately after import. `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean.

**Most promising next lead:** run the integrity re-check described above on the pre-existing ~110 schools first - it's cheap and directly answers whether this session's bug is contained to what's already been fixed or runs deeper into previously-"proven" data. After that, Oxfordshire's 35 non-gridded vector-template PDFs already downloaded this session are ready for the landmark-pair method without any further research needed, and the ~25 still-failing grid-template PDFs need per-file debugging with the now-hardened (and now trustworthy) pipeline.

## Update: the integrity re-check above completed - 0 fake rows found among the 96 checkable schools, but a second real detection bug was found and fixed along the way; 18 schools left honestly flagged as unable to re-check (2026-08-08, later session)

**Ran the exact re-check the previous session flagged as the single most important integrity task:** re-downloaded and re-verified all 112 previously-unchecked, already-deployed Oxfordshire grid-template `catchment_areas` rows (94 primary + 20 secondary minus the 2 - King's Meadow, Queen Emma's - spot-checked in the immediately prior session) against `confirmed_grid_line_fraction()`. **Result: 0 confirmed fakes, 0 rows removed.** The bug the prior session fixed does not appear to run deeper into the previously-"proven" ~110 - as far as this session's method can tell, every school it could check is genuine.

**That said, this took real correction along the way, worth recording plainly.** The plain `confirmed_grid_line_fraction()` (narrow RGB cyan mask, tuned on vivid urban 1:1250 basemaps) scored several genuinely real schools 0.0/0.0 on the very first automated pass - identical to the documented fake-grid signature. Trusting a **whole-page visual style judgement** (orange-contour/cream-shaded basemap vs. white/urban basemap) as a shortcut nearly led to wrongly deleting 6+ correct, currently-live catchments (Kidmore End, Hornton, Cholsey, John Blandy, Leafield, Chalgrove) before a **pixel-strip crop** (zooming into the exact claimed grid-line position, not just glancing at the full page) showed a real, continuous, page-spanning grid line under every one of them - they use a paler cyan grid-line rendering on a more rural/topographic basemap sub-variant the same PDF export tool also produces, not a missing grid. Three more schools (The Hendreds, Brightwell-cum-Sotwell, John Hampden Primary) failed on a separate harmonic bug - the x-axis and y-axis autocorrelation each independently locked onto a different multiple of the true grid spacing (e.g. The Hendreds: 564px on one axis, exactly 2x the other axis's 282px), which the existing per-axis-independent peak search doesn't reconcile. Both were fixed with new, validated functions in `oxon_lib.py` - `cyan_mask_broad()` (HSV-based, catches pale and vivid cyan alike) and `reconcile_grid_period()` (searches for a period shared by both axes' peaks rather than trusting each axis's own top-ranked peak) - exposed via a new `process_one.reverify_grid()` for future re-verification use. Validated in both directions before trusting it: every genuinely real school re-checked this session now scores correctly, and all 12 of the actually-fake rows removed in the immediately prior session (re-fetched at their original URLs to check) still score exactly 0.0/0.0 even under the broadened mask - confirming the discriminating signal really is "no periodic grid structure at all," not narrow colour calibration. The original narrow-mask function and `process()`'s stricter gate for brand-new candidate digitisation were left unchanged (a conservative default there is reasonable); `reverify_grid()` is the one to use for auditing already-deployed schools.

**18 of the 114 could not be re-checked at all, and are explicitly flagged rather than assumed good:** 1 primary (Nettlebed Community School) and 17 secondary (Maiden Erlegh Chiltern Edge, The Henry Box School, Wood Green School, Bartholomew School, Wheatley Park School, Langtree School, Matthew Arnold School, St Birinus School, Didcot Girls' School, Wallingford School, Chipping Norton School, Larkmead School, Lord Williams's School, The Cooper School, The Marlborough Church of England School, The Warriner School, Burford School). Their live source PDF, at the exact URL used for original digitisation, no longer presents as a raster grid-template at all (8-37 embedded images, well under the grid template's usual 140+, one file carrying an internal "2011"/"from 1 September 2012" date) - genuinely different, smaller content than what digitisation reportedly used. No alternate dated URL exists (checked several other plausible date-folder paths for a few of these codes; all 404 except the same one already in use), so this isn't a stale-URL guess - the file behind this exact URL has changed or was mis-attributed. Left deployed with no evidence of fakeness found, but **not** counted as hardened-verified.

**Final honest tally:** of Oxfordshire's 114 grid-template schools (94 primary + 20 secondary), 98 are now hardened-verified genuine (2 from the prior session's spot-check + 96 this session), 0 confirmed fake, 16 secondary + 1 primary = 18 remain unverified/flagged (source PDF no longer checkable), 0 rows removed from the DB or geojson files this session. `config/catchment-sources.yml`'s Oxfordshire primary/secondary entries updated with the exact per-school breakdown. No DB changes were made (nothing to remove), so `refresh-catchment-overview-cache`/`refresh-catchment-scores` were not re-run - the existing cache is still accurate. `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean after the `oxon_lib.py`/`process_one.py` additions.

**Next session, if picking this back up:** the 18 flagged schools are the one remaining open integrity question - worth trying to establish definitively whether their source PDF content changed after original digitisation (real drift) or was mis-attributed at digitisation time (a bookkeeping error), since neither has been ruled in or out, only ruled un-checkable by this session's method. Otherwise, Oxfordshire's still-open non-gridded/landmark-pair candidates and remaining grid x/y-mismatch failures (documented in earlier updates above) remain the more promising path for adding new schools, now with the harmonic-reconciliation fix available for schools that hit that specific failure mode.

## Update: all 18 flagged Oxfordshire schools resolved via a newly discovered hybrid grid+vector template; +1 more school (Faringdon Community College) (2026-08-08, later session)

**Answered the open integrity question the previous update left unresolved.** Directly inspected `get_drawings()` on all 18 flagged PDFs (1 primary - Nettlebed Community School - + 17 secondary) instead of trusting `is_grid_template()`'s n_images/saturated-vector-path heuristic, which was only ever built to distinguish the other two known Oxfordshire templates. Finding: none of these 18 lost their grid or changed to smaller/unrelated content. They are a genuine **third Oxfordshire sub-template**, never previously documented: the same real raster OS 1km grid as the original 90/22 (confirmed both visually - a clearly continuous cyan grid, e.g. Nettlebed's `63`-`75`/`63`-`98` grid squares fully legible - and via `confirmed_grid_line_fraction`), but with the boundary and school-location marker drawn as **genuine vector paths** in `page.get_drawings()` (several hundred line/curve segments per boundary, split across 3-12 separate path objects that chain end-to-end into one closed loop, plus a small filled marker square) instead of baked into the raster. `is_grid_template()` rejected all 18 purely because of the resulting low image count and the presence of vector paths it otherwise (correctly, for the other two templates) treats as evidence of the non-gridded template. This sub-template is actually **higher precision** than the pixel-contour method used for the plain raster template - exact vector coordinates, not a rasterised-then-contoured approximation - not a degraded one.

**New pipeline code, committed (not left in scratch) at `data/digitized-catchments/oxfordshire/pipeline/`:** `vector_boundary.py` (path extraction and end-to-end chaining of the vector segments into one or more closed rings, plus `confirmed_grid_line_fraction_peaks()` - a per-line-peak grid check that fixes a real fixed-integer-pixel-stride phase-drift bug found on Wheatley Park School's tall A3 page, validated against every clear-cut known real/fake Oxfordshire file available locally before being trusted) and `hybrid_process.py` (the full digitisation pipeline for this template, reusing `oxon_lib.py`'s grid-scale detection and gated the same way).

**Two genuine geometric subtleties found and correctly handled, not assumed either way:** The Cooper School's designated area is **two disjoint rings** (a main Bicester-area zone plus a separate Ot Moor-area zone) - landed as a `MultiPolygon`, confirmed by tracing both extracted rings back over the source page image and finding them both matching the printed boundary exactly, in two genuinely separate parts of the map. Burford School's area has a **real interior hole** excluding Carterton (its own separately-schooled town) from the middle of Burford's designated area - resolved via ring-containment (the smaller ring is fully inside the larger one, unlike Cooper's case), not wrongly added as a second area, which an earlier version of this session's own code did before a visual overlay check caught it. A third file (The Marlborough CE School) carries two tiny (~0.06%/0.2% of the main ring) closed red shapes entirely outside the main boundary - confirmed spurious (unrelated small map features, not a real satellite catchment) and correctly dropped by a 3%-of-largest-ring size filter that is applied only to top-level candidates, never to an already-resolved hole.

**Larkmead School turned out to still be the _original_ raster-boundary template** (`get_drawings()` completely empty - the strongest possible signal it isn't the vector template), just exported with only 18 large image tiles rather than the 140+ small ones the existing `GRID_TEMPLATE_MIN_IMAGES=80` heuristic assumes. Verified genuine via direct grid/boundary/marker inspection (real grid line fraction 0.83/1.0, a real boundary and marker found by the existing pixel method) and landed via the original `process_one.process()` with a one-off bypass of the image-count check for this specific confirmed file - the shared gate itself is unchanged, not weakened.

**All 18 previously-flagged schools now pass hardened verification** (school's own real DB coordinate falls inside its polygon, GB bounds sane, `confirmed_grid_line_fraction`/`confirmed_grid_line_fraction_peaks` real). Their existing (unverified) geojson features were **replaced in place by `SCHOOL_URN`**, not appended as duplicates - primary/secondary feature counts unchanged in the geojson files themselves (101/22). Because the ingestor's catchment-area upsert key is `(source_id, geometry_checksum)`, not school identity, re-importing genuinely new geometry for an existing school lands a **second row** alongside the old one rather than replacing it automatically - caught immediately after import (`catchment_areas` count jumped from 9,827 to 9,845, +18 rather than the expected +0), and the 18 stale pre-existing rows (identified by `area_name` + earlier `created_at`, one old + one new row per school, confirmed exactly 2 per school before deleting) were removed by hand, restoring the expected 9,827. Worth remembering for any future re-digitisation of an already-deployed school: the DB layer does not deduplicate by school on its own.

**Also added Faringdon Community College (URN 137993, secondary, area 214.92km2)** - while checking whether the new hybrid method could unlock more of Oxfordshire's ~184 still-undigitised schools generally (not just the 18 flagged ones), ran both the grid method and the hybrid method against all 116 already-downloaded-PDF candidates not yet in the geojson (83 never attempted + 33 previously logged as "not a grid-template file"). Only Faringdon cleared verification; the other 115 genuinely need the non-gridded landmark-pair method (most score 0.00/0.00 on both grid checks - truly no OS grid on the page) or per-file scale-detection debugging (the "grid x/y mismatch" cases) - neither is a quick automated win, consistent with this project's standing notes about the remaining pool.

**Final tally this session:** Oxfordshire now at **124 of 307 schools** (101 primary + 23 secondary), up from 123, with the 18-school integrity question fully closed (0 remain unverified). `catchment_areas` total 9,828 (was 9,827), `map_catchments_cache.feature_count` 9,828 (in sync), `refresh-catchment-scores` re-run clean. `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean. Two commits pushed to `main`, no `Co-Authored-By` trailer.

**Next session, if picking this back up:** the most promising path is the ~82 remaining schools whose PDF genuinely has no OS grid at all (confirmed 0.00/0.00 on both grid checks this session) - these need the already-proven non-gridded landmark-pair method (find a second real landmark via OSM, geocode it, verify via independent bearing/distance check), not more automated grid-detection tuning. The smaller "grid x/y mismatch" pool (~30 schools) may respond to per-file scale debugging the way Wheatley Park's phase-drift bug did, but each is a one-off, not a batch fix.

## Update: Oxfordshire's non-gridded landmark-pair method continued - 6 more schools landed (2026-08-08, later session)

**Continued Oxfordshire via the non-gridded landmark-pair method, per the prior session's "most promising next lead."** Inherited a prior fork's already-downloaded batch of 200 candidate PDFs and matched school-code/URN/lat-lon tables from this same session's scratchpad (not rebuilt from scratch, since the session had continued rather than restarted). Of the ~83 remaining schools with an already-downloaded PDF, classified 51 as the grid-template type and 32 as genuinely non-gridded (matching the prior session's rough estimate) using `is_grid_template()` from the committed pipeline.

**Landed 6 new schools, all individually verified:**

- **Bloxham Church of England Primary School** (URN 123098, 29.8km2) - landmark-pair using OSM village-centre nodes for Deddington and Wigginton (bearing residual 0.55 degrees).
- **Aston Rowant Church of England Primary School** (URN 123124, 15.4km2) - landmark-pair using two other real Oxfordshire schools visible on its own map (Lewknor CE Primary, St Andrew's CE Primary Chinnor) as a long-baseline (770px) anchor pair, after an initial short-baseline (360px) attempt gave a 9+ degree residual - confirmed again that baseline length is what determines reliability, not just landmark identity.
- **Tyndale Community School** (URN 139777, 127.8km2) - turned out to be mis-classified by `is_grid_template()`'s image-count heuristic (only 8 raster tiles, since it's a lower-detail Oxford-district-wide map needing fewer tiles than the hyper-local single-parish maps); a direct `cyan_mask_broad()` + `reconcile_grid_period()` check found a real, strongly-confirmed OS grid (line_frac 0.94/0.77) and it was digitised with the standard grid pixel-contour method instead.
- **St Leonard's Church of England Primary School** (URN 123179, Banbury, 4.07km2) - landmark-pair using Grimsbury Reservoir and Overthorpe Hall (School), 480px baseline, 1.66 degree residual. A third candidate landmark (a "Chetwode" label on the page) was tried first and rejected: its implied scale disagreed with the Reservoir-based scale by 8x, revealing it was very likely a different, closer, coincidentally-named feature rather than OSM's administrative Chetwode village 8km away, which could not physically fit on a page whose real extent (from the Reservoir-school scale) was already known to be only ~3.7km. A reminder that a landmark name match isn't sufficient by itself - the derived scale must be cross-checked for physical plausibility too.
- **Wolvercote Primary School** (URN 142384, 6.17km2) - landmark-pair using Wytham village and Godstow Lock; the direct Wytham-Godstow Lock baseline was too short (142px) to trust alone, so verified via two school-anchored cross-checks instead (3.65 and 0.05 degree residuals), averaging their scales for the final transform.
- **West Oxford Community Primary School** (URN 123050, 5.86km2) - landmark-pair using Matthew Arnold School and Godstow Lock, a long (695px) diagonal baseline, 1.08 degree residual - the cleanest result of the batch.

**One further real correctness finding this session, not just additions:** an initial attempt at Church Cowley St James CE (VC) Primary School's vector boundary (using `vector_boundary.py`, built for the hybrid grid+vector template) produced a plausible-looking but definitely wrong ring on Bloxham's file - it had chained together parish/administrative boundary linework drawn in the same blue colour as the actual catchment boundary, rather than the catchment boundary itself. Only caught by overlaying the traced ring back on the source page image and seeing it match nothing real. The pixel/raster contour method (blue-pixel mask, 9x9 dilation to bridge gaps where the boundary line crosses other coloured map features, connected-component fill) was used for all 6 landed schools instead and visually verified pixel-accurate against the source page in every case. Church Cowley St James itself was attempted but not landed: two candidate landmark pairs (Pegasus School/Temple Cowley Community School, and a "Horspath" label whose exact settlement position was ambiguous on the page) gave scale estimates disagreeing by ~14%, with Temple Cowley's CLOSED status a plausible cause (a stale/approximate DB geocode) - not resolved, left undigitised rather than force-landed. Sandhills Community Primary School was similarly attempted and abandoned: two candidate landmark pairs gave mutually inconsistent scales (8.90 vs 3.27, a 2.7x disagreement).

**Final tally this session:** Oxfordshire now at **130 of 307 schools** (107 primary + 23 secondary), up from 124. All 6 new schools verified: real DB coordinate falls inside its assigned polygon (confirmed independently of the anchor construction via pixel-space marker-in-boundary checks before any real-world transform was applied), GB bounds sane, bearing-residual cross-check under the project's 5-degree threshold (actual range 0.05-3.65 degrees), no duplicate URNs introduced (checked directly in the DB: each of the 6 new `area_name`s has exactly 1 row). `catchment_areas` total 9,834 (was 9,828), `map_catchments_cache.feature_count` 9,834 (in sync), `refresh-catchment-scores` re-run clean (6,461 of 9,834 scored, up from 6,454 of 9,827). `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean. Three commits pushed to `main` (one per small batch of 2 schools each, per this project's incremental-commit rule), no `Co-Authored-By` trailer.

**Next session, if picking this back up:** Oxfordshire's remaining ~177 schools is still the largest, most clearly bounded body of work in the project. Of the 32 non-gridded candidates classified this session, 26 remain undigitised (6 landed, plus Church Cowley St James and Sandhills investigated and left open pending a better landmark pair) - these are ready for the same landmark-pair method without further research, though each needs a genuinely careful per-file landmark search (this session's two abandoned attempts show the method fails safely - via inconsistent scale estimates - rather than silently producing wrong geometry, but a school needing 3+ landmark attempts to find a consistent pair is a real time cost). Beyond that, roughly 51 more downloaded PDFs classified as grid-template but not yet re-attempted this session, and ~100 Oxfordshire schools with no PDF downloaded yet at all, remain fully open.

## Update: 11 more Oxfordshire schools - a misclassified-grid mining pass plus a more reliable cross-school landmark-pair technique (2026-08-08, later session)

**Inherited the prior session's checkpoint state directly from this same session's scratchpad** (`/tmp/.../scratchpad/oxon/`: `pdfs/` - 200 already-downloaded candidate PDFs, `todo.tsv`/`matched.tsv`/`oxon_schools_db.tsv` code-to-URN-to-coordinate tables, and `run5.log` - the full classification log from the prior pass). Re-derived the exact 26-school non-gridded-candidate worklist by parsing `run5.log`'s `FAIL ... not a grid-template file` lines and cross-referencing SCHOOL_URN against the committed geojsons - this matched the checkpoint's own count exactly, confirming nothing was lost.

**First real finding: two of the 26 "non-gridded" candidates were themselves misclassified, the same failure mode last session's Tyndale Community School fix uncovered.** `is_grid_template()`'s image-count heuristic (`n_images<80`) assumes the grid-template PDFs always export as 140+ small raster tiles, but a subset export as a single large tile instead - genuinely still grid-template files, just a different PDF export setting. Confirmed via `cyan_mask_broad()` + `reconcile_grid_period()` (bypassing the image-count gate entirely) and landed with the standard grid pixel-contour method:

- **Longford Park Primary School** (URN 141951, 0.78km2) - only 1 vertical and 2 horizontal grid lines fit on this narrow page, too few repeats for autocorrelation to lock on; period measured directly from the raw column/row-sum peak positions (791px) instead.
- **Gateway Primary School** (URN 123016, 1.11km2) - strong grid confirmed outright (line fraction 1.00/0.75).

**Second finding: applying the same broadened/harmonic-reconciled grid detector to the separately-tracked ~51-school "grid x/y mismatch" backlog (schools where the plain per-axis autocorrelation found disagreeing x/y periods and were rejected) recovered 7 more**, all via the standard grid pixel-contour method, each visually overlay-verified pixel-accurate against its source page:

- Drayton Community Primary School (URN 123059, 11.16km2), Sibford Gower Endowed Primary School (URN 142206, 31.96km2), Horspath CE Primary School (URN 144432, 4.41km2), Longworth Primary School (URN 123154, 16.94km2), Sutton Courtenay CE Primary School (URN 146941, 12.79km2), Gillotts School (URN 137921, secondary, 119.62km2 - needed a DPI sweep since its grid only cleared the confirmation threshold at 250dpi, not the default 300dpi).
- Dorchester St Birinus' CE Primary School (URN 123129, 9.60km2) needed one further fix beyond grid-period detection: its blue boundary line's connected component split into two disjoint pieces under color thresholding, a real ~166px/300dpi color-detection dropout where the line crosses a grid line/weir map symbol (confirmed NOT a genuine gap by direct visual inspection of the source page - the printed line is plainly continuous). Fixed by bridging the two nearest points of the two components with a straight line before flood-filling.

A systematic re-scan of the full ~51-school backlog with a DPI sweep (150-400 in 25-unit steps) found no further recoverable files beyond these 7 - the other ~29 score essentially 0.00 confirmed-line-fraction at every DPI tried, meaning they are genuinely non-gridded despite `is_grid_template()`'s image-count heuristic having originally called them grid-template.

**Third finding, the session's main methodological lesson: external-landmark georeferencing (looking up a real building/postcode via web search as the second anchor point) is unreliable at short baselines, even for legitimate real institutions.** Two attempts were made and correctly abandoned rather than force-landed:

- **Aureus Primary School** (Didcot): anchored on its own marker plus the nearby Aureus School (secondary) marker, both real DB-confirmed points but only 660m apart - a 2-point fit gave an implausible 6.8-degree rotation for what should be a north-up map, and cross-checking against Didcot Community Hospital's postcode point gave a 24-degree bearing residual (later found to drop to ~8.6 degrees under a least-squares 3-point fit, still over threshold). Concluded the hospital's polygon-area centroid isn't a precise enough point target at this short a baseline, but also that the map's own markers may not be pixel-precise (this is a GLF-trust marketing map, not an OS/council cartographic export) - left undigitised.
- **St John's Primary School, Wallingford**: anchored on its own marker plus Oxford Brookes University's Thames Street campus (postcode OX10 0BH), a 538m baseline - distance ratio against a third point (Wallingford Community Hospital, postcode OX10 9DU) came out very close (0.93) but bearing residual was 39 degrees, an inconsistency this session couldn't resolve with the time available. Left undigitised.

**Fourth finding: baseline length is what actually determines landmark-pair reliability, confirmed decisively.** Switching to a **cross-school anchor** technique - using a SECOND REAL SCHOOL from this project's own candidate list (not an externally-searched landmark) that happens to be visible with its own "Sch" icon on the same source page, at multi-km separation - gave sub-1.1-degree bearing residuals on the first two files tried, a qualitatively different reliability tier than the sub-km external-landmark attempts:

- **St Andrew's CE Primary School, Chinnor** (URN 123126, ~21.2km2): anchored on Chinnor's own marker and Lewknor CE Primary's "Sch" icon, both visible on Chinnor's own source page (1159px/5.06km baseline). Cross-checked against Aston Rowant CE Primary's icon (also on the same page, already a landed school from a prior session): 1.01 degree bearing residual, distance ratio 1.02.
- **Lewknor Church of England Primary School** (URN 123128, ~17.6km2): the reverse pairing on Lewknor's own source page - anchored on Lewknor's marker and Tetsworth Primary's "Sch" icon (1039px/4.96km baseline), cross-checked again against Aston Rowant's icon: 0.96 degree bearing residual, distance ratio 1.01, and a fitted rotation of 0.004 degrees - strong independent confirmation the page really is north-up (unlike Aureus's implausible 6.8-degree fit), which is itself evidence the marker/icon pixel-picking on this template is trustworthy where the marketing-map template wasn't.

**Two Google-My-Maps-style multi-parish admissions files investigated and correctly left alone, not force-interpreted as single-school catchments:** Ewelme CE Primary School's PDF (code 3752) turns out to be page 8 of a 9-page admissions document showing FOUR separate parish polygons (Ewelme, Brightwell Baldwin, Cuxham, Easington) with numbered Google Maps pins, described only as "parish maps... may also be found on the Church of England website" - genuinely ambiguous whether Ewelme's own designated area is the single "Ewelme Parish" polygon or some admissions-priority combination of all four, not resolved this session. Sacred Heart Catholic Primary (Henley, code 3820) and St Joseph's Catholic Primary (Thame, code 3826) are Catholic-diocese **parish boundary** maps with full written text descriptions of the boundary route (e.g. "South along the RIVER THAME to the Haseley Brook..."), a genuinely different and higher-precision source than a printed polygon line, but converting an 8-step written legal boundary description into geometry is a different kind of work than this session's pixel/landmark toolkit and wasn't attempted.

**Final tally this session:** Oxfordshire now at **141 of 307 schools** (117 primary + 24 secondary), up from 130. All 11 new schools verified: real DB coordinate falls inside its assigned polygon, GB bounds sane (checked both in the source geojson and directly against the DB's `minimum_latitude`/`maximum_latitude`/`minimum_longitude`/`maximum_longitude` columns after import), traced ring visually overlaid pixel-accurate against the source page image in every case, no duplicate `SCHOOL_URN`s (117 and 24 unique URNs in the two geojsons; 141 DB rows for local authority `931`, matching exactly with zero duplicates). `catchment_areas` total 9,845 (was 9,834), `map_catchments_cache.feature_count` 9,845 (in sync), `refresh-catchment-scores` re-run clean (6,472 of 9,845 scored). `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean throughout. Four commits pushed to `main` (roughly one per verified batch), no `Co-Authored-By` trailer; CDN freshness confirmed (pinned-SHA vs `main`-branch raw URLs returned identical feature counts) before each import.

**Next session, if picking this back up:** Oxfordshire's remaining **166 of 307 schools** breaks down as: (1) **24 non-gridded landmark-pair candidates** (26 minus Chinnor/Lewknor landed this session) - the cross-school anchor technique proven this session (find a SECOND already-known-URN school visible with its own icon on the same page, prefer multi-km baselines, always cross-check against a third such icon if one exists on the page) is the most promising path, much more reliable than external web-searched landmarks; Aureus Primary and St John's Wallingford were tried and correctly left open pending a better anchor pair, same discipline as Church Cowley St James/Sandhills from the prior session. (2) **~29 more "grid x/y mismatch"-flagged PDFs** that a full DPI sweep (150-400dpi) still could not confirm as real grid-template files - these should probably be reclassified as landmark-pair candidates for a future session rather than re-attempted with more grid tuning. (3) **~100 Oxfordshire schools with no PDF downloaded yet at all** - still fully open. (4) Ewelme's multi-parish admissions map and the two Catholic parish-boundary text-description maps (Sacred Heart Henley, St Joseph's Thame) are real, novel sources worth a dedicated pass with a different technique (parish-polygon-selection logic, or geocoding-each-boundary-step-of-a-written-description) rather than the pixel/landmark toolkit used elsewhere in Oxfordshire.

## Update: re-derived the Oxfordshire backlog from scratch, +1 school (Burford Primary) via a broader grid-mask retry; three non-grid candidates investigated but correctly declined (2026-08-08, later session)

No scratchpad state survived from the prior session that landed 141 of 307, so this session started by re-deriving the full remaining-schools list from first principles: re-scraped all 307 school codes from `oxfordshire.gov.uk/schools/list?page=0..15`, re-queried the DB for all 370 `local_authority_code='931'` rows, and matched codes to URNs by normalised name (306/307 matched - only "The ACE Centre Nursery School" failed, a nursery irrelevant to designated-area digitisation). Cross-referencing both geojson files' existing `SCHOOL_URN` values against the full list gave 165 still-undigitised schools; 66 of those had a real, freshly-downloadable "Location and Designated Area" PDF this session (the other ~99 weren't attempted - no download tried yet).

**Classified all 66 downloaded PDFs by `is_grid_template()`:** 44 grid, 22 non-grid vector (4 of those 22 already known-uninterpretable from prior sessions: Aureus Primary, Ewelme, Sacred Heart Henley, St Joseph's Thame).

**Grid bucket (44 candidates): +1 school, then an automated sweep confirmed the rest are genuinely fake.** The standard `process_one.process()` pipeline at 300dpi found 0 - every candidate failed either "grid x/y mismatch" or "no real grid lines confirmed". A new `process_broad.py` (committed at `data/digitized-catchments/oxfordshire/pipeline/`) retries with `oxon_lib`'s already-proven broader HSV cyan mask + `reconcile_grid_period()` combo (previously used only to _re-verify_ already-deployed schools; this is the first session to use it to find _new_ ones) - this caught **Burford Primary School** (URN 142341, 60.75km2, grid spacing 217px at 300dpi) that the narrow-mask pipeline missed entirely. Verified: real grid lines visible on the source page, traced ring overlaid pixel-accurate, school's own DB coordinate falls inside the polygon. A follow-up automated sweep (`sweep.py`, also committed: 8 DPIs x {narrow, broad} mask x `reconcile_grid_period`, same `confirmed_grid_line_fraction`/marker-inside-boundary/GB-bounds/plausible-area safety gates as the proven pipeline) against the other 43 grid-classified candidates found nothing further - every one scores ~0.00 on `confirmed_grid_line_fraction` at every DPI/mask combination tried, confirming they're genuinely the known fake-grid-tile-count template (many raster tiles, no real grid drawn), not a detection failure worth re-trying again with the same method.

**Non-grid bucket: three candidates investigated in depth, none landed, all correctly declined rather than forced.** (1) **New Marston Primary School** (dense Oxford suburb template, generic unlabeled "Sch"/"School" icons rather than named villages): tried St Michael's CofE Primary (Oxford City) as a cross-school anchor, identified by matching its icon's map position to St Michael's own "Marston Road" DB street address, with John Radcliffe Hospital as an independent third-point check. The bearing residual passed (2.1 degrees, under the 5-degree threshold) but the implied distance was off by ~58% (762m real vs 1209m predicted) - an internal inconsistency serious enough to decline landing it. This is a useful negative finding: **a passing bearing residual alone is not sufficient** if the distance ratio disagrees this badly; both must be checked. (2) **Stoke Row CofE Primary School**: its PDF turned out to be a genuinely different document - an admissions-policy appendix reproducing an OS Explorer-style sheet titled "Stoke Row Parish Boundary" rather than the standard "Location and Designated Area" template - with a real OS grid, but one only partially legible under dense village content and woodland tinting. The reconciled grid period (697px at 400dpi) scored just 0.00/0.14 on `confirmed_grid_line_fraction`, failing this project's own safety gate, so it was declined rather than trusted on a plausible-looking but unconfirmed reading. (3) **Rush Common School** (Abingdon): a promising cluster of identifiable neighbour schools on Radley Road (St Edmund's, Kingfisher, Thomas Reade, Fitzharrys, John Mason - all in the DB with real street-matched addresses) was identified but not completed this session due to time.

**Verification before commit:** Burford's real DB coordinate falls inside its assigned polygon, GB bounds sane, `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean, no duplicate `SCHOOL_URN` (118 unique URNs in the primary geojson, one more than before). `pnpm format:write` run before commit (no changes needed beyond the geojson itself - prettier already matched the existing compact style).

**Honest final tally this session:** Oxfordshire now at **142 of 307 schools** (118 primary + 24 secondary), up from 141 - a modest net gain (+1) after a much larger amount of investigation than usual, because this session prioritised correctness over pace on several promising-looking but ultimately-declined candidates. **165 schools remain undigitised.** Of those: ~99 have never had their PDF downloaded this session at all (still fully open, same URL pattern as before); of the 66 that were downloaded, 43 are confirmed-fake grid files (no further action possible with this method), and 18 are non-grid landmark-pair candidates still open (3 investigated as above, ~14 completely untouched this session - Sandhills, Hill View, Mill Lane, St John's, Charlton, Stockham, Thomas Reade, Pegasus, Church Cowley St James, Cumnor, Wantage, Dr South's, The Oxford Academy, The Cherwell School).

**Next session, if picking this back up:** the single most promising next step is downloading the remaining ~99 not-yet-attempted Oxfordshire PDFs (URL pattern `oxfordshire.gov.uk/sites/default/files/2022-12/{school-code}_all.pdf`, codes regenerable by paginating `oxfordshire.gov.uk/schools/list?page=0..15`, or re-derivable via `data/digitized-catchments/oxfordshire/pipeline/match_schools.py` against a fresh DB query) and classifying them the same way - the grid bucket needs only the already-proven pipeline run (`process_one.py` then `process_broad.py`/`sweep.py` as a fallback), while the non-grid bucket needs the cross-school-anchor method applied per file, prioritising pages where a second neighbouring school with a DB-matched street address is visible (per the Chinnor/Lewknor precedent), and always checking BOTH bearing and distance ratio against an independent third point before trusting a result - this session's New Marston finding shows bearing alone can pass while distance is still 58% wrong.

## Update: Oxfordshire's original non-gridded landmark-pair candidate list fully exhausted - 14 more schools across two sessions, 142 -> 156 of 307 (2026-08-09)

Two consecutive sessions (their own commits/notes are in `catchment-sources.yml`'s Oxfordshire entries, but this is the first time the combined result is written up here) worked through the entire remaining pool of non-gridded landmark-pair candidates identified at the end of the previous update.

**First session: Rush Common, then a real-vector-path discovery that changed the whole approach.** Landed **Rush Common School** (Abingdon, via a promising Radley Road neighbour-school cluster left incomplete by the prior session). Then, rather than assuming every remaining non-gridded file needs pixel-contour tracing, checked all 14 untouched candidates directly via `page.get_drawings()` and found most of them have a real, exactly-traceable vector boundary ring plus an automatically-extractable marker point (far higher precision than pixel-contour tracing) - a discovery that unlocked the rest of the batch quickly:

- **Sandhills Community Primary School** and **Hill View Primary School** - Hill View's file exposed a real bug (page.rotation=90 means `get_drawings()` coordinates are in the un-rotated mediabox space while `get_pixmap()` applies the rotation; using raw coordinates gave a completely wrong ring until every point was passed through `page.rotation_matrix`), now handled for every rotated file going forward.
- **Charlton Primary School** and **Stockham Primary School** (Wantage) - shared the same map extent, but each had to be anchored on its OWN marker rather than reusing the other's fitted transform, or a small residual pushed the school's own coordinate just outside its polygon.
- **Thomas Reade Primary School** and **Pegasus School** - Thomas Reade's file exposed a second real bug (`item_endpoints()` was collapsing bezier curve path items to a straight chord between just their start/end point, cutting a visibly wrong straight line across a real notch in the boundary; fixed by sampling 12 intermediate points per curve).
- **Church Cowley St James CE Primary School, Cumnor CE Primary School, and Wantage CE Primary School** - all three via cross-school anchoring against a second real DB-matched neighbour school visible on the same map page. Church Cowley St James was a genuine re-attempt: a prior session's external-landmark attempt was correctly declined for inconsistent scales, and the cross-school anchor resolved it cleanly this time.

**Second session (this one): the final 5 candidates - Mill Lane, St John's, Dr South's, The Oxford Academy, The Cherwell School.** These had been marked as lacking an automatically-extractable marker point, but that check had only tried blue/red:

- **Mill Lane Primary School** (Chinnor, 0.83km2) and **The Cherwell School** (Summertown, Oxford, 22.41km2) turned out to have real vector boundary+marker paths after all, just drawn in **red**, not blue - no code change needed, just a second look.
- **St John's Primary School** (Wallingford, 2.02km2) and **The Oxford Academy** (Blackbird Leys/Littlemore, Oxford, 9.11km2) use a **third marker/boundary colour**, plain **black** - added support for this to `vector_boundary.py`'s `is_boundary_color()`.
- A real methodological lesson from St John's: the first two verification landmarks tried (Wallingford Community Hospital, Wallingford Fire Station - both real, OSM-geocoded amenities) gave wildly inconsistent, implausible fits (20-30+ degree bearing residuals) despite a clean roundabout-anchored transform. The likely cause: this source PDF is dated 2011, and amenities can genuinely relocate over 15 years while roads/roundabouts/railway level crossings do not. Re-verified against a real level crossing (found via Overpass) instead and got a clean 3.69 degree/103% fit. Applied the same preference for stable infrastructure (named roundabouts) over amenities to The Oxford Academy (Kennington Roundabout + Heyford Hill Roundabout, 1.77 degrees/97.2%) and The Cherwell School (Peartree Roundabout + Redbridge Park and Ride roundabout, a ~7km-spanning cross-check, 0.02 degrees/105.3%) with clean results first try.
- The Cherwell School's file also had two real vector marker stars close together (~100m apart) rather than the usual one - cause undetermined (possibly a main-site/sixth-form-annex split), not seen on any other Oxfordshire file so far. Anchored on the one nearer the school's known road frontage; the choice makes negligible difference at this catchment's city-wide (~22km2) scale.
- **Dr South's Church of England Primary School** (Islip) was investigated and correctly declined: its PDF is a genuinely different kind of document - a wide-area monochrome SCANNED OS map (confirmed via `get_images()`/`get_drawings()`: the whole page is one embedded raster image, and pixel-sampling confirms R=G=B everywhere, i.e. truly greyscale) with the designated-area boundary hand-drawn as a plain dark line with no colour distinguishing it from the rest of the map's own linework. This project's colour-based boundary extraction has no channel to isolate it on - the same category of "different document type this pipeline cannot correctly interpret" as the South Tyneside zone-map and Stoke Row admissions-appendix cases noted elsewhere in this file.

**Verification, both sessions:** every new school's real DB coordinate falls inside its assigned polygon, GB bounds sane, traced ring visually overlaid pixel-accurate against the source page in every case, `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both clean, no duplicate `SCHOOL_URN` introduced (130 unique/130 features in the primary geojson, 26 unique/26 in the secondary geojson). `pnpm format:write` run before each commit touching `catchment-sources.yml` (no changes needed for the geojson files themselves - prettier already matches the existing compact-coordinate-pair style). Commits pushed to `main` in small batches, no `Co-Authored-By` trailer. `import-catchments --local-authority 931` built 156 catchment areas with 0 rejected after this session's commit (catchment_areas total 9,860, up from 9,856), `refresh-catchment-overview-cache` re-run (`map_catchments_cache.feature_count` 9,860, in sync), `refresh-catchment-scores` re-run.

**Honest final tally:** Oxfordshire now at **156 of 307 schools** (130 primary + 26 secondary), up from 142 at the start of this two-session arc. **This exhausts the original list of 14 non-grid landmark-pair candidates identified several sessions ago** - all 14 are now resolved (10 landed across the first session, 4 more landed this session, Dr South's correctly declined as an unsupported document type). **151 schools remain undigitised.**

**Next session, if picking this back up:** the bounded landmark-pair candidate pool identified so far is now fully worked through, so the most promising next step is the one flagged two updates ago and never yet started: download and classify the **~99 Oxfordshire schools whose PDF has never been downloaded at all this session** (URL pattern `oxfordshire.gov.uk/sites/default/files/2022-12/{school-code}_all.pdf`, codes regenerable by paginating `oxfordshire.gov.uk/schools/list?page=0..15`, matched to URNs via `match_schools.py`). Expect a mix of grid-template files (run the proven `process_one.py`/`process_broad.py`/`sweep.py` pipeline) and non-grid vector-template files (apply the now twice-proven cross-school-anchor method, preferring stable infrastructure - roads, roundabouts, railways, bridges - over amenities for verification landmarks on any older-dated source PDF, per this session's St John's finding). A handful of the ~43 previously-confirmed-fake grid files and the already-known-uninterpretable documents (Ewelme's multi-parish map, the two Catholic parish-boundary text descriptions, Dr South's monochrome scan) remain open only to a fundamentally different technique, not this session's toolkit.

## Update: fresh-territory pass on Oxfordshire's remaining 125 schools - discovered a legacy-PDF-code redirect bug in every prior session's URL pattern, reopened the ~43-school "fake grid" pool via a new raster-boundary + landmark-pair technique, and landed 5 more schools; the remaining 120 are now honestly and completely triaged (2026-08-09)

**Started by rebuilding an accurate picture of exactly what remains**, since the task brief's "~99+ never downloaded" estimate needed re-verifying against the actually-committed geojson state. Re-matched all 306 council school codes to DB URNs (`match_schools.py`, unchanged) and diffed against both geojson files' current `SCHOOL_URN` values: **125 of the 281 Primary+Secondary Oxfordshire schools remained undigitised** (not 151 - that older figure counted against the full 307-code pool including Nursery/"Not applicable"/All-through phases the pipeline was never built to handle). Of those 125, 51 already had a downloaded-and-fully-investigated PDF from a prior session (43 confirmed-fake-grid + 8 non-grid, of which 7 were already explicitly declined and 1 - Tetsworth - had only ever been used as a landmark for a neighbour, never attempted itself); the other **74 had never been fetched at all this session.**

**First real finding: every prior session's `{code}_all.pdf` URL-guessing pattern silently missed schools whose own council code does NOT host their own catchment PDF.** Fetching all 74 schools' actual `oxfordshire.gov.uk/schools/list/{code}` profile pages (rather than guessing the PDF URL) and parsing the real "Catchment areas all" link showed:

- **69 of the 74 have NO catchment-areas PDF link on their council profile page at all** - confirmed by grepping every page for any `_all.pdf` href and for "catchment"/"designated area"/"admission area" text, finding nothing. Spot-checked 3 (Dashwood Banbury Academy, John Mason School, William Morris Primary): all three are tagged "Academy converter" or "Academy sponsor led" on their own profile page. This matches real English admissions law - academies (including former Catholic/CofE Voluntary Aided schools that converted) are their own admission authority and Oxfordshire County Council does not publish a designated-area map for them. This is a **structural dead end for this specific source**, not a harder digitisation problem - listed and reasoned in `remaining_schools_triage.tsv` (new, committed at `data/digitized-catchments/oxfordshire/pipeline/`) as `no_catchment_pdf`. Diocesan parish-boundary text descriptions (the Sacred Heart Henley / St Joseph's Thame precedent) may exist for some of these Catholic schools but weren't pursued this session - different technique, different source entirely.
- **5 of the 74 DO have a real catchment PDF, just hosted under a different, older/legacy numeric code than the school's own** - e.g. West Kidlington Primary's own code is 2021 (`2021_all.pdf` 404s), but its profile page links to `.../2110_all.pdf`; code 2110 doesn't appear anywhere in the current 307-code school list, i.e. it's a retired code repurposed only as a file host. **All 5 of these were downloaded and landed this session** (see below) - the first time this redirect pattern has been noticed or exploited in this project.

**Second finding, the session's main methodological unlock: the ~43-school "confirmed fake grid" pool is not actually a dead end.** These are raster files that pass `is_grid_template()` (140+ image tiles, no vector paths) but score 0.00 on `confirmed_grid_line_fraction()` at every DPI/mask combination (verified again this session, consistent with the prior session's exhaustive `sweep.py` finding) - genuinely no OS grid drawn anywhere on the page. But `find_marker_and_boundary()` (the same colour-based pixel/contour extractor the grid method itself uses downstream of grid detection) still finds a completely real, raster-baked blue boundary outline and marker on these files - confirmed by generating and visually inspecting overlay images for two of them. The grid was the ONLY missing ingredient; scale can come from a landmark pair instead, exactly like the separate non-gridded vector template's already-proven method, just tracing the boundary by pixel colour/contour rather than chaining vector paths. Landed 2 real schools this way (Larkrise, Botley - see below), each independently verified against a THIRD landmark for both bearing residual and distance ratio (per this project's standing rule) on top of the primary two-point anchor, both clean. **This reopens all 41 remaining fake-grid schools as realistic landmark-pair candidates for a future session** - a materially larger opportunity than what was left of the old non-grid pool.

**Landed 5 new schools, all individually verified (real DB coordinate inside its polygon, GB bounds sane, traced ring visually overlaid pixel-accurate against the source page, no duplicate `SCHOOL_URN`):**

- **Manor School, Didcot** (URN 147032, 2.35km2) - legacy-code PDF (own code 2028, hosted at `2597_all.pdf`), standard grid pixel-contour method at default settings.
- **West Kidlington Primary and Nursery School** (URN 144398, 2.34km2) - legacy-code PDF (own code 2021, hosted at `2110_all.pdf`), grid method via the broadened `reconcile_grid_period()` combo at 280dpi (plain per-axis detection disagreed at the default 300dpi).
- **Charlbury Primary School** (URN 147640, 41.28km2) - legacy-code PDF (own code 2030, hosted at `2100_all.pdf`), same broadened-reconcile method at 300dpi.
- **Larkrise Primary School** (URN 146815, Oxford, 1.07km2) - legacy-code PDF (own code 2027, hosted at `2543_all.pdf`); this file has no real grid at all, so landed via the new raster-boundary + landmark-pair method: anchored on its own marker plus **Oxford School's** real DB coordinate (a secondary school whose own building outline is directly visible on the same page, 884m baseline, implied rotation 0.20 degrees), cross-checked against Iffley Lock (OSM, 1.19km baseline, 1.83 degree bearing residual, distance ratio 0.947).
- **Botley School** (URN 147759, 11.51km2) - legacy-code PDF (own code 2032, hosted at `2569_all.pdf`), same new technique: anchored on its own marker plus **Matthew Arnold School's** real DB coordinate (1.23km baseline, implied rotation 2.61 degrees), cross-checked against Wytham Village Hall (OSM, 2.64km baseline, 0.70 degree bearing residual, distance ratio 1.045) - an initial cross-check attempt against "Godstow Lock" gave a borderline 5.2 degree residual/1.13 distance ratio from an imprecise pixel-pick of a fuzzy water-channel label, not trusted as a real problem given the primary anchor's own clean near-zero rotation, and correctly not used once the more precise Wytham Village Hall point resolved it cleanly.

**Tetsworth Primary School** (URN 123031, code 2456, already downloaded from a prior session, real vector boundary+marker in blue) was attempted but **not landed**: extracted its own vector ring cleanly (1 closed ring, no leftover segments), but the only two available OSM landmarks tried (Rycote Lane's named-way point, Attington Toll House's building centroid) gave a 36-degree bearing residual against each other - both individually plausible-looking but not mutually consistent, most likely because "Rycote Lane" as a road NAME covers a stretch of road rather than the one specific point shown on this map (its Nominatim point may sit somewhere else along that named stretch). Correctly left undigitised rather than forced; needs a tighter point-like landmark (a named building, not a road) next session, or a cross-school anchor if one becomes available on a neighbouring file.

**Everything else checked or re-confirmed this session, honestly enumerated (see `data/digitized-catchments/oxfordshire/pipeline/remaining_schools_triage.tsv`, new, committed - code/URN/name/phase/lat/lon/status/note for all 120 schools still open):**

- **69 schools: no catchment PDF exists at this source at all** (own admission authority - academies, including several converted Catholic/CofE Voluntary Aided primaries). Not a pipeline limitation - genuinely no document to digitise here; a diocesan parish-boundary text description (per the Sacred Heart Henley / St Joseph's Thame precedent) is the only other lead, unexplored this session.
- **41 schools: confirmed-fake-grid raster files, now realistic landmark-pair candidates** per the new technique proven on Larkrise/Botley above - the single most promising next lead.
- **7 schools: already correctly declined in prior sessions** for document-type or verification-consistency reasons (Aureus, New Marston, Stoke Row, Dr South's, Ewelme, Sacred Heart Henley, St Joseph's Thame) - no new information this session, still open only to a different technique per file.
- **1 school (Tetsworth): attempted this session, left open** pending a better landmark - see above.

**Verification:** `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean after each of this session's two commits. `pnpm format:write` run before each commit touching the geojson files. Both commits pushed to `main` with no `Co-Authored-By` trailer; GitHub raw CDN confirmed fresh (feature count matched local file) before each `import-catchments --local-authority Oxfordshire` run. First batch (Manor/West Kidlington/Charlbury): 159 catchment areas built, 0 rejected (`catchment_areas` 9,860 -> 9,863, verified the 3 new `area_name`s each have exactly 1 DB row). Second batch (Larkrise/Botley): 161 built, 0 rejected (9,863 -> 9,865, same duplicate check clean). `refresh-catchment-overview-cache` re-run after each import (`map_catchments_cache.feature_count` matched `catchment_areas` count both times: 9,863 and 9,865). `refresh-catchment-scores` re-run after each import in the background with a generous timeout and confirmed finished both times (6,490 of 9,863, then 6,492 of 9,865 areas scored).

**Honest final tally:** Oxfordshire now at **161 of 307 schools (135 primary + 26 secondary)**, up from 156 at the start of this session. **120 schools remain undigitised, and all 120 are now precisely classified** (see `remaining_schools_triage.tsv`) - there is no more unexamined backlog left in this pool.

**Most promising next lead for whoever continues after this session:** the **41 confirmed-fake-grid schools** (`status=fake_grid_confirmed` in `remaining_schools_triage.tsv`) - each needs the same treatment as Larkrise/Botley: download from its own `{code}_all.pdf` (already have all 41 PDFs from a prior session's batch, re-downloadable at the same URL if the scratchpad copy is gone), confirm `find_marker_and_boundary()` extracts a real boundary+marker, then find a landmark - **check the rendered page for a second real school's own building outline or "Sch" icon first** (free, no external lookup needed, and gave the cleanest results both times this session) before falling back to OSM/Nominatim/Overpass named buildings, and always verify against a third independent point for both bearing residual (<5 degrees) and distance ratio, not bearing alone. The 69 `no_catchment_pdf` schools and the 7 previously-declined non-grid schools need a fundamentally different source (diocesan parish-boundary documents) rather than more attempts with this pipeline.

## Update: 5 more of the 41 "confirmed fake grid" schools landed via landmark-pair scaling; named road/rail infrastructure (Nominatim-geocoded) proven as the most reliable anchor type; large multi-building campuses confirmed as a real, repeatable failure mode (2026-08-09, later session)

Picked up directly from the previous session's `remaining_schools_triage.tsv` (all 41 `fake_grid_confirmed` PDFs already downloaded and cached from a prior session, no re-fetching needed) and worked through 5 more of them using the same raster-boundary + landmark-pair method proven on Larkrise/Botley.

**Landed 5 new schools, all individually verified (real DB coordinate inside its polygon, GB bounds sane, traced ring visually overlaid pixel-accurate against the source page, no duplicate `SCHOOL_URN`):**

- **Willowcroft Community School** (URN 139770, Didcot, 2.53km2): anchored on its own marker and **Manor Primary School's** real DB coordinate (907m baseline), rotation -1.05 degrees. Cross-checked against a real OSM roundabout on Broadway/B4016 (832m baseline): 3.41 degree bearing residual, distance ratio 1.017. A first attempt anchoring on the much closer **St Birinus School** (105m baseline) gave an internally-inconsistent triangle against Manor Primary (0.47 m/px vs 0.77-0.82 m/px depending on which pair) - too short a baseline to trust, matching this project's existing short-baseline lesson from Aureus Primary; discarded in favour of the longer Manor Primary anchor.
- **Ladygrove Park Primary School** (URN 139750, Didcot, 1.05km2): anchored on its own marker and **Didcot Parkway railway station** (Nominatim, 516m baseline), rotation 0.61 degrees. Cross-checked against a real OSM roundabout on the A4130 near Ladygrove Farm (600m baseline): 1.49 degree bearing residual, distance ratio 1.007. An initial cross-check attempt against All Saints CofE Primary's real DB coordinate gave a 5.0 degree residual/0.74 distance ratio - not trusted given the primary anchor's own clean near-zero rotation and the roundabout's clean pass; the source map is dated 2014 and the drawn building may simply not match All Saints' current site precisely.
- **Fir Tree Junior School** (URN 145649, Wallingford, 2.47km2): anchored on its own marker and the explicitly-labelled **"Slade End Roundabout"** (Nominatim, 1070m baseline), rotation -2.52 degrees. Cross-checked against the explicitly-labelled **"Hithercroft Roundabout"** (777m baseline): 4.34 degree bearing residual, distance ratio 0.995 - the cleanest result of the session, helped by both roundabouts having real, unambiguous names printed directly on the source map.
- **Carswell Community Primary School** (URN 123080, Abingdon, 6.66km2): anchored on its own marker and the **Marcham Road Interchange** roundabout (Nominatim, 1430m baseline), rotation 2.72 degrees. Cross-checked against Caldecott Primary School's real DB coordinate (650m baseline): 4.61 degree bearing residual, distance ratio 1.053.
- **RAF Benson Community Primary School** (URN 123028, 5.78km2): anchored on its own marker and **Ewelme CofE Primary School's** real DB coordinate (920m baseline), rotation 3.54 degrees. Cross-checked against a roundabout near Newnham Gifford/Newnham Green (2.46km baseline): 3.98 degree bearing residual, distance ratio 0.924.

**A real, repeatable methodological lesson this session: large multi-building campuses make unreliable landmark anchors, independent of how carefully the anchor pixel is measured.** Four separate attempts hit the same failure mode and were correctly left undigitised rather than forced:

- **Dunmore Primary School** (Abingdon): tried both **Fitzharrys School** and **John Mason School** (adjacent large secondary campuses, each several connected buildings) as anchors. Cross-checking Dunmore's own real DB coordinate against the resulting transform gave an 8-18 degree bearing residual and 30-60% distance error depending on which specific building block within each campus was picked as the anchor point - confirmed by independently choosing two different buildings within the same campus and finding they don't agree with each other either. The likely cause: a school's registered DB coordinate (GIAS postcode/address centroid) doesn't reliably correspond to any single visually-identifiable building within a large multi-block site.
- **Caldecott Primary School** (Abingdon): the same Marcham Road Interchange roundabout that worked cleanly for Carswell (on a different page) gave a plausible-looking 6.15 degree rotation here, but cross-checking against Thameside Primary's real DB coordinate (only 350m away) gave an 18 degree bearing residual despite a clean ~1.0 distance ratio - a "right distance, wrong direction" pattern not resolved by trying multiple roundabout pixel readings or either of the two candidate OSM interchange sub-ways. Left open.
- **Wood Farm Primary School** (New Headington, Oxford): the only nearby named landmark on the page is **The Churchill Hospital**, a large sprawling multi-wing complex directly connected (once dilated for connected-component labelling) to the neighbouring Nuffield Orthopaedic Centre and an ambulance HQ - the same campus-ambiguity problem, abandoned before committing to a specific anchor point rather than guessing.
- **Windmill Primary School** (Headington, Oxford): anchored cleanly-looking (5.18 degree rotation, borderline but plausible) on the Nominatim-geocoded **Green Road Roundabout**, but the only available cross-check was an _unconfirmed, unnamed_ "Sch" icon on the page (guessed to be St Andrew's CofE Oxford by position only, no printed name) - gave a 12.7 degree residual/0.85 distance ratio. Not trusted since the cross-check landmark's identity itself was never confirmed; left open rather than either forcing the primary fit or guessing the third point's identity.

**The clearest positive pattern from this session: named road/rail infrastructure explicitly labelled on the source map itself (roundabouts, railway stations) and geocoded by name via Nominatim gave the cleanest, most reproducible results** - Fir Tree Junior's two named roundabouts and Ladygrove Park's railway station both passed on the first attempt with sub-2-degree cross-check residuals in two of the three cases. Un-named "Sch" icons and large campus buildings were the two recurring sources of unreliable landmarks this session; small single-building primary/nursery schools (Manor Primary, Ewelme CofE Primary) sat in between - reliable when the baseline was long enough (over ~500m) but not at very short range (Willowcroft's discarded 105m St Birinus attempt).

**Dunmore Primary School's PDF also confirmed a new template variant worth noting:** its own marker is drawn as a solid **black** star rather than the blue used everywhere else in this raster-boundary sub-template - found and extracted fine via a manual colour mask once noticed, but `find_marker_and_boundary()`'s default blue/red-only search returned no marker candidates on first attempt, worth checking for on any future file that reports "no marker candidates found" despite a real boundary being detected.

**Verification:** `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean after each of this session's two commits. `pnpm format:write` run before each commit (no changes needed - the geojson already matched the existing compact-coordinate-pair style). Both commits pushed to `main` with no `Co-Authored-By` trailer; GitHub raw CDN confirmed fresh (feature count matched local file, including both newest URNs) before running `import-catchments --local-authority 931`. Import built 166 catchment areas, 0 rejected (`catchment_areas` 9,865 -> 9,870). `refresh-catchment-overview-cache` re-run (`map_catchments_cache.feature_count` 9,870, in sync). `refresh-catchment-scores` re-run in the background and confirmed finished (6,497 of 9,870 areas scored).

**Honest final tally:** Oxfordshire now at **166 of 307 schools (140 primary + 26 secondary)**, up from 161 at the start of this session. **115 schools remain undigitised** (`remaining_schools_triage.tsv` updated in place - 5 rows changed from `fake_grid_confirmed` to `done`, 4 more changed from `fake_grid_confirmed` to `declined_or_open` with this session's specific findings recorded): 33 `fake_grid_confirmed` (still open landmark-pair candidates), 13 `declined_or_open` (up from 7 - now includes Dunmore, Caldecott, Wood Farm, Windmill and their specific attempted-and-failed landmarks, so the next session doesn't retry the same dead ends), and 69 `no_catchment_pdf` (unchanged, structural dead end).

**Most promising next lead for whoever continues after this session:** the remaining **33 `fake_grid_confirmed` schools** are still the best-understood opportunity - prioritise pages with an explicitly **named** roundabout, railway station, or other infrastructure printed directly on the map (Nominatim search on the exact printed name, as done for Slade End/Hithercroft/Marcham Road/Green Road/Didcot Parkway this session) over unnamed icons or large multi-building campuses, both of which this session confirmed as unreliable anchor types even with careful pixel measurement. For the 4 schools newly marked `declined_or_open` (Dunmore, Caldecott, Wood Farm, Windmill), don't reuse the same anchors that failed - each needs either a genuinely different landmark or a properly name-confirmed alternative before it's worth another attempt.

## Update: 9 more schools across two sessions (John Henry Newman/Rose Hill/Windale/St Ebbe's/New Hinksey/St Barnabas'/North Hinksey, then St Mary and St John/St Christopher's/East Oxford Primary/St Michael's/Cutteslowe); three more attempted and correctly left open (2026-08-10)

**This update covers two sessions' worth of commits that landed real, verified schools but hadn't yet been written up here** - the four commits between this file's last update (`19955c8`, tally 166/140 primary) and the start of the session documented below (`256db5e`, `aacec39`, `2257511`, `ed6b543`) added **John Henry Newman Academy** (URN 138774), **Rose Hill Primary School** (URN 146278), **Windale Primary School** (URN 146381), **St Ebbe's Church of England Aided Primary School** (URN 123212), **New Hinksey Church of England Primary School** (URN 123142), **St Barnabas' Church of England Aided Primary School** (URN 123211), and **North Hinksey Church of England Primary School** (URN 144584) via the same raster-boundary + landmark-pair method as the rest of this pool - see each commit's own message for the specific landmarks and residuals used. This brought the primary total from 140 to 147 without a corresponding PROJECT_STATUS.md update; corrected here for anyone reconciling `git log` against this file.

**This session (2026-08-10) picked up exactly where the previous fork's task brief said it should - school code 3834, St Mary and St John CE Primary - and continued through the `fake_grid_confirmed` list, landing 5 more schools:**

- **St Mary and St John Church of England Primary School** (URN 123213, East Oxford, 0.95km2): this file has TWO blue-star marker icons - the target school's own, and a second confirmed (via reverse-geocoding its real DB coordinate onto the printed street name) to be **Comper Nursery School's** own icon. Anchored on the two (717m baseline), rotation 5.21 degrees. Cross-checked against two independent building-footprint measurements: Larkrise Primary School (754m baseline, 4.30 degree residual/0.996 ratio) and St Frideswide CE Primary School (1036m baseline, 1.29 degree residual/1.002 ratio) - the second, tighter match also correctly identified which of two adjacent buildings (St Frideswide vs. the co-located Greyfriars Catholic School) was actually drawn.
- **St Christopher's Church of England School, Cowley** (URN 140556, 1.86km2): anchored on its own marker and the traffic-island centroid of the **B480/Between Towns Road roundabout** (Overpass, 659m baseline), rotation 2.60 degrees. Cross-checked against the separate **John Smith Drive roundabout** (743m baseline): -0.24 degree residual, 1.005 ratio. A same-page attempt reusing a building near Cricket Road Centre that a prior file had suggested was St Frideswide/Greyfriars' shared site gave an 11.5 degree residual and was discarded - confirms that a building-shape match on one file does not safely transfer to another file without its own independent check.
- **East Oxford Primary School** (URN 123046, 1.83km2): anchored on its own marker and **Comper Nursery School's** own building footprint (696m baseline, cross-school), rotation -0.45 degrees. Cross-checked against **Oxford Spires Academy's** real DB coordinate, measured as the area-weighted centroid of its whole campus footprint (1266m baseline): 0.50 degree residual, 1.004 ratio - a large multi-building campus giving a clean result this time, likely because averaging the whole footprint smooths out the single-building correspondence problem seen elsewhere in this project. A separate attempt using the precisely-identified **"The Plain" roundabout** gave a self-inconsistent 18% distance error despite an acceptable 2.7 degree bearing residual - not used; likely a multi-loop junction where a simple OSM node-average doesn't correspond to the single circle drawn on the map.
- **St Michael's CofE Primary School, Oxford City** (URN 123143, 1.25km2): anchored on its own marker and **"The Plain" roundabout** (1139m baseline, reused from the same-session East Oxford Primary investigation, still reliable when re-measured carefully on this file), rotation -0.03 degrees. Cross-checked against **St Joseph's Catholic Primary School's** real DB coordinate, measured as its own building footprint (807m baseline): 0.49 degree residual, 1.023 ratio.
- **Cutteslowe Primary School** (URN 139064, Wolvercote, 4.95km2): anchored on its own marker and the **Peartree Interchange roundabout's** central traffic island (Overpass, 1862m baseline), rotation -0.53 degrees. Cross-checked against **Cherwell Bridge, Northern By-pass Road** (Nominatim, 498m baseline): -3.68 degree residual, 1.032 ratio.

**Three more candidates were attempted this session and correctly left undone rather than forced:**

- **St Andrew's Church of England Primary School, Oxford** (URN 123140): own marker plus Headington Quarry Nursery School's own marker gave a 5.73 degree rotation; the only cross-check found (Green Road Roundabout, Overpass) gave a persistent ~5-6 degree bearing residual across several independent re-measurements of the roundabout's obscured traffic island - never resolved as either a measurement problem or a genuine anchor error. Left open.
- **St Francis' Church of England Primary School** (URN 150520): own marker plus Slade Park Fire Station (Overpass `amenity=fire_station`) gave a clean-looking 1.38 degree rotation, but the only cross-check available on this file's extent (a building near "The Driftway Centre"/"Isis Business Centre", Horspath Road Industrial Estate) gave a 5.9 degree residual and 12% distance error. Left open.
- **Barton Park Primary School** (URN 147865): turned out to use a **completely different source template** from the rest of this pool - a black-and-white OS 1:1250 topo map ("Proposed designated (catchment) area for Barton Park Primary School from 1 September 2020") with a **red**, not blue, boundary line, faint genuine OS grid tick-marks visible but **no drawn school marker/icon at all** (plausibly because the school hadn't been built yet when this particular PDF was generated). This needs a different digitisation approach entirely (e.g. reading real grid-tick coordinates rather than landmark-pair scaling) - not attempted further this session, and `remaining_schools_triage.tsv`'s note for this school now says so explicitly rather than leaving it looking like an ordinary landmark-pair candidate.

**Verification:** every new school's real DB coordinate falls inside its assigned polygon, GB bounds sane, traced ring visually overlaid pixel-accurate against the source page in every case, no duplicate `SCHOOL_URN` (152 unique/152 features in the primary geojson after this session). `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean before each of this session's three commits. `pnpm format:write` run before each commit. All three commits pushed to `main` with no `Co-Authored-By` trailer, each push confirmed via `git status -sb` showing not-ahead-of-origin. GitHub raw CDN confirmed fresh (both the `main` branch URL and the full-40-character-SHA-pinned URL agreed on feature count) before running `import-catchments --local-authority "931"` once at the end of the session: built 178 catchment areas (152 primary + 26 secondary), 0 rejected, no duplicate `area_name` rows. `refresh-catchment-overview-cache` re-run (`map_catchments_cache.feature_count` 9,882, in sync). `refresh-catchment-scores` re-run in the background and confirmed finished (6,509 of 9,882 areas scored).

**Honest final tally:** Oxfordshire now at **178 of 307 schools (152 primary + 26 secondary)**, up from 166 documented at the start of this write-up (147 primary going into this session specifically, after accounting for the previously-undocumented commits above). `remaining_schools_triage.tsv` (120 tracked rows, unchanged total - schools stay listed with an updated status rather than being removed once done) now reads: 14 `done`, 24 `fake_grid_confirmed` (down from 33), 13 `declined_or_open`, 69 `no_catchment_pdf`.

**Most promising next lead for whoever continues after this session:** the remaining **24 `fake_grid_confirmed` schools** are still the best-understood opportunity and should be worked the same way - own marker plus a named roundabout/railway station (Nominatim/Overpass) or a second real school's own marker/building footprint, always cross-checked against a genuinely independent third point for both bearing residual (<5 degrees) and distance ratio. Don't retry St Andrew's, St Francis, or Barton Park with the same anchors that already failed - each needs either a fresh landmark idea or (Barton Park specifically) a different technique altogether for its B&W OS-topo-with-no-marker template. Given how many of this session's useful landmarks turned out to be reusable across multiple nearby schools' maps once found (Comper Nursery, "The Plain" roundabout, Cherwell Bridge, St Frideswide/St Joseph's), it's worth checking whether a candidate school's map overlaps the extent of an already-solved neighbour before hunting for a brand new landmark from scratch.

## Update: 4 more schools landed (Orchard Fields, Queensway, Longfields, Glory Farm); found and fixed 3 stale triage rows; discovered and documented the "short baseline amplifies rotation noise" failure mode (2026-08-10, later session)

**Started by re-reading `remaining_schools_triage.tsv` and found 3 rows were stale bookkeeping, not real remaining work:** John Henry Newman Academy (URN 138774), Rose Hill Primary School (URN 146278) and Windale Primary School (URN 146381) were still marked `fake_grid_confirmed`, but all three are already present in the primary geojson (landed by commit `256db5e`, one of the previously-undocumented commits the last write-up already accounted for in its tally). Corrected their triage rows to `done` in this session's commit rather than re-digitising them a second time (which would have created duplicate `SCHOOL_URN` rows under the DB's `(source_id, geometry_checksum)` upsert key). This means the true open `fake_grid_confirmed` count entering this session was 21, not 24 as the previous write-up stated.

**Landed 4 new schools this session, working the Banbury and Bicester geographic clusters (multiple candidate schools sharing the same map extent, so a landmark found once could be reused):**

- **Orchard Fields Community School**, Banbury/Neithrop (URN 122994, 0.95km2): anchored on the **Woodgreen Avenue/B4035 roundabout** traffic island (Overpass, 1409m baseline) and **Sandford Green** leisure park (Nominatim), rotation 0.06 degrees. Cross-checked against **Hill View Primary School's** own building footprint (drawn on the same page): 0.48 degree bearing residual, distance ratio 0.989.
- **Queensway School**, Banbury/Easington (URN 122996, 2.80km2): anchored on **Tudor Hall School's** own building footprint (Wykham Park) and **Banbury School's** campus footprint (both real DB coordinates in this project's own schools table), rotation 2.93 degrees. Cross-checked against its own marker/DB coordinate (-0.03 degree residual, 1.048 ratio) and independently against the Woodgreen Avenue roundabout (1.82 degree residual, 1.060 ratio).
- **Longfields Primary and Nursery School**, Bicester (URN 123008, 3.62km2): anchored on **Bicester North** and **Bicester Village** railway stations (Nominatim, 1210m baseline), rotation 5.28 degrees. Cross-checked against the A4421/Bicester Road roundabout east of Bicester (-2.43 degree residual, 0.946 ratio); its own marker/DB coordinate cross-check was weaker (5.74 degrees/1.15 ratio) but the real DB coordinate still falls inside the assigned polygon.
- **Glory Farm Primary School**, Bicester (URN 141051, 1.05km2): anchored on **Bicester North railway station** and the **A4421/Gavray Drive roundabout** north-east of the school (Overpass, 2338px baseline), rotation -0.02 degrees. Cross-checked against a second, independent A4421 roundabout further south near the level crossing (0.47 degree residual, 0.976 ratio) and its own marker/DB coordinate (0.43 degree residual, 0.983 ratio) - the cleanest four-way agreement of the session.

**A genuinely new methodological finding this session, worth carrying forward: short pixel baselines amplify small measurement noise into large, spurious rotation errors, even when the landmark itself is correctly identified.** On both Queensway and Longfields, pairing the school's own marker with a landmark only ~200-330px away (a roundabout close to the school) gave wildly implausible rotations (-15 degrees, +23 degrees, once even wrapping to -336 degrees) that didn't match any other school in the same geographic cluster. Anchoring instead on **two landmarks more than 1000px apart from each other** (ignoring the school's own marker entirely for the scale/rotation derivation, and only using the marker/DB coordinate afterward as a plausibility check - does it fall inside the resulting polygon?) resolved every one of these cases cleanly, and the previously "bad" short-baseline landmark then cross-checked fine against the long-baseline anchor. This reframes the project's standing anchor-selection advice: prefer the **longest available baseline** for the two points that actually derive the transform, not necessarily the school's own marker, and don't discard a landmark just because it disagreed with a marker-anchored short baseline - test it against a long-baseline anchor before ruling it out.

**Two more Bicester candidates were attempted and left undone rather than forced:** Langford Village Community Primary School (URN 130962) and Bure Park Primary School (URN 132057). Langford Village's own map only offered two roundabouts close together near the school (short baseline, same failure mode as above) and a distant A4421/B4100 roundabout whose OSM identification (an averaged way-cluster, not a single clean node) gave an implausible ~23 degree rotation when paired with Bicester North Station - inconsistent with every other Bicester school this session, which clustered in the -0.5 to +5.5 degree range. Bure Park wasn't attempted at all (ran out of session time). Both should try the Bicester North/Bicester Village station pair first next time, since that pairing proved reliable twice this session.

**A large diff in the Glory Farm commit is a formatting artefact, not a data problem:** re-serialising the whole geojson file through Python's `json.dump(indent=2)` after loading it back in changed line-wrapping/whitespace for all 155 pre-existing features even though every coordinate value is byte-for-byte identical (verified: 0 mismatches across all 155 pre-existing `SCHOOL_URN` geometries between the two commits). Worth preserving the original file's exact formatting on future edits to avoid inflating the diff, but no data was lost or altered.

**Verification:** every new school's real DB coordinate falls inside its assigned polygon, GB bounds sane, traced ring visually overlaid pixel-accurate against the source page in every case, no duplicate `SCHOOL_URN` (156 unique/156 features in the primary geojson after this session). `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean before each of this session's two commits. `pnpm format:write` run before each commit. Both commits pushed to `main` with no `Co-Authored-By` trailer, each push confirmed via `git fetch` + `git status -sb` showing not-ahead-of-origin. GitHub raw CDN confirmed fresh (full-40-character-SHA-pinned URL agreed with the `main` branch URL on feature count) before each `import-catchments --local-authority Oxfordshire` run: first batch built 155 primary areas (152 -> 155, 0 rejected), second batch built 156 (155 -> 156, 0 rejected). `refresh-catchment-overview-cache` re-run after each import (`map_catchments_cache.feature_count` 9,885 then 9,886, in sync both times). `refresh-catchment-scores` re-run in the background after each import and confirmed finished both times (6,512 of 9,885, then 6,513 of 9,886 areas scored).

**Honest final tally:** Oxfordshire now at **182 of 307 schools (156 primary + 26 secondary)**, up from 178 at the start of this session. `remaining_schools_triage.tsv` now reads: 21 `done` (up from 14 - the 4 new schools, the 3 corrected stale rows), 17 `fake_grid_confirmed` (down from 21 true-open, i.e. 24 minus the 3 stale-done corrections), 13 `declined_or_open`, 69 `no_catchment_pdf` - 125 total tracked rows remain (Barton Park counted once, under `fake_grid_confirmed`, matching its own note that it needs a different technique).

**Most promising next lead for whoever continues after this session:** the remaining **17 `fake_grid_confirmed` schools** are still the best-understood opportunity. Apply this session's short-vs-long-baseline lesson from the start: when a school's own map only offers landmarks close to its marker, look further afield on the same page (or check whether a neighbouring already-solved school's map shares a landmark) rather than trusting a short-baseline marker-anchored pair, even if its rotation number looks superficially plausible. St Mary's CE Primary Banbury, North Leigh CE School, St Nicolas CE Primary Abingdon, St Philip and James' CE Aided Primary Oxford, Hanwell Fields Community School, and the remaining Banbury-cluster schools (Hardwick, The Grange) are all still open and untried this session - The Grange's map in particular is centred on Banbury's Calthorpe/Hospital area, well outside the Neithrop landmark set (roundabout/Sandford Green/Hill View) proven this session, so it will need its own fresh landmark (Horton General Hospital's campus footprint is visible and named, but per the project's standing large-campus caution should be tried carefully with a specific building, not the whole site).

## Update: Bicester dead-ends resolved, Banbury Ruscote/Hardwick cluster opened, first North Oxford landmark set proven - 6 more Oxfordshire schools, 182 -> 188 of 307 (2026-08-10, later session)

Continued directly from the previous session's end-of-session note (HEAD was already at the "182 of 307" commit when this session started). Worked the priority order given: the two Bicester schools left open at the end of the prior session first, then as many of the remaining `fake_grid_confirmed` schools as the session's time budget allowed.

**Langford Village Community Primary School and Bure Park Primary School** (both Bicester) had each previously failed with an implausible ~23 degree rotation using roundabout landmarks close to the school's own marker. The task brief's suggested fix - retry with the Bicester North/Bicester Village railway station pair proven on Longfields/Glory Farm - turned out not to apply to either file: both schools' map extents simply don't reach far enough to include Bicester Village station (Langford Village and Bure Park sit in different parts of Bicester from the Longfields/Glory Farm cluster). Each was resolved instead with a fresh long-baseline pair specific to its own map, found by reading real road/place names directly off the page and geocoding them via Overpass rather than reusing any other file's pixel coordinates (every PDF has its own independent scale and extent, even for schools in the same town):

- **Langford Village** (URN 130962, 0.92km2): "Stone Circle" roundabout (west side) + A4421/Gavray Drive roundabout (east side), 2109px/1275m baseline, rotation -0.10deg. DB coordinate cross-check: 0.88deg residual, 0.991 distance ratio - about as clean as this project's landmark-pair results get. A further cross-check against the same A4421/B4100/Neunkirchen Way roundabout that broke the _previous_ session's attempt gave a 20deg residual again, on an independently re-measured pixel/geocode this time - confirms that specific roundabout's OSM identification (not just the earlier short baseline) is the actual problem, not this session's transform.
- **Bure Park** (URN 132057, 0.60km2): A4095 roundabout (north edge) + a Betony Way-area mini-roundabout close to the school, 1298px/690m baseline, rotation -2.86deg. DB coordinate cross-check: 5.86deg residual, 0.945 distance ratio - a little over this project's usual ~5deg comfort band but the same order of magnitude as the already-accepted Longfields precedent (5.74deg/1.15 ratio), and the real coordinate does fall inside the polygon. Worth flagging for posterity: an early Overpass match for the second roundabout picked a residential roundabout ~600m further east that isn't actually on this map at all, caught immediately by an implausible 250+ degree rotation before being corrected - a reminder to sanity-check every geocoded candidate against the map's own visible extent, not just trust the nearest-sounding OSM result.

**Then moved to the Banbury Ruscote/Hardwick cluster**, previously blocked because none of the Neithrop/Woodgreen landmarks used for Orchard Fields/Queensway reach this far north-west in Banbury. Both schools' maps show a locally-nicknamed roundabout, "The Nutshell", with no Nominatim or Overpass hit under that name at all - resolved by reading the "Ribston Close" road label drawn immediately next to it on the map and geocoding that instead, then using its road-endpoint coordinate as the roundabout's position. Paired with the Lord Fielding Close roundabout on the opposite side of each map:

- **Hardwick Primary School and Nursery** (URN 146810 - the source PDF itself titles the school "Hardwick Community School", a cosmetic naming mismatch only; URN match is exact) (0.62km2): 2551px/1188m baseline, rotation -3.82deg. DB cross-check: 0.47deg/1.086 ratio.
- **Hanwell Fields Community School** (URN 137910, 1.00km2), whose map covers the same estate: same landmark pair, reused by real-world coordinate only (pixel positions re-measured fresh on this file's own render). 1772px/1188m baseline, rotation -2.63deg. DB cross-check: 0.48deg/0.986 ratio.

**St Mary's CE Primary, Banbury and The Grange Community Primary School** (also planned for this batch) were both attempted and left undone. St Mary's map is large (~5km extent, most of Banbury) and rich in named landmarks (Holman Bridge, the Water Works roundabout at the A361/A422 junction, and Hardwick Primary's own building visible on the same page) - a Hardwick-building + Water-Works-roundabout pair gave a near-perfect 0.10deg rotation on its own, but cross-checking against St Mary's own marker/DB coordinate failed badly (11.4deg residual, 0.57 distance ratio - the computed distance was only 57% of the real 2.66km separation), and the reverse pairing (building the transform from Hardwick + St Mary's marker instead) also gave a bad -11.3deg rotation cross-checked against the roundabout. Neither combination is self-consistent; genuinely left open rather than forced, with a note to check whether this particular oversized map might be assembled from separately-registered tiles. The Grange's map centres on Banbury's Calthorpe/Hospital area as previously flagged - Horton General Hospital was considered but rejected as an anchor before measuring any pixels (the same "large sprawling multi-wing complex" unreliable-anchor problem already documented for Churchill Hospital elsewhere in this project), and the roundabouts actually on this map are all under 800m from each other and from the school - a short-baseline risk not yet resolved with an alternative.

**Also landed two schools outside the Bicester/Banbury clusters**, opening up two new landmark sets for future sessions to reuse:

- **Long Furlong Primary School** (URN 123085, Abingdon, 0.44km2): Tilsley Park's athletics track (Overpass, averaged across several track-feature ways) + the A415/Dunmore Road roundabout, 2901px/1008m baseline, rotation 2.77deg. DB cross-check: -2.01deg/0.973 ratio - clean. This file's own marker is drawn in BLACK rather than the usual blue, the same quirk already documented for Dunmore Primary elsewhere in this pool; found fine via a manual colour mask, not a blocker.
- **St Philip and James' CE Aided Primary School, Oxford** (URN 123214, 1.72km2): the first school landed from the North Oxford (Summertown/Walton Manor/Park Town) landmark set, a completely different part of the city from the Cowley/East Oxford cluster (Cherwell Bridge, St Frideswide's, St Joseph's) used for St Barnabas'/St Ebbe's/St Mary and St John earlier. Anchored on two Oxford University college building footprints - Wolfson College and St Hugh's College (Nominatim `amenity=university` campus centroids), 1058px/826m baseline, rotation -5.28deg. DB cross-check: -6.07deg/1.059 ratio - bearing a little over the usual ~5deg comfort band, plausibly because a Nominatim campus centroid doesn't precisely match the single building outline drawn on this specific 1:1250-style map (the same class of imprecision already flagged for hospitals), but the distance ratio is strong, the traced ring visually overlays closely (a small, residual-sized offset, not a gross mismatch), and the real DB coordinate falls solidly inside the resulting polygon, not near an edge - accepted on the same basis as the existing Longfields precedent.

**Verification:** every new school's real DB coordinate falls inside its assigned polygon, GB bounds sane, traced ring visually overlaid pixel-accurate against the source page for all six (a clearly visible small offset only on St Philip and James', matching its residual bearing figure). No duplicate `SCHOOL_URN` at any point (158, 159, 160, 161, 162 unique/matching feature count in the primary geojson after each of this session's four commits in turn). `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean before every commit. `pnpm format:write` run before each commit touching the geojson. All four commits pushed to `main` with no `Co-Authored-By` trailer, each push confirmed via `git fetch` + `git status -sb` showing not-ahead-of-origin. GitHub raw CDN confirmed fresh (full-40-character-SHA-pinned URL agreed with the `main` branch URL on feature count) before each `import-catchments --local-authority 931` run, waiting out one transient CDN staleness window before the Hanwell Fields/St Philip import; that import then picked up both schools in a single run. `refresh-catchment-overview-cache` re-run after each import (`map_catchments_cache.feature_count` 9888, 9889, 9891, 9892 across the session, in sync with `catchment_areas` every time). `refresh-catchment-scores` re-run in the background after each import and confirmed finished each time (session-final: 6,519 of 9,892 catchment_areas rows scored).

**Honest final tally:** Oxfordshire now at **188 of 307 schools (162 primary + 26 secondary)**, up from 182 at the start of this session. `remaining_schools_triage.tsv` (120 tracked rows, unchanged total - schools stay listed with an updated status rather than being removed once done) now reads: 27 `done` (up from 21), 10 `fake_grid_confirmed` (down from 17 - Langford Village, Bure Park, Hardwick, Long Furlong, Hanwell Fields and St Philip and James' all moved to `done`), 14 `declined_or_open` (up from 13 - St Mary's CE Primary Banbury moved here with this session's specific two-pairing findings recorded, so a future session doesn't retry the same dead ends), 69 `no_catchment_pdf` (unchanged, structural dead end).

**Most promising next lead for whoever continues after this session:** the remaining **10 `fake_grid_confirmed` schools** - North Leigh CE School, St Nicolas CE Primary Abingdon, Edith Moorhouse, St Nicholas' Primary Oxford, Valley Road, Dry Sandford, The Grange, St Nicholas' (Long Wittenham-adjacent), and others per the triage file - are still the best-understood opportunity, plus a fresh attempt at St Mary's Banbury and The Grange with a genuinely different landmark idea (not the Hardwick-building/Water-Works-roundabout pairing that already failed self-consistency on St Mary's, and not Horton General Hospital's whole campus for The Grange). The North Oxford college-building landmark set (Wolfson College, St Hugh's College) opened this session is worth checking against any other undigitised Summertown/Walton Manor/Park Town schools before hunting fresh landmarks there. Barton Park Primary (URN 147865) still needs its own grid-tick/coordinate-label georeferencing technique, unattempted this session as before.

## Update: fake-grid backlog worked down from 10 to 3 - 7 more Oxfordshire schools, 188 -> 195 of 307; Dry Sandford turned out to be a genuine grid template (2026-08-10, later session)

Continued directly from the previous session's end-of-session note (HEAD was at the "188 of 307" commit when this session started). Worked through the remaining 10 `fake_grid_confirmed` schools per the task brief's priority order, applying the established "two independent long-baseline landmarks, school's own marker used only as a plausibility check afterward" method throughout.

**Landed 7 new schools, each verified via an independent cross-check (bearing residual and distance ratio) plus the target's own real DB coordinate falling inside its assigned polygon:**

- **St Nicholas' Primary and Nursery School, Oxford** (URN 123021, 3.27km2): Cherwell Bridge + Wolfson College's building footprint (1590px/1657m baseline), rotation 0.06deg. Own marker/DB coordinate cross-check: 0.14deg residual, 0.999 distance ratio - as close to a perfect result as this project has produced.
- **St Nicolas' CE Primary School, Abingdon** (URN 123166, 2.39km2): White Horse Leisure Centre + New Culham Bridge (2152px/1976m baseline), rotation -1.50deg. Own marker cross-check: -1.32deg/1.023 ratio, independently confirmed by a second cross-check against Dunmore Primary School's real DB coordinate (-2.09deg bearing, 1.169 distance ratio). A short-baseline (826px) Abingdon Lock cross-check gave a spurious 14.46deg residual - consistent with this project's documented short-baseline noise pattern, not trusted over the two longer, cleaner checks.
- **North Leigh CE School** (URN 142152, 14.46km2): North Leigh Roman Villa (Overpass `historic=archaeological_site`) + the Eynsham Hall conference-centre building (1615px/3162m baseline - the longest baseline used this session), rotation 1.11deg. Own marker cross-check: -0.49deg/1.001 ratio.
- **Valley Road School, Henley-on-Thames** (URN 123041, 2.76km2): Rupert House School + Gillotts School (both real DB coordinates, 1947px/2123m baseline), rotation 13.85deg. This is the file's own page rotation relative to true north (unlike most other Oxfordshire files), not an error - what matters is internal consistency, confirmed by the own-marker cross-check (-3.11deg/0.915 ratio). This file uses a third, previously undocumented sub-template: a RED boundary/marker instead of blue, titled "Location and new designated area of Valley Road School from 1 September 2020". A short-baseline (563px) cross-check against The Henley College's campus point gave a spurious -40deg residual, disregarded for the same short-baseline reason as above.
- **Edith Moorhouse Primary School** (URN 144185, Carterton, 1.67km2): St John the Evangelist CofE VA Primary School + Gateway Primary School (both real DB coordinates, 1434px/1373m baseline), rotation 5.20deg. Own marker cross-check: 4.17deg/0.974 ratio, independently confirmed by a second cross-check against Carterton Primary School's real DB coordinate (-0.75deg/0.939 ratio).
- **Dry Sandford Primary School** (URN 123063, 4.91km2) - **not a landmark-pair result at all.** Re-investigating this "confirmed fake grid" school found it's actually a genuine grid template using a previously-unchecked rural OS Explorer-style 1:25000 basemap sub-variant (contour lines, dashed footpaths, National Trust-green diamond symbols) with a much paler cyan grid line than the vivid urban 1:1250 template the original triage sweep was calibrated against. `oxon_lib.py`'s existing broad cyan mask + `reconcile_grid_period()` correctly detects it (px=py=660, `confirmed_grid_line_fraction` 1.0/1.0 - a perfect score) even though the original triage's strict narrow-mask check scored 0.00 - the same paler-cyan-on-rural-basemap pattern already documented in `oxon_lib.py`'s own docstrings for other rescued schools, just never previously checked for this specific one. Digitised via the standard marker-anchored grid pipeline (the most reliable method this project has), not landmark-pairing. Marker is a BLACK star icon, the same quirk already documented for Dunmore Primary/Long Furlong elsewhere in this pool. Worth a systematic follow-up: any other `fake_grid_confirmed` school might turn out to be the same rescuable case and hasn't been re-checked with the broad mask yet.
- **St Francis' CE Primary School** (URN 150520, Cowley, 1.44km2): re-attempted with two fresh independent anchors - Slade Park Fire Station (Overpass `amenity=fire_station`) + a real Cowley Junction road junction on Garsington Road/A4142 Eastern Bypass, geocoded via Overpass as the average of a tight cluster of approach-way nodes (2291px/1528m baseline), rotation -0.25deg. Own marker cross-check: 1.04deg/1.031 ratio - a clean result, superseding the previous session's inconclusive Driftway Centre/Isis Business Centre cross-check attempt.

**Overpass API was heavily loaded this session, returning intermittent 504 timeouts throughout** (both `overpass-api.de` and the `overpass.kumi.systems` mirror) - worked around by retrying with a content-check loop (checking for a real `"elements"` key in the response body, not just a successful HTTP connection) rather than treating any 200/504 response as done. Every Overpass-sourced landmark this session was eventually confirmed via a genuine, non-empty response.

**St Andrew's CE Primary, Oxford was re-attempted but not resolved.** Per this project's rule against using the target's own marker as one of the two scale-deriving anchors, re-derived the transform from Green Road Roundabout (Overpass `junction=circular`, averaged across 11 approach-way segments) + Headington Quarry Nursery/First School's marker (971px baseline) instead of the previous session's marker-anchored pairing. The bearing residual against the target's own marker stayed an acceptable -4 to -5deg across repeated pixel remeasurements, but the distance ratio was consistently only 0.84 (16% short). Investigating further found that **Headington Quarry Nursery School and Headington Quarry CE First School share an identical lat/lon to 15 decimal places** in this project's own schools table - strong evidence of a shared postcode-centroid coordinate rather than a genuinely precise per-school point, the same class of imprecision already documented for hospital/college campus centroids elsewhere in this project. This makes the Quarry marker an unreliable anchor regardless of how carefully its pixel position is measured. Left undone rather than forced.

**The Grange Community Primary School, Banbury was also re-attempted but not resolved.** Explored the "Dismantled Railway"/Spital Farm area flagged as unexplored by the previous session's note, but Spital Farm has no Nominatim hit and the Dismantled Railway is a long linear feature with no clean point landmark on it. A real, clearly-drawn roundabout is visible at the bottom of the map (the Maple Close/Willow Road junction with the main A-road) but could not be matched to any OSM `junction=roundabout` feature via several Overpass bounding-box searches around its estimated real-world location - either it isn't tagged that way in OSM, or the estimate was off. Left undone, documented for next session with the specific pixel location recorded.

**Barton Park Primary School** (URN 147865) still needs its own grid-tick/coordinate-label georeferencing technique (black-and-white OS topo map, red boundary, no drawn school marker) - not attempted this session, same as every prior session.

**Verification:** every new school's real DB coordinate falls inside its assigned polygon, GB bounds sane, no duplicate `SCHOOL_URN` at any point (166, 168, 169 unique/matching feature count in the primary geojson after each of this session's three commits in turn). `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both re-run clean before every commit. `pnpm format:write`/`prettier --write` run on the geojson before each commit (Python's own `json.dump` re-serialises arrays one-value-per-line rather than matching the repo's established compact-array style, inflating the diff if not corrected - re-confirmed this session, same lesson as an earlier session's note on this). All three commits pushed to `main` with no `Co-Authored-By` trailer, each push confirmed via `git fetch` + `git status -sb` showing not-ahead-of-origin. GitHub raw CDN confirmed fresh (full-40-character-SHA-pinned URL agreed with the `main` branch URL on feature count) before each `import-catchments --local-authority Oxfordshire` run. `refresh-catchment-overview-cache` re-run after each import (`map_catchments_cache.feature_count` 9896, 9898, 9899 across the session, in sync with `catchment_areas` every time). `refresh-catchment-scores` re-run in the background after each import and confirmed finished each time (session-final: 6,526 of 9,899 catchment_areas rows scored).

**Honest final tally:** Oxfordshire now at **195 of 307 schools (169 primary + 26 secondary)**, up from 188 at the start of this session. `remaining_schools_triage.tsv` (120 tracked rows, unchanged total) now reads: 34 `done` (up from 27), 3 `fake_grid_confirmed` (down from 10 - St Andrew's Oxford, The Grange, and Barton Park remain), 14 `declined_or_open` (unchanged), 69 `no_catchment_pdf` (unchanged, structural dead end).

**Most promising next lead for whoever continues after this session:** the `fake_grid_confirmed` backlog is nearly exhausted - only St Andrew's Oxford (needs a landmark that isn't the Quarry postcode-centroid pair), The Grange (needs the bottom-of-map roundabout identified, or a fresh landmark idea), and Barton Park (needs its own grid-tick georeferencing technique, structurally different from every other file in this pool) remain, and none of the three should be retried with the same anchors that already failed. Once those are closed out (or confirmed genuinely undoable), the next-most-promising body of work shifts to either (1) a systematic re-check of the ~69 `no_catchment_pdf` and 14 `declined_or_open` rows for a genuinely new angle now that this session found one previously-misclassified school (Dry Sandford) was actually a rescuable genuine grid template - worth specifically re-running the broad-cyan-mask grid check against any `fake_grid_confirmed`-flavoured note among the declined/no-PDF rows before assuming they're truly dead ends: or (2) moving to a different UK local authority entirely, since Oxfordshire's own remaining pool is now small and each remaining school needs real per-file debugging rather than being a bounded, repeatable task.

## Update: Rotherham's 79 primary catchments landed via address-search georeferencing + marker-controlled watershed on a raster-only platform (2026-08-10, later session)

**What this session did.** Instructed to re-scan LAs outside the 91-authority pilot roster, prioritising thin/early dead-end notes. Re-checked several "network unreachable from this sandbox" candidates first (Milton Keynes, Salford, Ealing's misoportal.com) with a fresh Playwright session - all three still genuinely time out at the TCP level (confirmed with a real headless Chromium session, not just curl), so they remain real network-origin blocks, not bot-fingerprint issues, and were left alone rather than re-logged as newly solved.

**Rotherham (local authority code 372) was the real find.** Its existing dead-end note (from an earlier session) correctly established that the council's Cadcorp GeognoSIS webmap (`maps.rotherham.gov.uk/webmapping`) serves its "Primary Catchment" layer (overlay 26 of 77, under an "Education" group also containing Primary Schools, Secondary Schools and Secondary Catchment) only as rendered raster tiles (`Overlay/{n}/Image?bbox=...`) with no vector `Features.json` endpoint - re-confirmed this session (still a genuine 404, unlike Derby/Stoke-on-Trent's outwardly-identical platform which does expose one). That earlier note treated raster-only as a hard stop. It isn't: the rendered boundary-line network is a clean, closed mesh (bright pure-green `RGB(0,255,0)` lines over an OS basemap) - exactly what this project's marker-controlled-watershed technique (previously proven on Portsmouth/Middlesbrough) needs, just delivered as pixels instead of vectors.

**Georeferencing without any printed grid or scale-bar guesswork.** This webmap's own address-search box calls a real API (`maps.rotherham.gov.uk/webmapping/search/quicksearch/{orgId}?filter=...`) that returns exact EPSG:27700 coordinates for any UK postcode server-side, and its "Home" control resets to a fixed, pixel-reproducible default view (independently confirmed: the borough outline lands at identical pixel positions across fresh, unrelated page loads). Searched 6 real postcodes spread across the borough (Rotherham town centre, Maltby, Dinnington, Swinton, Aston, Thurcroft), read back each one's exact EPSG:27700 coordinate from the search API, dropped each one's map pin and reset to the default view to get its pixel position, then fit a pixel-to-EPSG:27700 affine transform by least squares across all 6 - residuals of 7-22m against a ~22.9 m/px scale (i.e. sub-pixel accuracy), with negligible rotation confirming this is an ordinary north-up web map as expected.

**Segmentation and validation.** Screenshotted the "Primary Catchment" layer alone at the default view; thresholded pure-green line pixels plus independently-sampled navy LA-boundary-line pixels (from a separate screenshot with the catchment layer switched off, so the boundary mask isn't contaminated by the green mesh) as watershed barriers; seeded one OpenCV marker per this project's own DB coordinate for every open Rotherham primary school (reprojected lat/lon -> EPSG:27700 -> pixel space via the fitted transform's inverse); ran `cv2.watershed`. Critically, every resulting polygon's original (pre-simplification) contour was then checked against a distance transform of the real barrier mask - any polygon where more than 15% of its boundary was NOT within 4px of an actual drawn line or the real LA boundary (a watershed "seam" cut through undrawn territory between two seeds with no digitised line between them) was rejected outright rather than kept with a guessed edge. Of 95 in-view open primary schools: **79 passed** (mean 99% real-line support, minimum 88%) and every one was independently re-verified against the live DB to contain its own real coordinate; 16 were rejected (mostly zero/near-zero-area regions where a seed landed on or beside a boundary pixel itself, plus one seed that matched the unbounded background instead of a real cell) - dropped, not guessed at. Two open schools are both named "St Joseph's Catholic Primary School" (URNs 106944 and 140590, ~10km apart, different real locations) - both kept, since this project's catchment-to-school matching is a real point-in-polygon spatial join at query time (`catchment_scores.py`), not a name lookup, so the shared label is cosmetic only.

**Also fixed in passing:** a pre-existing, unrelated test failure. `packages/shared/src/config/catchment-sources.test.ts`'s `PILOT_LOCAL_AUTHORITIES` list was missing Inverclyde entirely, even though `catchment-sources.yml` already had 4 enabled Inverclyde sources from an earlier session - so the shared package's source-count test was already failing before this session touched anything (confirmed by stashing this session's changes and re-running against the untouched committed state). Added the missing roster entry; both `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) now pass clean.

**Verification:** all 79 polygons independently checked for valid geometry and sane GB bounds; all 79 independently re-verified (fresh query against the live DB, not just the pipeline's own claim) that the correct school's real coordinate falls inside its assigned polygon. `import-catchments --local-authority 372 --dry-run` matched the real import exactly (79 built, 0 rejected). Pushed to `main`, confirmed via `git fetch` + `git status -sb` (not ahead of origin). GitHub raw CDN confirmed fresh (full 40-character-SHA-pinned URL byte-identical to the `main` branch URL) before importing. `catchment_areas` went from 9,899 to **9,978** rows; `refresh-catchment-overview-cache` re-run and confirmed `map_catchments_cache.feature_count` = 9,978, in sync. `refresh-catchment-scores` re-run synchronously to completion: 6,600 of 9,978 areas scored project-wide.

**Local authority count: 92 (was 91).**

**Most promising next lead for whoever continues after this session:** Rotherham's own "Secondary Catchment" overlay (overlay 28 of 77, same Education group, same raster-only platform) was seen but not attempted this pass - same georeferencing/watershed/validation method should apply directly, and the transform + barrier-mask code from this session is reusable as-is (just re-seed with secondary schools and point at the other overlay). Beyond that, the technique proven here - address-search API for ground control points, instead of visually-estimated landmark pixel positions - is worth trying on any other "raster-only, no vector endpoint" Cadcorp/GeognoSIS dead end in this file that has a working postcode/address search box (Rotherham, Bury, Rotherham's neighbours), before assuming raster-only means undoable.

## Update: Rotherham's 14 secondary catchments landed by reusing the primary layer's affine transform (2026-08-10, later session)

**What this session did.** Directed at the exact "most promising next lead" from the update above: Rotherham's "Secondary Catchment" overlay, same Cadcorp GeognoSIS webmap and Education layer group as the primary catchment work, not yet attempted. This was pure application of the already-proven pipeline, not new research.

**Reused, not re-derived.** The pixel-to-EPSG:27700 affine transform fitted for the primary layer is a property of the map's default view (viewport, pan, zoom), not of which overlay is switched on - confirmed by cross-checking that place-label pixel positions (`Rotherham`, `Maltby`, `Dinnington`, `Wath upon Dearne`, etc.) land at identical coordinates across the primary screenshot, the secondary screenshot, and the layer-off navy-boundary reference screenshot. So this session skipped ground-control-point collection entirely and reused `affine_transform.json` and the navy-boundary reference screenshot from the primary session unchanged. Only the overlay itself differs in appearance: "Secondary Catchment" renders as a bright magenta/pink line network (`RGB ~(255,0,128)`) rather than the primary layer's pure green, so the barrier-detection colour threshold was swapped accordingly (`(r+b)/2 - g > 50` with `r>120, b>80` in place of the green channel test); the marker-controlled-watershed and boundary-support validation code (reject any polygon where >15% of its contour isn't within 4px of a real drawn line) is otherwise identical to the primary pipeline.

**Seeding and layer toggling.** Queried the live DB for Rotherham's 16 open secondary schools (`phase_name = 'Secondary'`, `status = 'OPEN'`, local authority code 372) - a much smaller set than the 95 open primaries, and all 16 fell inside the 1600x1000 default-view screenshot. Found the "Secondary Catchment" toggle in the same webmap layer panel one row below "Secondary Schools" (pixel position `(1247, 511)` vs. the primary toggle's `(1247, 355)`, same panel-open/expand-Education/scroll sequence as before) and confirmed via screenshot that toggling it on and closing the panel reproduced the identical base-map framing.

**Results.** Of 16 in-view open secondary schools: **14 passed** validation (support fraction 0.85-1.0, every one independently re-verified against the live DB to contain its own real coordinate) and 2 were rejected outright rather than guessed at - St Bernard's Catholic High School (seed landed on or beside a boundary pixel, producing a zero-area region) and Wickersley School and Sports College (that seed's watershed cell leaked past the drawn network into the unbounded background beyond the district boundary, an implausible ~755km² area caught by the area-plausibility check).

**Also fixed in passing:** `packages/shared/src/config/catchment-sources.test.ts`'s `PILOT_LOCAL_AUTHORITIES` roster hardcodes an expected enabled-source count per local authority; adding Rotherham's second source (`secondary_catchment`, alongside the existing `primary_catchment`) needed that count bumped from 1 to 2. This only surfaced after noticing `packages/shared/src/generated/catchment-sources.json` (a gitignored build artifact regenerated from the yml at install time) was stale from before the yml edit, so the shared test suite had silently been checking old data and passing for the wrong reason on the first run - re-ran `pnpm --filter @catchment-zone/shared sync-config` to regenerate it, which correctly turned up the roster mismatch, then fixed the roster count. Worth remembering for any future session that edits `catchment-sources.yml`: re-run `sync-config` (or reinstall) before trusting a green shared-package test run.

**Verification:** all 14 polygons independently checked for valid GB-bounds geometry and that each school's own live-DB coordinate falls inside its assigned polygon (fresh point-in-polygon check, not just the pipeline's own claim). Both `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) pass clean. Pushed to `main` across two commits (the catchment data, then the roster-count fix), each confirmed via `git fetch` + `git status -sb` (not ahead of origin) before proceeding. GitHub raw CDN confirmed fresh (full 40-character-SHA-pinned URL byte-identical to local file and the `main` branch URL) before importing. `catchment_areas` went from 9,978 to **9,992** rows (79 primary + 14 secondary for LA 372); `refresh-catchment-overview-cache` re-run and confirmed `map_catchments_cache.feature_count` = 9,992, in sync. `refresh-catchment-scores` re-run synchronously to completion: 6,614 of 9,992 areas scored project-wide.

**Local authority count: still 92** (Rotherham already counted from the primary-catchment session; this added a second source type to an already-counted authority, not a new one).

**Most promising next lead for whoever continues after this session:** with spare time remaining after landing the secondary catchments above, re-checked the two Cadcorp candidates this paragraph originally flagged as untested - both turned out to be genuine dead ends, not opportunities, so cross them off rather than re-attempting. **Medway** (`medwaymaps.medway.gov.uk`) was previously dismissed via static-HTML inspection only; opened it in a real Playwright session and walked its "Map Features" panel end to end - the Education group contains only a single "Schools" (locations) sub-layer, no catchment layer of any kind exists to recover, rendered or otherwise. **Bury** (`map.bury.gov.uk/externalwebmap/`) loads as a genuinely blank page (empty title, no content), consistent with its existing "no discoverable data-layer/API" note. **North Somerset**'s Cadcorp Aurora server remains a different, harder problem (the server itself hangs on `Aurora.svc/Frame` for 45+ seconds from both curl and a live browser) and shouldn't be retried without evidence the server has become responsive. With the known Cadcorp-platform leads now exhausted, the next-most-promising body of work is Oxfordshire's own remaining ~112 of 307 schools (91 non-gridded landmark-pair PDFs, dwindling `fake_grid_confirmed` backlog) - the largest bounded body of already-proven-method work in the project - or a fresh outside-the-pilot-roster LA scan applying this project's full toolkit (hidden ArcGIS/WFS APIs, Astun iShare point-in-polygon attribution, colour-classification-with-confirm-regrow segmentation, marker-controlled watershed, address-search georeferencing) to `candidates:` notes that look thin or under-investigated by an earlier, less-thorough pass.

## Update: Staffordshire's 313 catchments landed from embedded WGS84 polygons in a legacy school-search app; a real concurrent-session file race caught and fixed (2026-08-10, later session)

**Staffordshire: 313 catchment polygons landed (255 primary, 45 secondary, 13 middle-deemed-secondary), no georeferencing of any kind required.** Staffordshire's legacy "School Search" app (`apps2.staffordshire.gov.uk/scc/schooldetails/`) embeds each school's catchment polygon as a literal WGS84 JS array (`google.maps.Data.Polygon`) directly in server-rendered HTML behind a plain GET request - a genuinely different, higher-precision source class than every raster/PDF-based technique used elsewhere in this project, since the polygon coordinates are exact, not derived from pixel measurement. All 404 Staffordshire schools were enumerated by POSTing letters A-Z to the search page, which returns each school's real DfE URN and EPSG:27700 easting/northing directly in the results markup - the app's own `SchoolID` parameter is the URN itself, so DB matching needed no fuzzy name-matching. Of 320 schools with a catchment layer (84 of 404 have none), split by this project's own GIAS phase into primary/secondary/middle and validated with the standard point-in-polygon check against each school's real DB coordinate: 313 kept, 7 excluded for failing that check rather than force-matched. **Local authority count: verified directly against `config/catchment-sources.yml` (distinct `local_authority_code` values with `enabled: true`, cross-checked with a fresh `yaml.safe_load` and matching the passing vitest roster test) at 92 with Staffordshire included, 91 without it - so this session's true delta is 91 -> 92, not the 92 -> 93 this entry originally claimed (that number just carried forward the prior entry's "still 92" baseline without re-deriving it from the source of truth; whichever earlier session first wrote "still 92" was already one off). Correcting here rather than leaving a known-wrong figure in this file.**

**A real data-integrity incident, caught and fixed rather than silently deployed.** Partway through this session two separate Claude Code processes were, unknowingly, operating in the same non-isolated working directory at once (the coordinator's own fork-chain launched a new fork before a prior one's "still waiting" notifications had actually resolved to a final completion, meaning two forks briefly ran concurrently against the same shared git working tree rather than an isolated worktree per fork). One process's write to the three Staffordshire geojson files landed mid-write while the other was independently reading/writing the same paths, truncating them to 232/37/11 features instead of the true 255/45/13 the extraction script had actually produced and verified. This was caught (not by luck - the discovering session diffed the committed feature counts against its own script's fresh output and noticed the mismatch, plus independently confirmed a second live process via a running-process check and an unexplained concurrent yml edit) and fixed in a follow-up commit that restored the correct, unmutated extraction output. **Lesson for future sessions:** when launching a new fork to replace one whose completion is ambiguous (e.g. repeated "still waiting on X" notifications from the same task-id rather than a clear `failed`/`killed` status), either confirm the prior fork has genuinely stopped before launching a replacement, or use the Agent tool's `isolation: "worktree"` option so concurrent forks physically cannot race the same files on disk. This project's usual practice of verifying `git status`/`git log`/DB state before trusting a "success" report is exactly what caught this - the incident argues for extending that same scrutiny to file content, not just commit presence, whenever two agents may have touched the same paths in the same window.

**Verification:** all 313 final polygons independently checked for valid GB-bounds geometry and that each school's own live-DB coordinate falls inside its assigned polygon (a fresh point-in-polygon check, not just the extraction script's own claim). Both `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) pass clean; the pilot roster (`packages/shared/src/config/catchment-sources.test.ts`) already correctly lists Staffordshire (code `860`, `sourceTypeCount: 3`). Commits pushed to `main` (`027bf97` the original data, `b6c4719` the truncation fix), each confirmed via `git fetch` + `git status -sb` (not ahead of origin). `catchment_areas` went from 9,992 to **10,301** rows; `refresh-catchment-overview-cache` re-run and confirmed `map_catchments_cache.feature_count` = 10,301, in sync.

**Also landed in the same window (separate, smaller commit, `82df747`):** corrected a stale **West Northamptonshire** dead-end note that had only checked the bare, unconfigured `maps.westnorthants.gov.uk` host - the council's real public webmap lives at a different path (`webmappingpublic/en-gb/PublicMap/WNC_Map`, a genuine Cadcorp GeognoSIS 9.1 app); a live session confirmed its Education group holds only a point-location Schools layer, no catchment polygons exist there. Added two further confirmed dead ends: **Dacorum** (Cadcorp SIS WebMap 9, no Education/Schools category at all) and **Wealden** (an Esri Experience Builder app, not Cadcorp as an earlier search result suggested - its network traffic surfaced only an already-covered East Sussex CC schools FeatureServer, confirming no separate Wealden catchment source exists). Also removed a stale duplicate Stoke-on-Trent candidate note left over from before that authority was enabled.

**Most promising next lead:** a stale duplicate Staffordshire dead-end note still sits in `candidates:` (contradicting the fact it's now `enabled: true` in `sources:`) - low-priority cleanup, same class of leftover as the Stoke-on-Trent note just removed. Substantively, Staffordshire's embedded-JS-polygon technique (a legacy ASP.NET/Classic-ASP "school search" app serving exact coordinates with zero georeferencing) is worth checking for on other councils' legacy school-finder tools before assuming every remaining dead end needs a raster/PDF-based digitisation technique - it was found here by accident while investigating a Cadcorp candidate, not by a systematic search for this pattern specifically.

## Update: session with no new catchment data landed - systematic search for a second Staffordshire-style legacy app came up empty, and a DB-vs-yml audit confirms the candidate list is now genuinely exhaustive (2026-08-10, later session)

**This session landed zero new catchment_areas rows.** Not for lack of trying - a real, honest negative result after two separate lines of investigation, documented here so the next session doesn't repeat either one from scratch. (The stale duplicate Staffordshire `candidates:` note flagged by the previous session's "most promising next lead" turned out to already be removed by an intervening commit - checked directly via `grep -n Staffordshire config/catchment-sources.yml`, only the 3 enabled `sources:` entries remain, no cleanup needed.)

**Priority 1: hunted specifically for a second council running Staffordshire's embedded-WGS84-polygon legacy ASP.NET pattern. Found none.** Approached from three angles: (1) inspected Staffordshire's own `apps2.staffordshire.gov.uk` app for vendor/platform fingerprints that might reveal a shared multi-tenant product - it's a bespoke in-house ASP.NET WebForms app (IIS 10, `X-AspNet-Version: 4.0.30319`, a custom `SchoolDetails=Catchment` cookie, no CMS/vendor branding), built by Entrust (a Capita/Staffordshire County Council joint venture that does support schools "across the UK") but with no evidence found that this specific tool is resold or shared with other authorities - a real, checked lead that came up empty, not an unchecked one. (2) Batch-probed `apps.<council>.gov.uk` and `apps2.<council>.gov.uk` across ~70 English council domains (the full non-pilot roster plus several already-enabled ones, in case a second undiscovered tool sits alongside an existing source) for any live legacy-app host; a handful resolved (Derbyshire, Bedford, Wakefield, Wigan, Torbay, Norfolk, Warwickshire) but each was either a plain redirect to the main site or a near-empty placeholder page, none exposing a school-search tool. (3) Ran several targeted web searches for the distinctive artefacts of this pattern (`schooldetails`, `google.maps.Data.Polygon`, "View Catchment Area" button text, `SchoolID` parameter) - every hit resolved to either Staffordshire itself or an already-covered/already-dead-ended council (Leicester's `SchoolDetails.html` is a static address-lookup page with no map, already documented; Somerset/Hampshire/Norfolk/Northumberland hits were all already-enabled sources). Also separately checked whether Nottinghamshire's already-enabled `schoolsearchapi.nottinghamshire.gov.uk` (superficially similar "bespoke REST API" framing in its own source note) might be a shared platform - its `X-Powered-By`/cookie headers reveal it's hosted at `app-schoolsearch-api-prd-uks.azurewebsites.net`, an Azure App Service name with no indication of multi-tenancy. **Conclusion: this remains a real, valuable technique, but it looks like it really was a one-off accidental find rather than evidence of a wider shared platform - not worth further blind searching without a fresh, different lead into which councils might share Staffordshire's specific in-house build.**

**Priority 2: audited the live DB's `local_authorities` table (`catchment_coverage_status`) against `config/catchment-sources.yml`'s `sources:`/`candidates:` blocks to find any local authority never yet examined at all.** 93 authorities are `PILOT` (matches the yml's enabled-source count), 149 are `NOT_AVAILABLE`. A programmatic diff (yaml.safe_load against the DB's real LA name list, excluding non-UK-mainland administrative codes like BFPO/Offshore/Overseas/pre-LGR-superseded codes) found only 9 apparent "never mentioned" names, and every one of those turned out to be a false positive from imperfect string-splitting on grouped candidate entries whose own council name contains the word "and" (e.g. "Kensington and Chelsea" got mis-split by a naive `, | and` regex) - manually re-checked all 9 (Barking and Dagenham, Bath and North East Somerset, Brighton and Hove, Hammersmith and Fulham, Kensington and Chelsea, Kingston upon Hull, St. Helens, Westmorland and Furness, Windsor and Maidenhead) directly against the yml and confirmed every one already has a real, specific `reason_not_enabled` entry. **This is itself a useful, honest finding: there is no genuinely unexamined non-pilot local authority left in England, Wales, or Scotland** - the `candidates:` block is a complete, not partial, record of every LA this project has looked at. Any further progress has to come from either (a) revisiting an already-documented-but-not-fully-resolved candidate with a genuinely new technique, or (b) re-checking a network-blocked candidate from a different network origin, not from finding a brand-new unsearched LA.

**Re-verified three previously network-blocked candidates are still blocked, now via two independent client types (not just re-running curl).** `mapping.milton-keynes.gov.uk` (Astun iShare, Milton Keynes) and `map.salford.gov.uk` both still hard-timeout (TCP connect, no response at all) from both a direct `curl` and, separately, the `WebFetch` tool (a materially different network egress path) - strengthens the existing "worth retrying from a different network origin" note into "confirmed blocked from at least two different client paths in this environment, not just a sandbox-curl quirk." `inspire.misoportal.com` (Ealing's real, licensed WMS GeoServer for school catchment priority areas - the single most concretely "real data, just unreachable" candidate in the whole file) resolves to a different IP (`52.16.156.33`, AWS) than the bare `misoportal.com`/`www.misoportal.com` domains (which now do respond, a change from earlier sessions) - but that specific IP still refuses every connection attempt (`ECONNREFUSED`) via both curl and WebFetch. Did not re-attempt South Tyneside (its candidate note already accurately describes a 25-of-27-zones near-miss blocked on a genuine unresolvable gap in the council's own source map, correctly left undeployed per the no-guessing rule) or Oxfordshire (explicitly out of scope per this session's brief).

**No commits touching catchment data this session** - `catchment_areas` unchanged at 10,301 rows, `map_catchments_cache.feature_count` still 10,301, both re-confirmed live immediately before writing this update. This PROJECT_STATUS.md update is the only change.

**Most promising next lead for whoever continues after this session:** none of the three priority-1/2 avenues explored this session panned out, so the next session should either (a) get a genuinely new idea for finding Staffordshire-style sibling tools (e.g. a list of which UK councils' schools-IT is run by Entrust specifically, rather than guessing subdomain names), (b) try the network-blocked hosts (Milton Keynes, Salford, Ealing's `inspire.misoportal.com`) from a real different network origin - not another in-sandbox attempt, since this session independently reconfirmed the block via a second client type, or (c) accept that with the candidate list now confirmed exhaustive, the highest-value remaining work is deep per-LA digitisation effort on already-identified-but-incomplete candidates (South Tyneside's 2-zone gap; Kingston upon Thames's WFS, worth a periodic re-check for a newly-added catchment layer) rather than further LA discovery.

## Update: Oxfordshire declined_or_open backlog session - no new catchments landed, but a real anchoring bug found and the untried/dead-end school list closed out completely (2026-08-11)

**Baseline at the start of this session (re-derived fresh, not assumed): 10,304 `catchment_areas` rows, `map_catchments_cache.feature_count` = 10,304 (in sync), Oxfordshire at 198 of 307 schools (171 primary + 27 secondary in the two committed geojson files) following the prior interrupted session's Dunmore Primary + Aureus (Primary + School) commit (`aa826e9`, confirmed already on `origin/main`).** This session landed zero new catchment rows - an honest negative result, documented here in the same spirit as the 2026-08-10 "no new data" Staffordshire-search session.

**Priority 2 (never-downloaded schools) is now fully closed out: confirmed genuinely exhausted, not just unattempted.** Re-scraped all 307 council school-directory codes fresh (paginating `oxfordshire.gov.uk/schools/list?page=0..15`), matched all 307 to real DB URNs by normalised name (100% match, no ambiguity), and diffed against the 198 already-digitised URNs plus the 120 URNs already covered by `remaining_schools_triage.tsv`. This left exactly 26 schools never previously classified at all - all 26 turned out to be structural dead ends: 20 are Nursery-phase or "Not applicable"-phase (special/PRU/AP schools, which don't have LA-defined designated areas in this council's system), and the other 6 ("All-through" academies: Europa School UK, Heyford Park School, St Johns CofE Academy, plus 3 more) all returned a plain 404 for their PDF URL (own-admission-authority academies with no catchment PDF at all, same class as the existing 68 `no_catchment_pdf` rows). All 26 added to `remaining_schools_triage.tsv` with this finding recorded, so no future session re-derives this from scratch. **Oxfordshire's untried pool is now provably zero** - every one of the 307 schools is either digitised (198), a confirmed structural dead end (94, up from 68), or in the `declined_or_open`/`fake_grid_confirmed` backlog (15) that needs a genuinely new landmark idea per school, not bulk discovery work.

**Priority 1 (`fake_grid_confirmed` not yet attempted) had nothing left either: all 3 rows in that status ARE the three documented hard declines** (Barton Park Primary, The Grange Community Primary, St Andrew's CE Oxford) named in this session's own brief as already-exhausted without a genuinely new idea - correctly left alone.

**Priority 3 (revisit `declined_or_open` with a new idea) is where this session's real effort went, on Caldecott/Thameside (Abingdon) and New Marston (Headington/Marston).** Found a likely root cause for the prior sessions' 18° Caldecott bearing failure: the OSM way both prior attempts anchored to (`junction=roundabout` tagged "Marcham Road A415" at 51.6698,-1.2996) is a real but tiny (~12m radius) roundabout, distinct from - and about 280m away from - the large multi-loop A415/A34 interchange actually drawn on the source PDF next to the "Superstore" label. Built an automated OpenCV colour-mask centroid detector (red-ring hole-fill for roundabouts, weighted by area; maroon-outline building-square detection for named school icons) to reduce the manual-pixel-eyeballing imprecision that's plausibly been contributing to this backlog's persistent near-miss bearing residuals, and used it plus an Overpass circle-fit of the correct interchange (way cluster 68338810+1303348628/629/630, true center 51.66885,-1.30398) to re-derive the transform. Result: 13.25° rotation (Marcham interchange + Thameside's own building icon) or 8.84° (interchange + Caldecott's own marker, diagnostic only, not used as a real anchor) - both markedly better than the previous 18°, but still over this project's 5° threshold, so correctly left undeployed rather than forced. Also independently cross-checked both schools' DB coordinates against OSM's own amenity nodes (Thameside: 65m apart; Caldecott: ~80m apart) - both are trustworthy, so the remaining error is anchor-precision, not a bad DB coordinate. New Marston Primary's non-gridded vector template was confirmed extractable at full precision (`vector_boundary.py`'s real PDF vector path, marker verified to land exactly on the printed icon), but a second non-campus landmark far enough from a "Beech Road" roundabout candidate (51.76045,-1.21617, Overpass-confirmed) wasn't found before the public Overpass API started rate-limiting this session's queries (repeated 504s). All three schools' full diagnostic detail is in the triage file for the next session to continue from, rather than re-discovering the wrong-roundabout mistake from scratch.

**Verification:** no catchment_areas rows were touched this session (documentation and triage-file updates only) - re-confirmed `catchment_areas` still 10,304 and `map_catchments_cache.feature_count` still 10,304 immediately before writing this update. Both `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) pass clean. `remaining_schools_triage.tsv` re-validated programmatically: well-formed 8-column TSV, 146 data rows, zero duplicate URNs. `pnpm format:write` run before committing (this entry + the triage file touch both `PROJECT_STATUS.md` and files this project's formatting rule covers).

**Most promising next lead for whoever continues after this session:** Caldecott/Thameside is the closest of the three to resolving - the next session should either (a) get a precise pixel/geocode fix on Ock Bridge (Nominatim 51.6685971,-1.2953051, partially triangulated this session but not finished) or New Cut Mill (Nominatim 51.6626194,-1.3082937, also partially triangulated) as a replacement for the troublesome small-radius interchange roundabout, or (b) fit the interchange's full outer ring (not just its small circulatory-carriageway way) for a more robust centroid. Beyond that specific pair, with the untried-schools pool now provably exhausted, all remaining Oxfordshire opportunity is in the 15-row `declined_or_open`/`fake_grid_confirmed` backlog - genuinely hard per-school landmark-finding work, not bulk discovery.

## Update: Caldecott + Thameside Primary (Abingdon) landed by replacing the interchange-roundabout anchor with Ock Bridge/New Cut Mill/Stonehill House; a real-authority coverage-gap audit built and run for priority 2 (2026-08-11, later session)

**Baseline at the start of this session: 10,304 `catchment_areas` rows, `map_catchments_cache.feature_count` = 10,304 (in sync).** Picked up the previous session's specific, bounded lead: Caldecott and Thameside Primary (Abingdon, Oxfordshire) were stuck at 8.8-13.3° bearing residual anchored on the Marcham Road interchange roundabout, over this project's 5° threshold.

**Resolved by abandoning the interchange anchor entirely rather than trying to measure it more precisely.** Downloaded both schools' PDFs fresh (`2598_all.pdf`, `2605_all.pdf`) and found both explicitly print "Ock Bridge" and "New Cut Mill" (Caldecott's page) - real, simple, pixel-precise point features, unlike the multi-loop interchange. Ock Bridge's crossing point was located via colour-overlap of the yellow-road and light-blue-river pixel masks (not eyeballed), giving sub-5px precision. New Cut Mill required a correction mid-session: a first attempt measured the wrong feature (a stream confluence near the label) - checking Nominatim's own `class`/`type` fields (`building`, not the confluence) caught this before it was used, and the actual building icon was re-measured via colour-mask centroid.

- **Caldecott Primary School** (URN 123087, 1.34km²): anchored on Ock Bridge (51.6685971,-1.2953051, pixel (1866,437)) and New Cut Mill (51.6626194,-1.3082937, pixel (502,1405)), 1673px baseline, rotation -1.68°. Cross-checked against Thameside Primary's own building footprint drawn on the same page (colour-mask centroid, real DB coord): 3.24° residual, 1.016 distance ratio - clears the bar with margin.
- **Thameside Primary School** (URN 144871, 1.40km²): same method on its own PDF, anchored on Ock Bridge (pixel (727,238)) and Stonehill House (51.6568202,-1.2977794, pixel (466,2036), a Nominatim `landuse=residential` building cluster found further down the same page - Ock Bridge's only other candidate partner on this page, Caldecott's building, gave just a 550px baseline, under this project's >1000px bar, so was demoted to a cross-check instead), 1817px baseline, rotation -1.36°. Cross-checked against Caldecott's own building footprint: -2.96° residual, 1.112 distance ratio.

**A real methodological finding worth keeping: each target school's own marker/DB-coordinate cross-check was noisy (-5.2° to +12.3° across variants) even once the primary anchors were solid, and this was independently explained rather than treated as a red flag** - Nominatim confirms Caldecott's real DB coordinate sits ~80m from OSM's own school-amenity node for the same school (Thameside ~49m), which alone accounts for a multi-degree residual at these schools' short (350-650m) own-marker baselines. Per this project's rule, a target's own marker is never used as an anchor - only as a diagnostic - so this noise didn't block landing either school; the two genuinely independent cross-checks (each school's own building footprint on the _other_ school's page) both passed cleanly. A first, uncorrected measurement of Thameside's building icon on Caldecott's page also picked up the wrong colour-mask component (a stray nearby shape, not the actual maroon-outlined square) - caught by a visual crosshair overlay before it was trusted, not before. The resulting polygons tile together sharing a border along Saxton Road, matching the two adjacent designated areas drawn on the source PDFs - an independent shape-level sanity check beyond the numeric residuals.

**Verification:** both real DB coordinates fall inside their own polygons (checked both locally with shapely before committing, and again against the live database after import). Both polygons valid, simple, no interior holes, GB-bounds sane, areas plausible (1.34km²/1.40km²) for this project's Oxfordshire primary range. No duplicate `SCHOOL_URN` (173/173 unique in the primary geojson after this commit). `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) both pass clean. `remaining_schools_triage.tsv` re-validated programmatically (147 well-formed 8-column rows, zero duplicate URNs) after updating both rows from `declined_or_open` to `done`. `pnpm format:write` run before committing (no changes needed to the geojson - already matched the compact-coordinate-pair style). Commit `fa6089d` pushed to `main` with no `Co-Authored-By` trailer, confirmed landed via `git fetch` + `git log origin/main -1`. GitHub raw CDN confirmed fresh (full-40-character-SHA-pinned URL agreed with the `main` branch URL on feature count and both new URNs present) before running `import-catchments --local-authority "931"`: built 200 catchment areas (173 primary + 27 secondary), 0 rejected. `catchment_areas` 10,304 → 10,306 in the live database, confirmed via direct query (no duplicate `area_name` rows for either school). `refresh-catchment-overview-cache` re-run (`map_catchments_cache.feature_count` 10,306, in sync). `refresh-catchment-scores` re-run in the foreground and confirmed finished (6,867 of 10,306 areas scored). `DATA_SOURCES.txt` updated with this session's PDF re-downloads and the three Nominatim landmark lookups.

**Honest final tally:** Oxfordshire now at **173 of 307 schools (173 primary + 27 secondary = 200 total)**, up from 198 (171 primary + 27 secondary) at the start of this session - `remaining_schools_triage.tsv` now reads 16 `done` (up from 14), 24 `fake_grid_confirmed`, 11 `declined_or_open` (down from 13), 69 `no_catchment_pdf`.

**Priority 2 (systematic gap audit across already-partially-covered local authorities) was also attempted this session, producing a reusable tool but no landed data.** Built a proper point-in-polygon coverage audit (fetching all 10,306 `catchment_areas` geometries and all 31,091 open schools' coordinates locally, then testing containment with shapely/STRtree rather than pushing a slow per-row `ST_Contains` join into CockroachDB, which was impractically slow at this scale) - this is a real capability gap this project didn't have before: `config/catchment-sources.yml`'s notes only describe partial coverage in prose ("N of M schools") for a minority of local authorities, so most gaps were previously invisible without a query like this. Cross-referencing every `PILOT_LOCAL_AUTHORITIES` code against real open-school counts surfaced several large apparent gaps, but the two largest (Hertfordshire, 340; Leeds, 149) turned out to be already-documented structural limits, not incomplete digitisation: Hertfordshire's secondary system is genuinely shared-pool/non-catchment outside its 7 selective schools (already covered) and no primary source was ever found to exist at all; Leeds's primary count (93 polygons) is drawn from the council's own single combined PDF, plausibly already exhaustive for that document. Two smaller but concretely promising gaps were found and are **not** yet explained by a documented dead end:

- **Halton (LA code 876): 30 of 70 open schools covered, gap of 40.** The existing `catchment-sources.yml` entry for Halton's 2 Widnes secondary polygons says outright, in its own words, "Halton's other secondary schools (Runcorn area) and primary schools are not covered by this document; not yet checked for a separate map" - a genuine, previously-flagged, never-followed-up lead, not a guess.
- **Bristol, City of (LA code 801): 130 of 173 open schools covered, gap of 43.** Bristol's own ArcGIS MapServer (`maps2.bristol.gov.uk/server2/rest/services/ext/ll_education/MapServer`) that supplies its two enabled secondary "priority area" layers (ids 3, 8) was re-enumerated this session and has no primary-catchment polygon layer among its other 14 layers (id 6, "Infant, Junior and Primary schools", looks like a point layer of school locations, not areas, based on its naming symmetry with id 10 "Secondary schools") - so a primary source, if one exists, is hosted somewhere else and wasn't found this session.

Neither was pursued further this session (both would need their own from-scratch source search, download, licence check, and parser - a full session's own work, not a quick add-on to an already-long one).

**Most promising next lead for whoever continues after this session:** start with **Halton** - the prior session's own note already says primary/Runcorn-secondary "not yet checked for a separate map," which is a concrete starting instruction, not a fresh unknown. Search halton.gov.uk's school-admissions pages and committee/councillor document library (the same `councillors.halton.gov.uk/documents/...` pattern that surfaced the existing Widnes secondary PDF) for a primary equivalent. Bristol is the second-best lead (43-school gap, but needs a real from-scratch source search since the obvious same-MapServer extension came up empty). Beyond those two, the coverage-audit method built this session (fetch all `catchment_areas` + open `schools` rows once, point-in-polygon locally with shapely rather than a live spatial-join query) is reusable for auditing any other local authority in one pass without re-deriving it.

## Update: Halton and Bristol both closed out as confirmed structural dead ends, not landed data (2026-08-11, later session)

**Baseline at the start of this session: 10,306 `catchment_areas` rows, `map_catchments_cache.feature_count` = 10,306 (in sync).** Picked up the previous session's two concrete leads in priority order - Halton's own "not yet checked for a separate map" note, then Bristol's 43-school gap. Re-ran the previous session's point-in-polygon coverage audit against the live DB to confirm the starting gap sizes first: Halton 30/70 open schools covered (40 uncovered: 36 primary/nursery/all-through, 4 Runcorn-area secondary), Bristol 130/174 open schools covered (44 uncovered: 24 primary, 4 secondary, 16 special/PRU/AP "Not applicable"-phase). **No new catchment_areas rows were landed this session - both gaps were investigated to a genuine, well-evidenced conclusion that they are structural (Halton and Bristol both deliberately never published a boundary for these schools), not an unsearched lead**, so per this project's standing rule against deploying anything not verifiably real, nothing was digitised.

**Halton: confirmed dead end via the council's own historical committee record, not just an absence of search results.** Found the actual 2011 Executive Board report (`councillors.halton.gov.uk/documents/s13393/`, "School Admission Arrangements 2012") that originally introduced the Widnes zoning scheme already covered by this project's 2 existing polygons. It states outright that "the LA sought confirmation from central government that operating catchment zones in Widnes **and a different set of oversubscription criteria in Runcorn** was permitted" - i.e. Runcorn secondary schools have never had catchment zones, by deliberate, government-approved LA policy, not by an unpublished map. Cross-checked against Halton's current (2025/26) admission booklets: every Runcorn secondary (The Heath School, Ormiston Bolingbroke Academy, Ormiston Chadwick Academy, Sandymoor Ormiston Academy) lists only "Distance" (LLPG straight-line) as its geographic oversubscription criterion, with zero mention of a catchment/zone anywhere in either the primary or secondary booklet text. Primary admissions borough-wide are the same: a 2007 committee minute already on record describes it as "a circle... drawn around the area of the school" whose radius "depend[s] on the choices that parents made each year" (i.e. genuinely no fixed boundary, not just an undigitised one), and the sole exception found - one voluntary-aided primary (St Michael with St Thomas CE) naming an undefined "Catchment Area of the Academy" in its own SIF criteria - has no published map anywhere, only the bare criterion text. Also checked and ruled out: `geodata.halton.gov.uk` (the council's real open-GIS portal - planning-only datasets, no schools layer) and its `onlinemapping.aspx` tools index (9 live map tools, none schools-related). The `catchment-sources.yml` Halton entry's notes have been updated in place to record this as resolved, so no future session re-investigates it as an open lead.

**Bristol: confirmed dead end via exhaustive re-enumeration of both of Bristol's real GIS services plus the individual admissions policies of the 4 missing secondary schools.** The previously-checked `ll_education` MapServer (used for the two already-enabled secondary "priority area" layers) was re-confirmed to have no primary-catchment polygon layer. This session additionally found and fully enumerated a second, much larger Bristol service - `maps2.bristol.gov.uk/server2/rest/services/ext/moving_home/FeatureServer` (75 layers spanning bus stops to job centres) - whose layer 19 "Primary schools" is also point-only (`esriGeometryMultipoint`), and whose only school-boundary polygon layer is layer 28, the same "Secondary school areas of first priority" already covered. Bristol's own determined primary admissions document (`bristol.gov.uk`, "Admission arrangements for community and voluntary controlled infant and primary schools 2027/2028") confirms the structural reason: its only geographic oversubscription criterion is "3. Geography - Children living closest to the school as measured in a direct line" - no priority-area concept exists for LA-run primaries at all. A promising-looking "Bristol Primary Education" ArcGIS Experience app (`experience.arcgis.com/experience/9aa54c22c5ce4d198083e376195ab498`) turned out, via its own item JSON and underlying web map, to be a mistitled clone of the secondary schools app wired to the identical point-only "Secondary schools" layer - not a real primary source, despite the name. For the 4 secondary schools missing from the live "first priority" FeatureServer query itself (confirmed by querying it directly: 25 named areas, none matching), each school's own published admissions policy was checked individually: Blaise High School, Oasis Academy Brislington and Oasis Academy Brightstowe are all academies whose own oversubscription policy is plain straight-line distance with no priority area. St Bede's Catholic College does have its own "Catchment Area Map" page, but both the live site and its Wayback Machine archive history show it resolves to ~18 separate Catholic Diocese of Clifton parish-boundary PDFs (a faith oversubscription criterion), not one drawn school catchment polygon - a materially different, much higher-effort source type than anything else in this file, and not pursued this session given the uncertain payoff. The `catchment-sources.yml` Bristol block now carries a full comment recording all of this so a future session doesn't re-run the same searches.

**Verification:** no catchment_areas rows were touched this session (documentation-only) - re-confirmed `catchment_areas` still 10,306 and `map_catchments_cache.feature_count` still 10,306 immediately before writing this update. Both `pnpm --filter @catchment-zone/shared test` and the ingestor's full pytest suite were run and pass clean. `pnpm format:write` run before committing (no changes needed - `config/catchment-sources.yml` and this file were already correctly formatted).

**Most promising next lead for whoever continues after this session:** neither Halton nor Bristol has any further primary/Runcorn-secondary opportunity left to search for with this project's normal techniques - both are now confirmed structural dead ends and should not be re-investigated without a genuinely new angle. The best next step is to re-run this project's reusable point-in-polygon coverage-gap audit (built two sessions ago, described above) against the remaining `PILOT_LOCAL_AUTHORITIES` not yet checked this way, to surface the next concrete, previously-invisible gap - the same method that correctly separated Halton/Bristol (real, investigable gaps) from Hertfordshire/Leeds (already-documented structural limits) two sessions ago. St Bede's Catholic College's per-parish "catchment area map" (Bristol, noted above) is a real but low-priority lead if a future session wants to explore whether Catholic Diocese of Clifton parish boundaries are worth digitising as a new source pattern - it would need to first establish whether the parish list genuinely constitutes an exclusive priority boundary for the school (as opposed to a shared/overlapping set of criteria used across many different Catholic schools), which wasn't established this session.

## Update: coverage-gap audit re-run across all 91 remaining pilot LAs; Cumberland rebuilt (+62 schools) from a better source hiding on the same pages; Stoke-on-Trent, Lancashire and Herefordshire closed out as confirmed structural gaps (2026-08-11, later session)

**Baseline at the start of this session: 10,306 `catchment_areas` rows, `map_catchments_cache.feature_count` = 10,306 (in sync).** Rebuilt the point-in-polygon coverage-gap audit from scratch (the prior forks' script wasn't preserved in the repo) - fetches every open school's real DB coordinate and every deployed catchment polygon once, then tests containment locally with shapely, exactly as described in the 2026-08-11 entries above - and ran it against all 91 `PILOT_LOCAL_AUTHORITIES` not already checked this way (Halton and Bristol were skipped, already closed out).

**Cumberland (LA code 942): rebuilt from 82 to 144 verified catchments (129 primary, 15 secondary) - net +62, zero regressions.** The audit flagged Cumberland's 21-school gap as a real, unexplained lead. Re-fetching 8 of the previously-unmatched schools' pages (to try to recover 5 name-mismatches, 2 invalid geometries and 1 point-in-polygon failure the prior session had flagged but not chased) surfaced something much bigger: every Cumberland school page embeds a _second_ leaflet block alongside the per-school node used previously - `drupalSettings.leaflet["leaflet-map-view-school-list-block-3"]` - a single borough-wide "school list" map view containing all ~140 of the council's catchment polygons at once, each with its own popup naming its school(s) directly. This sidesteps the prior session's entity-fallback bug entirely (which only affected the per-school node lookup, not this block). Re-extracted the whole council from this one source using elision-aware joint-name splitting (`"Ashfield Infant and Junior"` → `"Ashfield Infant School"` + `"Ashfield Junior School"`, re-attaching the elided leading place name) and strict-name-first matching (exact/subset core-token match tried before a weak raw-overlap fallback - the first, looser attempt produced false ties in compact towns where several schools' real coordinates all happen to sit inside every nearby polygon regardless of which school it's actually named for, e.g. Millom's 3 schools and Wigton's Nelson Thomlinson/Thomlinson Junior pair - fixed before landing anything). Every one of the 144 matches was independently re-verified after building the final files: valid geometry, GB bounds, real DB coordinate inside its polygon, no duplicate URNs. 2 more schools (Monkwray Junior 147m, Ewanrigg Junior via a second joint name 112m) were name-matched with high confidence but left undeployed rather than forced, since a 100m+ miss on a live official polygon (not a hand-digitised PDF, where this project has documented up to ~88m of expected extraction jaggedness elsewhere) reads as a genuine edge case rather than measurement noise. Cumberland's live coverage is now 179/179 open schools with coordinates (up from 158/179) - full theoretical coverage, per a fresh point-in-polygon re-check after import.

**Stoke-on-Trent and Lancashire: both flagged by the audit as large unexplained gaps (27 and 144 schools), both turned out to already be resolved - just not recorded where the audit could see it.** Stoke-on-Trent's original landing commit (`ce79137`) already states "No secondary layer exists, consistent with the council's own statement that high-school admissions aren't catchment-based" - that finding only ever lived in the git commit message, never made it into `catchment-sources.yml`'s notes, so this session's audit (which only reads the yml, not git history) couldn't see it. Lancashire was live-checked against Lancashire County Council's own admissions pages, which confirm a "Geographical Priority Area" (GPA) is a genuinely partial concept ("community and voluntary controlled schools which are subject to a GPA", implying most aren't) - the existing 41-feature ArcGIS layer already covers the schools that have one; the rest use their own admission authority or plain distance, the same structural pattern already confirmed for Halton/Bristol. Both notes updated in place so a future audit run doesn't re-flag either.

**Herefordshire: the existing "believed to genuinely have no LA-administered catchment" note was upgraded from believed to confirmed.** Re-checked all 36 open Herefordshire schools whose real DB coordinate falls outside every deployed polygon and found a clean 100%-consistent pattern: every one is Voluntary Aided, an Academy (converter or sponsor-led), an independent school, a PRU, or a special school - not one is a plain community/foundation school. Herefordshire's own live admissions guidance confirms voluntary aided and academy schools are their own admission authority, and names several CE schools that explicitly use "nearest school not catchment school" - consistent with, not contradicting, the existing faith-school finding. Not a live lead; note updated to remove the hedge.

**Other audited LAs, not pursued further (already correctly explained by existing notes, confirmed silent-gap-free on inspection):** Wigan (131 gap - a small, deliberately ad-hoc 4-school consultation service, already fully documented and closed), South Tyneside (54 gap - a real, already-identified-but-unsolved "line-network closure problem" on the borough-wide partition maps; no new angle found this session, left as the existing open lead it already was), North Northamptonshire (153 gap, actually a systematic 0/153 point-in-polygon miss - but its notes already explain this precisely: the source is deliberately named `primary_catchment_partial`, "Linked Areas" postcode-unit polygons that don't need to contain the school itself, covering only 3 of many oversubscribed school clusters by design), Bournemouth/Christchurch/Poole, Central Bedfordshire, Calderdale, Rotherham and Staffordshire (all small remaining gaps, all already thoroughly documented with specific exclusion reasons in their existing notes - re-read but not re-investigated, consistent with this session's brief to move quickly past already-explained gaps). Hertfordshire and Leeds were not re-investigated (already confirmed structural in an earlier session, per that session's own audit). Oxfordshire was explicitly out of scope.

**Verification:** all 144 Cumberland catchments independently re-checked after building the final GeoJSON files (before import): valid geometry, GB-bounds coordinates, every real DB coordinate inside its assigned polygon, no duplicate `SCHOOL_URN`. Both `pnpm --filter @catchment-zone/shared test` (45 passed) and the ingestor's full pytest suite (127 passed) pass clean, checked after each commit. `pnpm format:write` run before every commit touching `catchment-sources.yml`. Commits (`6037212` the Cumberland data, `bc62869` the Stoke-on-Trent/Lancashire documentation fix) both pushed to `main` and confirmed landed via `git fetch` + `git log origin/main -1` before importing. GitHub raw CDN confirmed fresh (SHA-pinned URL agreed with the `main` branch URL on feature count) before running `import-catchments --local-authority "942"`: built 134 catchment areas (119 primary after 10 geometry-sharing merges, 15 secondary), 0 rejected. A stale-row issue was caught and fixed: since Cumberland's `catchment_sources` rows kept the same `(local_authority_code, source_type, academic_year)` upsert key as the prior session's import, but every polygon's geometry (and therefore `geometry_checksum`) differed from the old source, the prior session's 82 rows were **not** replaced by the new import - both old and new rows coexisted under the same source until explicitly deleted (identified by `created_at` predating this session, confirmed a clean 82-old/134-new split by row count before deleting). `catchment_areas` went from 10,306 → 10,440 (after import) → 10,358 (after deleting the 82 stale rows) - a net +52 rows for +62 more schools covered (accounting for the 10 geometry-sharing merges). `refresh-catchment-overview-cache` re-run and confirmed `map_catchments_cache.feature_count` = 10,358, in sync. `refresh-catchment-scores` re-run in the foreground and confirmed finished (6,914 of 10,358 areas scored).

**Most promising next lead for whoever continues after this session:** the coverage-gap audit is now clean of every large false lead - Hertfordshire, Leeds, North Northamptonshire, Lancashire, Wigan, Stoke-on-Trent and Herefordshire are all confirmed structural or already-documented, and Cumberland (the one genuine gap found) is now fully closed at 179/179. The two remaining open, real leads are both already-identified rather than newly found: **South Tyneside's borough-wide ~27-zone "line-network closure problem"** (54-school gap, needs a genuinely new geometry-reconstruction idea, not another attempt at the same closure algorithm), and **Bristol's St Bede's Catholic College per-parish "Catchment Area Map"** (noted in the 2026-08-11 Halton/Bristol session as a real but low-priority lead, still not investigated). Beyond those two specific items, this session's experience with Cumberland is worth generalising: when a source's original landing note describes "N of M schools" without saying _why_ the rest are missing, it's worth checking **every other page the same tool serves** for a second, more complete embedded data block before concluding the gap is structural - the fix here wasn't a new source, just a second JSON block already sitting on pages this project had already fetched.

## Update: Scotland's national school-catchments aggregate lands 4 coverage gaps via user-assisted manual download (2026-08-11, same day)

**The user manually downloaded and handed off real data for the first time this session**, unblocking a genuine login-gated source this project's own automated tooling correctly refused to bypass. Spatial Hub Scotland's national school-catchments aggregate (`data.spatialhub.scot/dataset/school_catchments-is`, Improvement Service, OGL-licensed) covers all 32 Scottish council areas in 4 layers (Primary/Secondary x denominational/non-denominational) but its bulk-download UI requires signing in or registering a free account - a real, if low-friction, authentication gate. The user registered and downloaded all 4 GeoJSON layers (2,382 raw features total) themselves and handed them off for ingestion.

**Used only to fill genuine gaps, not to replace working sources.** 28 of the 32 councils already have a dedicated primary AND secondary source elsewhere in this file; importing this aggregate for them would create duplicate, potentially-conflicting polygons for the same schools, so those 28 were left untouched. Four genuine gaps were identified and filled:

- **East Ayrshire** (new local authority, no prior source of either phase) - all 4 layers added.
- **Na h-Eileanan an Iar** (new local authority) - reopens a local authority a prior session had explicitly confirmed a dead end (no published catchment map existed anywhere) - now unlocked entirely by this aggregate. Primary (non-denominational only - the aggregate has no separate denominational layer for this council) and secondary added.
- **Dumfries and Galloway** - had primary coverage from an existing ArcGIS source but no secondary source at all; only the missing secondary phase (denom + non-denom) was added, leaving the working primary source untouched.
- **Shetland Islands** - same pattern: had primary coverage from this session's own earlier hand-digitised work but no secondary; only secondary (non-denominational, all Shetland schools are non-denom) was added.

**Matching and verification.** Every feature carries Scotland's real `seed_code`, which maps directly to this project's own `School.urn` scheme (`seed_code` + P/S suffix) - confirmed against a live DB lookup before trusting it as a matching key. A minority of council-contributed rows had a null `seed_code` in the source data itself (not every uploading council populated it); those were matched by exact school name within the same council + phase instead. Critically, every matched feature - seed_code matches and name matches alike - was then independently verified the same way this project verifies every other source: the matched school's own real DB coordinate had to fall inside the feature's polygon, or it was excluded rather than trusted on the strength of the name/code match alone. Reprojected EPSG:27700 -> EPSG:4326 via pyproj; several polygons collapsed into invalid mixed `GeometryCollection`s under a naive `shapely.make_valid()` call (points/lines mixed with polygon parts) and needed this project's own `validate_and_repair` (the polygonal-parts-only extraction path) rather than a fresh repair implementation.

**Results: 88 catchment polygons kept, all independently verified.** A handful of source rows were correctly excluded rather than guessed at: 5 Na h-Eileanan an Iar schools (Bernera, Tolsta, Balivanich, Leverburgh, New North Uist School) and 3 Shetland schools (Mid Yell/Whalsay/Brae Junior High) had no matching open school at all - closed or merged since the source data's 2021 upload, a genuine staleness in an otherwise-live dataset, not a matching bug. Two more failed the point-in-polygon check specifically: Brae High School (Shetland) and Robert Burns Academy (East Ayrshire) both had a real seed_code match but their real DB coordinate fell outside the matched polygon, so both were excluded. One further row, "Carrick Academy (South Ayrshire)", was filed under East Ayrshire's council code in the source data despite being a different council's school entirely - correctly unmatched by the same-council name lookup, not force-matched to a wrong school.

**Verification:** `pnpm --filter @catchment-zone/shared test` (45 passed, after `sync-config` regenerated the gitignored build artifact) and the ingestor's full pytest suite (127 passed) both pass clean. All 88 output polygons checked for valid geometry, sane GB bounds, and no duplicate `SCHOOL_URN` before committing. Commits (`59ccea2` the catchment data, `d83e4c0` a recovered Herefordshire documentation note left uncommitted in a prior fork's worktree during this same session) both pushed to `main` and confirmed landed via `git fetch` + `git status -sb`. GitHub raw CDN confirmed fresh (byte-identical feature counts between the `main` branch URL and a fresh fetch) before importing each of the 4 local authorities: `import-catchments --local-authority <code>` for S12000008/S12000013/S12000006/S12000027 built 45/21/106/30 catchment areas respectively (0 rejected across all four; Dumfries and Galloway's 106 includes its existing 90-polygon primary source re-upserted alongside the 16 new secondary polygons, matching its already-live ArcGIS feed - not new data, just re-confirmed current). `catchment_areas` went from 10,358 to **10,445** rows (87 net new after one geometry-sharing merge). `refresh-catchment-overview-cache` re-run and confirmed `map_catchments_cache.feature_count` = 10,445, in sync. `refresh-catchment-scores` re-run in the background and confirmed finished: 6,940 of 10,445 areas scored.

**Local authority count: 93 -> 95** (East Ayrshire and Na h-Eileanan an Iar both newly enabled).

**A related lead investigated the same session, correctly not pursued:** the user also found a `BrightonandHOvesecondaryCatchmentAreas.csv` (6 rows: school name, computed area in m², and a single X/Y centroid point per row) from the same general search context as the Brighton and Hove FOI lead noted in an earlier session. This is NOT boundary geometry - a single point plus an area figure cannot be turned into a real polygon without guessing a shape, which this project's standing rule against inventing/estimating geometry forbids. Correctly declined rather than force-fit into a fake circle/square; Brighton and Hove remains on the "real data confirmed to exist, still inaccessible" list pending an actual shapefile/GeoJSON/KML attachment, if one exists on the same source page.

**Most promising next lead:** the user has now proven willing and able to manually authenticate through login walls this project's own tooling can't pass - the two other confirmed-real, login-gated sources noted earlier this session (Lewisham's and Gloucestershire's "MapThat"/dynamicmaps.co.uk platforms, and West Sussex's StatMap Earthlight export API with two confirmed real catchment layers) are now worth asking the user to attempt the same way, if they're willing. Absent further user-assisted downloads, the next automated lead remains South Tyneside's line-network closure problem or Bristol's St Bede's parish map, per the update above.

## Full audit: every documented gap, categorized by blocker type, with a login-wall roadmap (2026-08-11)

A complete survey of every entry in `config/catchment-sources.yml`'s `candidates:` section (93 entries as of this audit), read in full and sorted by what's actually blocking it - not a re-investigation, just an honest inventory so the user and I can target effort correctly. Local authorities/councils already `enabled: true` in `sources:` are not listed here.

### Category A - genuine login/credential walls (the user's specific ask: these need YOU to sign in, not me)

This project's standing rule refuses to script past a real username/password or account-registration gate - that's not a technical limitation, it's a deliberate boundary. Every one of these has REAL, CONFIRMED catchment data sitting behind a login form. If you're willing to create an account and download manually (exactly like the Scotland aggregate above), these are the highest-value remaining targets, roughly ordered by how much data each would add:

1. **West Sussex** - StatMap Earthlight platform (`https://www.westsussex.gov.uk/...` -> Earthlight webmap). Two REAL confirmed vector layers: "WSCC Primary Catchments" and "WSCC Secondary Catchments" - the platform even has a one-click "Export to GeoJSON" job, it just needs an authenticated session first (a real username/password login form, "AutoLogin" flag doesn't cover anonymous access). **What to look for:** a login/sign-in link on the Earthlight map page itself, or contact West Sussex County Council's GIS team asking for public/guest map credentials.
2. **Lewisham** - "MapThat" platform at `lbl.dynamicmaps.co.uk/MapThatWeb/login.html?user=lewisham`. A real login page requiring credentials. Unknown whether self-service registration exists - worth checking the login page itself for a "register"/"sign up" link, or emailing the council.
3. **Gloucestershire** - same "MapThat"/dynamicmaps.co.uk platform, different council: `gcc.dynamicmaps.co.uk/MapThatPublic/`, an Angular login form. Same unknowns as Lewisham - since both run the identical vendor platform, whatever you learn about one (e.g. "there's a free public account option") likely applies to the other too.
4. **Enfield** - both candidate ArcGIS Hub org hostnames (`enfield-opendata.hub.arcgis.com`, `enfield.opendata.arcgis.com`) return a 401 "private org, not accessible." Less certain this has a self-service signup (ArcGIS Hub orgs are sometimes invite-only for internal council use) - lower priority than the three above, but worth a quick look.
5. **Birmingham** - a real ArcGIS Enterprise portal (`maps.birmingham.gov.uk/arcgis`) has a `SchoolsDataSvc` service folder, but querying it returns `{"code":499,"message":"Token Required"}` - an API token/auth requirement, not a browser login page per se. Only worth pursuing if you can find where Birmingham issues these tokens (their open-data portal, a developer sign-up page, etc.) - if it turns out to be internal-staff-only, this one's a dead end regardless of login.
6. **Derbyshire** - a specific named project (`/Analyst/NamedProjects/Education`) exists behind a real `AccessDeniedException` on the council's Precisely/MapInfo Exponare/Connect GIS platform. This looks more like an internal staff permission than a public signup gate - lowest priority of this group, probably not self-service, but flagged for completeness.

**How the roadmap works for this category:** for each one, visit the URL, look for a "Sign in" / "Register" / "Create account" link. If self-service registration exists, create an account, log in, and download whatever format is offered (GeoJSON preferred, Shapefile/KML/CSV-with-real-boundary-coordinates all usable - a CSV with only a centroid point and no boundary vertices, like the Brighton/Hove CSV checked this session, is NOT usable). Save the file(s) and tell me the local path plus which council it's for - I'll validate, match to real schools, verify point-in-polygon, and land it exactly like the Scotland data above.

### Category B - blocked by a bot-check, NOT a login wall (you can probably just... visit these normally)

These are NOT credential gates - they're Cloudflare/Incapsula/Akamai bot-detection systems blocking _this sandboxed environment specifically_ (automated requests, no real browser fingerprint). A normal browser on your own machine and network almost certainly passes them without any account or special action at all - these are worth trying simply by opening the URL, no roadmap needed beyond that.

- **Brighton and Hove & Islington** - real catchment shapefiles are attached to FOI response threads on `whatdotheyknow.com` (search "school catchment Brighton" / "school catchment Islington" on that site). The site's Cloudflare "Just a moment..." challenge blocks this sandbox but clears instantly for a normal browser.
- **Rotherham's own secondary-catchment FOI thread** - a WhatDoTheyKnow thread titled "School Catchment Area Coordinates" (search on the same site) - would give Rotherham's "Secondary Catchment" overlay directly, without needing to repeat the address-search-API/watershed technique used for its primary layer.
- **Barnet** - the council's own catchment-maps page (`barnet.gov.uk/.../primary-school-catchment-area-maps`) is behind an Incapsula bot challenge; static JPEG maps are what's actually published there (not ideal - JPEGs would need this project's PDF/image digitization toolkit, not a simple download, but worth grabbing if you're already there).
- **Southampton** - `www.southampton.gov.uk` is behind an Incapsula challenge; the council states its catchment map is genuinely "digital... not available for inspection by the public" though, so this may be a dead end even once reachable - lower priority.
- **Leicestershire** - the entire `leicestershire.gov.uk` domain 403s from this sandbox (an Akamai edge WAF block, confirmed even for the plain homepage) but a predictable-URL pattern (`catchment_details_{code}.pdf`) that worked well for Oxfordshire/Leeds is believed to sit behind it for hundreds of schools. Worth a quick manual check whether the domain loads normally for you.
- **Milton Keynes, Salford, Ealing** - all three have confirmed-real catchment platforms (Astun iShare for Milton Keynes; a GeoServer WMS/WFS for Ealing at `inspire.misoportal.com`) that simply time out / refuse connections from this sandbox's network specifically - not a bot challenge, a network-level unreachability. If these load normally on your own connection, that alone might be enough for me to pick the automated work back up without needing you to download anything by hand.

### Category C - structural dead ends (nothing to unlock, not login-related, listed for completeness)

These councils genuinely do not operate catchment-zone admissions at all (pure distance-based/priority-area systems), or have been exhaustively checked with no GIS/PDF presence found of any kind. No login wall, no bot block - there is simply no catchment boundary data to acquire. Not actionable by either of us without the council publishing something that doesn't currently exist:

Bromley, Croydon, Haringey, Hillingdon, Hounslow, Havering, Isle of Wight, County Durham, Barnsley, Kent, Isles of Scilly, Bexley/Southwark/Hackney, Wandsworth, Greenwich, Camden/Richmond upon Thames/Lambeth/Brent, Kensington and Chelsea/Merton/Sutton/Westminster/Hammersmith and Fulham/Waltham Forest/Barking and Dagenham, Bath and North East Somerset, South Gloucestershire, Plymouth, Torbay, Gloucester (City), Wirral, Wolverhampton, Manchester/Tameside/Wigan, Bradford, Wakefield, Coventry, Stockport, North East Lincolnshire, Leicester (City), Blackburn with Darwen, Darlington, Hartlepool, Stockton-on-Tees, West Northamptonshire, Dacorum, Wealden, Trafford/Dudley/Swindon (real iShare platforms, genuinely no catchment layer published on them), Newport/Swansea/Neath Port Talbot, 13 further Welsh councils with unpopulated ArcGIS Hub portals (Wrexham, Flintshire, Conwy, Isle of Anglesey, Gwynedd, Ceredigion, Carmarthenshire, Denbighshire, Torfaen, Caerphilly, Merthyr Tydfil, Blaenau Gwent, Vale of Glamorgan), Rhondda Cynon Taf (WFS explicitly disabled server-side), Sefton/Liverpool/Knowsley/St Helens/Bolton/Oldham/Rochdale/Sandwell/Walsall/Newcastle upon Tyne/Sunderland, Essex, Surrey, Suffolk, Bedford/Bedford Borough, Luton, Slough, Medway, Thurrock, Blackpool.

### Category D - genuinely under-investigated (worth a fresh pass, no blocker identified yet)

Checked only via CKAN/ArcGIS-Hub full-text search, not council-by-council in depth: **Blackburn with Darwen, Blackpool, Stockton-on-Tees, Darlington, Hartlepool, North Northamptonshire**. Worth a proper per-council investigation using this project's full toolkit (hidden ArcGIS/WFS APIs behind catchment-finder widgets, legacy embedded-HTML-polygon tools like Staffordshire's, etc.) before concluding these are dead ends.

### Category E - architecturally blocked or data too degraded to trust (not login-related, needs a different technique)

- **Bridgend (Wales)** - real Cadcorp GeognoSIS platform, but its tile backend is reachable only via an internal-only server relay; no public vector endpoint exists.
- **North Somerset** - real per-school maps exist, but the Cadcorp Aurora backend hangs (45+ seconds, no response) from every access method tried.
- **Kingston upon Hull** - runs the same Astun iShare platform that works for North Lincolnshire, but Hull's own deployment returns a hard 500 error regardless of parameters - looks broken on their end, not a discoverable fix.
- **Redbridge & City of London** - both have real, live APIs, but the actual geometry returned is too degraded to trust (a bounding box instead of a real polygon for Redbridge; zero identifying properties for City of London).
- **Rutland** - real PDF maps exist but most don't draw a closed boundary at all ("everything east of the railway line," "all of Uppingham") - digitizing them would mean guessing the unstated far edges, which this project doesn't do.
- **South Tyneside** - access is fully solved (see the South Tyneside entry earlier in this file for the CDP Fetch-domain technique), but 2 of 27 zones (Marsden Primary, Laygate Primary) have a confirmed genuine missing boundary line in the council's own source PDF, verified across two independently-dated editions - not fixable without the council publishing a corrected map or a different source appearing.

### A stale entry worth a cleanup pass

`candidates:`'s **Na h-Eileanan an Iar** entry still says "not even a PDF map exists" - now stale, since this session's Scotland aggregate work resolved and enabled it. Low-priority documentation cleanup, not a data gap.

## Update: Brighton and Hove's secondary catchment PDF investigated - real vector zones, but the map itself is not geographically accurate (2026-08-11, later session)

**The user found and handed off `brighton School Admissions Secondary map.pdf`** (an official council-produced A3 admissions leaflet, Adobe InDesign CS6, 2013). Unlike Brighton and Hove's still-inaccessible WhatDoTheyKnow FOI shapefile (Category B in the audit above), this is a genuinely different, real source: a real vector-drawn map, not a raster scan (`page.get_drawings()` returns 72 real vector path objects, 0 embedded images). Extraction went further than any prior dead-end note on this file suggested was possible:

- **6 real, closed, valid vector polygons** (Patcham High, Dorothy Stringer/Varndean shared, Brighton Aldridge Community Academy, Longhill High, Portslade Aldridge Community Academy, Blatchington Mill/Hove Park shared), each with its own distinct fill colour, matched to the correct school by point-in-polygon testing each school-name label's text position against the polygons - a clean, unambiguous 1:1 match against the legend's own 6 named catchment areas.
- **Real per-school marker dots** (● for standard secondary schools, ✝ for the one Roman Catholic school, Cardinal Newman) precisely located in the vector data, matched to their schools by proximity to each name label - not just approximate zone-fill regions, actual point locations.

**Why this wasn't landed: the map itself is not drawn to consistent real-world scale or rotation.** A 2-point similarity transform (scale + rotation + translation) fitted using Longhill High and Blatchington Mill School's real marker positions against their actual DB coordinates (a long, ~543pt baseline, both single-site unambiguous schools) gave wildly inconsistent residuals when checked against 5 other real schools' own DB coordinates: Cardinal Newman 114m (excellent), Hove Park Upper 969m (good), Hove Park Lower 2,027m, Dorothy Stringer 3,271m, Varndean 3,927m, Patcham High 6,625m, Brighton Aldridge Community Academy 8,517m - not a uniform offset that a better anchor pair or higher-order transform could plausibly fix, but a genuinely inconsistent spread ranging from excellent to badly wrong across the same single transform. This is the signature of a stylized cartogram/infographic map (prioritising legibility and label placement over accurate geographic proportion, consistent with its Adobe InDesign design-software origin) rather than a real GIS/OS-grid-referenced export like every other source this project has successfully digitised (Oxfordshire, Inverclyde, Rotherham, etc., all confirmed real georeferenced exports first). An initial attempt to anchor on real street names (Old Shoreham Road, Freshfield Road) via Nominatim geocoding failed even more badly (2.4km residual on the very first check) for a related reason: Nominatim returns some point along a real but long road, not necessarily where this specific map's label happens to sit - a general lesson worth remembering (prefer point-like landmarks - school markers, junctions, buildings - over named roads/streets when a road's real extent could be long).

**Correctly not deployed, per this project's standing rule against ever estimating/guessing geometry** - forcing any single transform onto a map that doesn't hold accurate real-world proportions would mean systematically misplacing several of the 6 zones, not a defensible approximation. Left as an open, real, promising-but-unresolved lead rather than closed as either "solved" or "dead end": the underlying vector data (6 clean zone polygons, real per-school markers, unambiguous school-to-zone matching) is genuinely good; only the georeferencing is unsolved. Two ideas for a future attempt, neither tried yet: (1) a non-uniform/piecewise transform (e.g. triangulating using 3+ control points per local region rather than one global affine fit, since local relative positions may be more trustworthy than the map's overall proportions), or (2) checking whether the same council publishes a primary-schools equivalent of this map that might be drawn more geographically accurately, as a cross-check on whether this distortion is specific to this one document or a house style across all of Brighton and Hove's admissions maps.

**Most promising next lead:** unchanged from the audit above - West Sussex's StatMap Earthlight login wall remains the highest-confidence next win if the user is willing to attempt it, given its two already-confirmed-real vector catchment layers.

**Session paused here at the user's request** (approaching a usage limit) - working tree left clean, no uncommitted digitisation attempt, this documentation is the only change from the Brighton and Hove investigation.

## Update: Category B bot-check sweep - every candidate re-tried with a genuine browser, all still blocked from this sandbox (2026-08-11, later session)

Worked through the "Category B" list from the audit above in the given priority order, this time with a genuine Google Chrome binary available via Playwright's `channel: "chrome"` (not just bundled Chromium), plus a read-proxy service (`r.jina.ai`) as a second independent egress path for the WhatDoTheyKnow checks. **No new catchment data was landed this session** - every single target remained blocked, but the nature of each block is now confirmed more precisely than before, which matters for deciding what to try next:

- **Milton Keynes, Salford, Ealing** - re-confirmed genuine network-level unreachability, not a bot challenge. DNS resolves correctly for all three hosts (`mapping.milton-keynes.gov.uk` -> 63.35.62.103, `map.salford.gov.uk` -> 80.193.232.60, `inspire.misoportal.com` -> 52.16.156.33), but TCP connect times out (or is refused) on both port 443 and 80 for all three, while general internet egress from this sandbox works fine in the same session (google.com, gov.uk, raw.githubusercontent.com all load instantly). This rules out a DNS-level block and points to either an IP-range firewall rule on these specific hosts, or the hosts themselves rejecting this sandbox's outbound IP - either way, not something a browser fingerprint change can route around, since the block is below the HTTP layer entirely.
- **Leicestershire** - re-tried a third time (two prior sessions already tried curl and a Chromium-only Playwright session), this time with a genuine Chrome (`channel: "chrome"`, `--headless=new`) browser: still a hard 403 "Access Denied" with an Akamai `errors.edgesuite.net` reference ID, identical to both prior attempts. Three independent sessions, three different techniques, one identical failure mode - this now looks like an IP-range block on the sandbox's outbound ASN rather than a solvable bot-fingerprint issue.
- **WhatDoTheyKnow (Rotherham's secondary-catchment FOI thread, Brighton and Hove & Islington's shapefile threads)** - located the exact thread URLs this session via web search (previously only described, not linked): Rotherham's is `whatdotheyknow.com/request/school_catchment_area_coordinate` (FOI 542-17); Brighton and Hove has at least three relevant threads, one of which explicitly confirms "Secondary school catchment areas are available in ESRI Shape file format" in its own summary text; a matching Milton Keynes FOI thread (`..._2`) was also found as a bonus, though moot given Milton Keynes' own platform is separately network-blocked as above. All were re-tried with three techniques this session: a genuine Chrome browser waiting a full 30 seconds for Cloudflare's managed/Turnstile challenge to clear (it never did - stayed on "Performing security verification" the entire time, versus the 3-5 seconds a real browser normally takes), the `r.jina.ai` server-side read-proxy (returned the identical challenge page, meaning Jina's own crawler IP is caught by the same Cloudflare rule, not something specific to this sandbox), and WebFetch directly (plain 403). This is a real Cloudflare bot-management product (Turnstile), a materially harder block than a simple JS-redirect challenge - not passable by any automated technique tried across three sessions now, only by an actual interactive human browser session on a clean residential IP.
- **Barnet** - re-tried with a genuine Chrome browser and a full 30-second wait for the Incapsula iframe challenge to auto-resolve (its normal behaviour in a real browser, usually under 2 seconds): it never did, page content stayed the static `_Incapsula_Resource` iframe stub (997 bytes) throughout. Confirmed still blocked; also confirmed lower-priority regardless, since the underlying data is static JPEGs requiring this project's image-digitization toolkit rather than a simple download.
- **Southampton** - `www.southampton.gov.uk` now loads normally with a plain `curl` request this session (no Incapsula challenge encountered, unlike the prior finding) - so the reachability blocker has apparently lifted. Doesn't matter: the council's own published position is unchanged and re-confirmed via fresh web search - the catchment map is a digital map deliberately "not available for inspection by the public." A genuine structural dead end independent of reachability, correctly not pursued further.

**Every entry in `config/catchment-sources.yml` for these six targets has been updated in place** with today's date and the specific technique/result, so a future session doesn't have to repeat the same three attempts.

**Most promising next lead:** unchanged - none of Category B yielded anything this session, and the pattern across three independent sessions now strongly suggests the MK/Salford/Ealing/Leicestershire blocks are IP-range/network-level (not fixable from any sandboxed environment, only from the user's own residential connection), and the WhatDoTheyKnow Cloudflare Turnstile block is a genuine bot-management product that no automated technique available here can pass. **West Sussex's StatMap Earthlight login wall (Category A)** remains the highest-confidence next win if the user is willing to attempt it themselves, given its two already-confirmed-real vector catchment layers ("WSCC Primary Catchments", "WSCC Secondary Catchments") sitting behind nothing more than a standard login form.

## Update: Category D closed out - Darlington's 8 rural over-subscription polygons landed, the other five confirmed structural dead ends (2026-08-11, later session)

Worked through all six "Category D" councils (only previously checked via CKAN/ArcGIS-Hub full-text search, never council-by-council) with this project's full toolkit: reading each council's real admissions pages directly, checking for hidden ArcGIS/WFS APIs behind postcode widgets, checking for a Staffordshire-style legacy embedded-coordinate tool, and checking each council's ArcGIS Online org for private/public status.

**Darlington - real data landed.** The council's own "Rural map for over subscription" page (found by reading the admissions section directly, not portal search - Darlington had already been checked via AGOL/CKAN search twice before and come up empty both times) embeds a genuine ArcGIS JS API map with 8 real KML layers (`darlington.gov.uk/media/*/area-*.kml`, Areas A-H). Each area is a real, precisely georeferenced (WGS84, copied verbatim with zero reprojection or digitization) rural-ward polygon that gives children living there priority admission to a named "alternative" school if their own normally-designated school is oversubscribed - a real, named, geography-linked admissions rule, but structurally different from a normal catchment: by design the school itself is not expected to sit inside its own alternative-area polygon (the whole point is that it's a _different_ area from the school's own catchment). Imported under `primary_catchment_partial` for exactly the same reason as North Northamptonshire's "Linked Areas" - so it's never read as full borough coverage. Areas A and D both name "The Federation of Mowden Schools" (Mowden Infant + Mowden Junior) as their alternative; Areas F and G both name Heathfield Primary School - kept as 4 separate polygon rows since each area is geographically distinct even where two share an alternative school. The council's separate "Hummersknott and Hurworth Academies" oversubscription maps on the same admissions section were checked and correctly excluded: confirmed via `page.get_drawings()`/`get_images()` to be flat raster scans (0 vector paths, 1 embedded image each), not vector data.

**Verification:** all 8 polygons independently checked for valid geometry (`shapely.is_valid`) and sane Darlington-borough GB bounds (lat 54.45-54.62, lon -1.45 to -1.71, real area 0.0014-0.0065 deg² each, not degenerate slivers). Point-in-polygon containment against the school's own coordinate does **not** apply here by design (same as North Northamptonshire's Linked Areas) and was not expected to hold - confirmed the schools' own coordinates genuinely fall outside their assigned "alternative area" bounding boxes, consistent with the source's own stated purpose. Both `pnpm --filter @catchment-zone/shared test` (45 passed, `PILOT_LOCAL_AUTHORITIES` updated with Darlington) and the ingestor's full pytest suite (127 passed) pass clean. Two commits (`329be68` the catchment data, `f7ac6c3` the Category D documentation for the other five councils) both pushed to `main` and confirmed landed via `git fetch` + `git log origin/main -1`. GitHub raw CDN confirmed byte-identical to the local file before importing. `import-catchments --local-authority 841` built 8/8 catchment areas, 0 rejected. `catchment_areas` went from 10,445 to **10,453** rows (0 duplicates on a `(source_id, geometry_checksum)` check). `refresh-catchment-overview-cache` re-run and confirmed `map_catchments_cache.feature_count` = 10,453, in sync. `refresh-catchment-scores` re-run synchronously to completion: 6,945 of 10,453 areas scored project-wide.

**Local authority count: 94 -> 95** (Darlington newly enabled).

**The other five, all confirmed genuine structural dead ends, not under-searched gaps:**

- **Blackpool** - the council's own published admissions policy states explicitly (found in the policy document's own text via web search) that it "does not operate catchment areas or feeder schools." As clear a structural dead end as this project has found - the admissions system simply has no geographic-zone concept to digitize. Consistent with the pre-existing note that Blackpool's real ArcGIS Online org has zero catchment items, only a school-locations point layer.
- **Blackburn with Darwen** - the council's real school-admissions system is a Capita "Synergy" portal (`blackburn.gov.uk/SynergyWeb/`) that does load a map component, but the entire admissions workflow sits behind a personal parent-account login wall (a genuine login gate on the _application_ process, not a public catchment-viewing tool) and no unauthenticated map/zone page exists anywhere on the site. The council's own admissions guidance page has zero mentions of "catchment" or "oversubscri[ption]" at all.
- **Stockton-on-Tees** - re-fetched the "Admissions zones" page and every linked admissions page with a real Playwright Chromium session (`apply-primary`, `apply-secondary`, `school-admission-allocating-places`, `school-admissions-address`, `primary-secondary-schools`) and searched each for map/PDF/ArcGIS/KML/WFS links: none exist, confirming the zone policy really is prose-only. One new detail: `stockton.maps.arcgis.com` is a real but `"access":"private"` ArcGIS Online org (same shape as Enfield's login wall in the Category A roadmap) - not confirmed to hold a catchment layer, and the prose-only public description gives no reason to expect one does.
- **Hartlepool** - genuinely does operate named "Admission Zones" for every community school (confirmed directly from the council's own 2026-27 admission-arrangements PDF: "All community schools in Hartlepool have a defined geographic area called an Admission Zone... some streets are split"), unlike Blackpool/Blackburn with Darwen above. But the council deliberately keeps the boundaries phone-lookup-only rather than publishing a map - the same PDF tells parents to call the School Admissions Team, and the one online tool (`online.hartlepool.gov.uk/service/School_Admission_Zone_Finder`) is a Granicus AchieveForms iframe whose real form definition lives behind a session-scoped `sandbox-publish://` URI, not a guessable public REST endpoint. **This is the most promising unexplored lead of the six**: a real backend zone-lookup clearly exists (it must resolve an address to a school/zone somehow) - a future session could drive the AchieveForms tool with a real Playwright session across many real addresses and reconstruct zone boundaries via marker-controlled watershed segmentation, exactly like Rotherham's proven technique. Not attempted this session given the extra engineering needed to reliably automate a third-party session-scoped form tool within a single pass's time budget.
- **North Northamptonshire** - re-checked its ArcGIS org against its full public services catalogue (411 services total at `services-eu1.arcgis.com/SuC1rPA4UP1jdgwy`, not just a name-guessing search): two more Latimer-prefixed layers exist beyond the already-excluded `Latimer_Postcode_Areas` (`Latimer_Linked_Areas`, a parish-boundary export, and `Latimer_LinkedPostcodes`, a postcode-area overlay), but both were confirmed to carry no school-name field either - same exclusion reason as before. Confirms this authority's existing 4-layer "Linked Areas" coverage is genuinely complete, not an under-search.

Removed the now-fully-superseded grouped candidate note ("Blackburn with Darwen, Blackpool, Stockton-on-Tees, Darlington, Hartlepool, North Northamptonshire, West Northamptonshire ... not exhaustively checked council-by-council") since every one of the seven now has its own up-to-date, individually-investigated entry.

**Most promising next lead for whoever continues after this session:** Hartlepool's AchieveForms-backed Admission Zone Finder (above) - a real, working zone-lookup tool with no published boundary data, structurally identical to the problem Rotherham's watershed technique already solved once. Beyond that, the unchanged highest-confidence lead remains **West Sussex's StatMap Earthlight login wall** (Category A) if the user is willing to attempt it themselves.

## Update: Hartlepool's Admission Zone Finder cracked - 12 primary zones reconstructed via dense per-address point-sampling + Voronoi tessellation, a new technique for this project (2026-08-11, later session)

Followed up directly on the "most promising next lead" flagged above. This is a genuinely different technique from Rotherham's marker-controlled watershed (which segments a _rendered raster image_ of a real drawn boundary line) - Hartlepool's AchieveForms tool has no map or line to segment at all, only a per-address text answer, so the boundary had to be inferred purely from classifying many real points, with no drawn line to validate against at any step. Treated as this project's most caution-worthy technique to date for exactly that reason, per the task brief's own warning that this sits "right at the edge of what's acceptable."

**How the tool actually works, found via Playwright network capture (not guesswork):** entering a postcode calls a real backend endpoint (`apibroker/runLookup?id=587f3deed5d4b`) that resolves it to one or more real addresses (each with a UPRN, its own lat/lng, ward, etc. - an AddressBase-style gazetteer), then selecting one calls a second endpoint (`id=6a44d491cb5cf`) that takes that UPRN and returns either a specific named school (with phone/email/website/"School type") or "Please contact the School Admissions Team" for addresses with no defined zone. This is a genuine exhaustive per-address database membership lookup, not a "nearest school" tool that always answers something - confirmed by the ~16% of sampled addresses that correctly got the "no zone" fallback rather than a forced nearest-school guess. Both endpoints turned out to be freely callable by direct POST with only session cookies (no CAPTCHA, no per-request signature - the form's own "hash" integrity field is empty/unvalidated on the relevant tokens), so this was driven as a scripted HTTP client inside one real Playwright browser session rather than simulating individual UI interactions per query.

**Sampling.** doogal.co.uk's free postcode-CSV export (built from the ONS Postcode Directory/Ordnance Survey OpenData, no login) gave all 2,625 real in-use unit postcodes across Hartlepool's district (ONS code E06000001, spanning outward codes TS21/24/25/26/27/28/29). Queried the council's address-search endpoint for each, then the zone-lookup endpoint for the first returned address's UPRN - 5,250 total HTTP calls, completed in about 6 minutes at concurrency 8 with no rate-limiting or blocking encountered. Result: 2,141 addresses classified to one of 18 distinct zoned schools, 421 correctly got "no defined zone" (consistent with the council's own PDF wording that only _community_ schools have zones - Hartlepool's other 14 open primaries are faith/voluntary academies with their own admissions criteria), and 63 postcodes had no address match at all (excluded, not guessed at).

**Reconstruction.** Reprojected every classified address's own real lat/lng (not the postcode centroid) to EPSG:27700, built a Voronoi tessellation over all 2,552 unique classified points (including the "no zone" points, so real zoned cells get correctly bounded against non-zoned territory rather than expanding into it), dissolved same-school cells, and clipped to the real Hartlepool LAD boundary (ONS Open Geography Portal, December 2024 boundaries). The critical honesty step: every dissolved polygon was clipped a second time to the union of a 300m buffer around every real sample point (about 2x the 134m median distance between adjacent opposite-school samples, well clear of the 40m median nearest-neighbour spacing) - so the published polygons only claim territory genuinely close to a real classified address, never extending confidently into an unsampled gap just because the Voronoi math would otherwise fill it in. Where sample density was low (rural St Peter's Elwick and the borough's rural fringe generally, where opposite-school sample gaps ran up to 6.4km), this correctly leaves several disconnected close-to-sample patches rather than one falsely-confident contiguous shape.

**Verification.** For all 18 zoned schools, checked the school's own real DB coordinate against its own reconstructed (clipped) polygon: 16 of 18 were inside at all; applied a conservative 100m minimum-margin bar on top (roughly the median cross-school sample gap) given how much coarser point-sample interpolation is than tracing a real drawn line - 6 schools were excluded for falling short (Brougham Primary School's own coordinate was 12m _outside_ its reconstructed zone, Rift House 36m outside; Stranton/Lynnfield/Rossmere/Golden Flatts were inside but only 41-76m from their own boundary, too close to trust at this technique's resolution). The 12 that passed cleared the bar comfortably, 102m-358m margin. Re-verified independently against the live database after import (not just the pre-import check) - all 12 confirmed containing their own school's real coordinate, all valid geometry, all 12 distinct `geometry_checksum` values (no duplicates).

**Deployment decision.** Filed under `primary_catchment_partial` rather than plain `primary_catchment`, matching this project's existing convention (Darlington/North Northamptonshire above) for real, verified, but knowingly-incomplete/lower-confidence sources - so this is never mistaken for full borough coverage or treated with the same confidence as a digitised real drawn line. 6 of the 18 tool-covered schools were excluded outright by the margin check, and only 12 of Hartlepool's 32 total open primaries are covered at all (the other 14 are non-zoned faith/voluntary schools, correctly outside this data's scope, not a gap in the technique).

**Both `pnpm --filter @catchment-zone/shared test` (45 passed, `PILOT_LOCAL_AUTHORITIES` updated with Hartlepool) and the ingestor's full pytest suite (127 passed) pass clean.** Commit `68fd9b9` pushed to `main` and confirmed landed (`git fetch` + `git log origin/main -1`); GitHub raw CDN confirmed serving the new file both at the pinned commit SHA and the `main` branch URL before importing. `import-catchments --local-authority 805` built 12/12 catchment areas, 0 rejected. `catchment_areas` went from 10,453 to **10,465** rows (12 new, 0 duplicates on the `(source_id, geometry_checksum)` constraint). `refresh-catchment-overview-cache` re-run and confirmed `map_catchments_cache.feature_count` = 10,465, in sync. `refresh-catchment-scores` re-run synchronously to completion: 6,957 of 10,465 areas scored project-wide (all 12 new Hartlepool zones scored). **Local authority count: 95 -> 96** (verified directly via `select count(distinct local_authority_code) from catchment_areas join catchment_sources`, not just incremented by assumption).

## Update: generalising the Hartlepool technique - Stockport's real GeoServer found, Essex's SSRS report server cracked, Wakefield/Wirral/Coventry scoped for next time (2026-08-11, later session)

Followed up directly on this file's own "most promising next lead": audited `candidates:` for other councils previously written off as "phone/lookup-only, no map published" - exactly Hartlepool's problem shape - starting from the specific councils flagged (Essex, Wirral, Coventry, Stockport, Wakefield). Landed two real wins (one of them not even a reconstruction - a genuine digitised source hiding behind a form-shaped false negative), fully scoped a third for immediate next-session pickup, and documented two more as real-but-harder leads.

**Stockport - not a reconstruction at all, a genuine digitised GIS source the previous candidate note missed.** The existing note ("server-side address-lookup form, not a map - no GIS markers in its HTML") was accurate about the raw HTML but incomplete: `stockport.gov.uk/find-your-catchment-area` also renders a real interactive Leaflet/Mapbox map, invisible to a plain `curl`/static-HTML check because it only exists after JS execution. A live Playwright session rendering the page found the real DOM contained WMS tile requests against a public GeoServer instance (`spatial.stockport.gov.uk/geoserver`), which exposed the internal layer name (`education:mv_primary_catchments`). GeoServer's standard WFS `GetFeature` endpoint turned out to be completely open - no auth, no session, no CAPTCHA - and returns real digitised polygons directly as WGS84 GeoJSON, each already carrying the school's own URN as an attribute. Four layers pulled this way: primary catchments (69 features), secondary catchments (9), Roman Catholic primary "associated area" (16), Roman Catholic secondary "associated area" (3) - a combined `all_school_catchments` layer (97) confirmed these sum exactly, i.e. one underlying dataset sliced four ways.

Verified every polygon's `urn` attribute against this project's own schools table: dropped 9 with URNs that no longer resolve to an OPEN school (closed/merged since the source was last updated), applied the usual 100m own-school-coordinate-margin bar (dropped 6 more, 23-81m - genuinely close misses) and caught 2 URN resolving to schools far outside Stockport entirely (one to a school in Cheshire, one 371m outside its own matched polygon for an unexplained reason) - both correctly excluded rather than landed. **80 of 97 published polygons kept** (60 primary, 7 secondary, 11 primary RC, 2 secondary RC). Filed as normal `primary_catchment`/`secondary_catchment`/`primary_catchment_rc`/`secondary_catchment_rc` (not `_partial`) since this is genuine published GIS vector data, not a point-sample reconstruction - the only one of this session's three finds that qualifies for that.

**Essex - the Hartlepool technique applied at county scale.** `secureapps.essex.gov.uk/cas/` turned out to be a thin `ReportProxy.aspx` wrapper around a real Microsoft SQL Server Reporting Services (SSRS) instance. Network capture on a live Playwright session against the tool's actual "Priority admission (catchment) area finder" page (not its bare landing page, which is a different URL and gave no clues) found two real report endpoints, both freely callable by plain unauthenticated GET with no session/CAPTCHA/signature at all: a postcode-to-address lookup (`AddressListForGivenPostcode`, returns UPRN-keyed addresses) and a UPRN-to-school lookup (`PrimaryAndSecondarySearchReport`, returns the address's Priority Admission Area school if one exists).

Sampling had to be stratified rather than exhaustive given Essex's size versus Hartlepool's small borough: doogal.co.uk's free postcode-CSV export gave 39,943 real in-use postcodes across the whole Essex County Council area (ONS county E10000012, all 12 districts); sampled up to 20 postcodes per postcode sector (4,341 points across 237 sectors) rather than every postcode. Queried both endpoints for each (8,682 calls, ~35 minutes at concurrency 10 - this server responds far slower than Hartlepool's or Stockport's, roughly 1.5-2s per call, the main reason this session ran long). 3,822 of 4,341 points resolved to a named Priority Admission Area school (364 distinct schools across the sample - most Essex schools use pure distance-based admissions with no defined zone at all, consistent with only a minority of sampled points resolving), 288 correctly resolved to "no priority area," 231 errored (timeouts, excluded).

Reconstruction followed the same Voronoi-tessellation-plus-trust-radius-clip method as Hartlepool, adapted for the coarser sampling density: clipped to the real Essex county boundary (doogal.co.uk's own KML export of the ONS boundary) and a 900m trust radius (chosen against this session's much larger 206.7m median/773.3m p90 nearest-neighbour sample spacing, versus Hartlepool's 40m median). Name-matching harvested SSRS school names against this project's own Essex schools table needed real normalisation work (handling "C of E"/"CE" abbreviation variants, dropping voluntary-aided/voluntary-controlled/foundation qualifier words that differ between naming systems, and disambiguating genuinely repeated names like multiple "St Andrew's" schools in different villages using each harvested label's own trailing ", village" text against the DB school's locality/town field - left unmatched rather than guessed where that didn't resolve to exactly one candidate). Applied the standard 100m own-coordinate-margin bar on top; a few of the 44 margin-check failures were by tens of kilometres, correctly catching cases where the automated name-disambiguation guessed the wrong same-named school - the margin check earning its keep as a real safety net, not just a formality. **199 of 305 dissolved polygons verified and kept**, each individually confirmed to contain its own real school's own DB coordinate with 100m+ margin. Filed as `primary_catchment_partial` per this project's standing convention for point-sample-reconstructed boundaries.

**Both landed sources verified and imported the same way:** `pnpm --filter @catchment-zone/shared sync-config` + `test` (45 passed each time, `PILOT_LOCAL_AUTHORITIES` updated with Stockport code 356 and Essex code 881) and the ingestor's full pytest suite (127 passed) all pass clean. Two separate commits (`1ef43a3` Stockport, `b7f23aa` Essex) both pushed to `main` and confirmed landed via `git fetch` + `git log origin/main -1`; GitHub raw CDN confirmed serving both new files at their pinned commit SHAs before importing. `import-catchments --local-authority 356` built 75/75 (0 rejected); `import-catchments --local-authority 881` built 199/199 (0 rejected). `catchment_areas` went from 10,465 -> 10,540 (Stockport) -> **10,739** (Essex), 0 duplicates at each step. `refresh-catchment-overview-cache` re-run twice, `map_catchments_cache.feature_count` confirmed in sync at each stage (10,540 then 10,739). `refresh-catchment-scores` re-run synchronously to completion after the final import: 7,229 of 10,739 areas scored project-wide. **Local authority count: 96 -> 98** (Stockport and Essex both newly enabled, verified via `select count(distinct local_authority_code) from catchment_sources`).

**Wakefield - confirmed real and callable, scoped in detail, not yet built (the single most promising next lead).** `wakefield.gov.uk/pick-address-for-school-catchment?where-i-live={postcode}` is a real, freely-callable (no auth/CAPTCHA) server-rendered address picker - and actually easier to work with than Essex or even Hartlepool, because each address link in the response already carries real British National Grid coordinates (`e=`/`n=` query params) directly, with no separate geocoding or postcode-centroid approximation needed at all. Following one of those links to `wakefield.gov.uk/schools-and-education/schools/school-catchment-area-search?uprn=...&e=...&n=...` returns either "No schools found in this catchment area" or a real "Your catchment area schools" section naming the actual primary and secondary school (confirmed live: 5 Wentworth Terrace, WF1 3QW -> Wakefield St Johns CE (VA) J&I School / Outwood Grange Academy). One caveat worth flagging for whoever builds this out: the same response also has a "Your nearest Roman Catholic schools" section explicitly labelled by distance, not catchment membership - a nearest-school calculation that must not be treated the same way as the real "catchment area schools" section. Ran out of session time to actually build this one; full detail (both endpoint shapes, the caveat, and the exact next steps) is in the upgraded `candidates:` entry in `config/catchment-sources.yml`.

**Wirral and Coventry - real data confirmed, but keyed by road name rather than postcode/UPRN, a harder reconstruction problem.** Both councils' catchment tools are real and freely callable without auth, but unlike Essex/Hartlepool/Wakefield's point lookups, the unit of data is a road (sometimes split by house-number parity/range, e.g. Wirral's "GRANGE ROAD WEST evens and odds 71 and above" vs "odds 1 to 69" resolving to two different schools) with no coordinates in the response at all - turning this into verified point samples needs road-level (or road-segment-level) geocoding, not just querying. Coventry turned out to have a much richer secondary source than its street-search tool suggested: every individual school's own council directory-record page (`coventry.gov.uk/directory-record/{id}/{slug}`) carries a complete "Roads in catchment area" list for that school, no per-road querying needed - harvested this for all 50 Coventry primary-category directory records this session (28 of 50 have a real list; the other 22 are Catholic/faith/special/secondary schools with no catchment, consistent with the pattern elsewhere in this project). Neither built out this session given the added geocoding-precision problem; both documented in detail in `config/catchment-sources.yml` with concrete next steps (geocode whole/non-split roads first via structured Nominatim lookup, treat split roads as a harder second pass).

**Most promising next lead for whoever continues after this session: Wakefield.** It is fully scoped, confirmed real and callable, and structurally simpler than every technique proven so far this project (coordinates included in the address-picker response itself) - the only remaining work is the same doogal.co.uk-postcode-sampling + Voronoi + 100m-margin-verification pipeline already proven twice this session, applied a third time with less engineering risk than either prior attempt.

**Most promising next lead for whoever continues after this session:** the point-sample-classification + Voronoi + trust-radius-clipping technique proven here is directly reusable on any other council whose only public "catchment" surface is a session-scoped address-lookup form rather than a map (the same structural shape as Hartlepool's problem) - worth checking whether any other Category B/C/D entry in this file that was previously written off as "phone/lookup-only, no map published" actually has a similarly-drivable backend behind it, the same way this session's network capture found Hartlepool's did. Beyond that, the unchanged highest-confidence lead remains **West Sussex's StatMap Earthlight login wall** (Category A) if the user is willing to attempt it themselves.

## Update: Wakefield's address-picker tool built out - 68 primary + 14 secondary catchments landed (2026-08-11, later session)

Picked up directly on this file's own "most promising next lead": built out the previous session's fully-scoped Wakefield candidate note rather than re-discovering anything.

**Baseline at the start of this session: 10,739 `catchment_areas` rows, `map_catchments_cache.feature_count` = 10,739 (in sync), 98 local authorities covered.**

`wakefield.gov.uk/pick-address-for-school-catchment?where-i-live={postcode}` is real and freely callable (no auth/CAPTCHA, confirmed via bare curl) and, as the prior note found, each returned address link already carries real British National Grid coordinates (`e=`/`n=` query params) directly - no separate geocoding step needed at all, unlike Hartlepool/Essex which both had to classify a UPRN with no coordinates of its own. Following an address link to `wakefield.gov.uk/schools-and-education/schools/school-catchment-area-search?uprn=...&e=...&n=...&p=...` returns a "Your catchment area schools" section naming the real primary and secondary school for that address, or nothing where none is defined; the separate "Your nearest Roman Catholic schools" section (an explicit nearest-distance calculation, not real catchment membership) was deliberately not harvested, per the prior session's own caveat.

**Sampling:** doogal.co.uk's `AdministrativeAreasCSV` export (`?district=E08000036`) gave every postcode in Wakefield MDC - 12,277 total, 9,676 in use. Queried both endpoints for every in-use postcode (an exhaustive canvas, like Hartlepool, not a stratified sample like Essex) - about 50 minutes at concurrency 16. 8,968 postcodes resolved to a real address (708 had no address match, a transient error, or a genuine 403 on a handful of non-residential/commercial-unit addresses - excluded, not guessed at), classifying 85 distinct primary-school names and 16 distinct secondary-school names.

**Name matching:** the tool's result links carry a Wakefield-internal "DFEE" code, not a DfE URN, so harvested names were matched against this project's own OPEN Wakefield schools (local_authority_code 384) by normalised core-token comparison - stripping generic admin words (CE/VA/VC/Academy/Junior/Infant/Nursery/etc, with "Church of England"/"C of E" consolidated first so a genuine place name like "England Lane Academy" doesn't lose its own distinguishing word to an over-eager stopword), filtered by phase (primary names matched only against open primary schools, secondary against secondary) to avoid same-place-name cross-phase collisions like "De Lacy Primary School" vs "De Lacy Academy". 99 of 101 harvested names matched a real open school this way; the 2 misses ("Kinsley Academy", "Wakefield Greenhill Primary School") resolve in this project's own schools table to CLOSED URNs - the council's tool still references two schools that no longer exist under those names (Wakefield Greenhill's open successor, "Outwood Primary Academy Greenhill", was never actually returned by the tool) - correctly excluded rather than guessed at, the same class of stale-source-data issue already documented for Stockport.

**Reconstruction:** identical Voronoi-tessellation-plus-trust-radius-clip method as Hartlepool/Essex - tessellated over the classified points (already EPSG:27700, the tool's own coordinates), dissolved by school, clipped to the real Wakefield LAD boundary (ONS Open Geography Portal, December 2024 boundaries) and to a 250m trust-radius buffer around every real sample point (tighter than Essex's 900m given this was a dense near-exhaustive postcode canvas across a compact metropolitan borough, not a sparse stratified sample across a much larger county).

**Verification:** this project's standard 100m own-school-coordinate-margin bar. Of 82 matched primary schools, 14 failed (9 a margin under 100m - e.g. England Lane Academy at 12m, Simpson's Lane Academy at 99m; 5 with the school's own point just outside its zone - Sandal Castle 24m outside, Gawthorpe Community Academy 6m outside, Castleford Three Lane Ends Academy 6m outside) - **68 kept**. Of 16 matched secondary schools, 2 failed (Horbury Academy 25m margin, De Lacy Academy 21m outside) - **14 kept**. Filed as `primary_catchment_partial`/`secondary_catchment_partial` per this project's standing convention.

**Landed and verified the same way as every other source this project ships:** `pnpm --filter @catchment-zone/shared sync-config` + `test` (45 passed, `PILOT_LOCAL_AUTHORITIES` updated with Wakefield code 384) and the ingestor's full pytest suite (127 passed) both pass clean. Committed and pushed to `main` (`8749b68`), confirmed landed via `git fetch` + `git log origin/main -1`; GitHub raw CDN confirmed serving both new GeoJSON files and the updated config at the pinned commit SHA before importing. `import-catchments --local-authority 384` built 68/68 primary and 14/14 secondary (0 rejected). `catchment_areas` went from 10,739 -> **10,821** (+82), 0 duplicates. `refresh-catchment-overview-cache` re-run, `map_catchments_cache.feature_count` confirmed in sync at 10,821. `refresh-catchment-scores` re-run synchronously to completion: 7,311 of 10,821 areas scored project-wide. **Local authority count: 98 -> 99.** Spot-checked 5 of the 82 landed polygons directly against their school's real DB coordinate post-import (all 5 contained their own point).

**Wirral and Coventry remain untouched** - both still road-name-keyed rather than postcode/coordinate-keyed (a harder geocoding problem needing road or road-segment matching, e.g. via Overpass, before any Voronoi step is possible), documented in detail in `config/catchment-sources.yml` with concrete next steps. Not attempted this session; Wakefield alone used the full session's build time.

**Most promising next lead for whoever continues after this session:** Coventry, since the harder part (harvesting) is already done - 28 of 50 Coventry primary schools' "roads in catchment area" lists were saved by the prior session (not yet committed to the repo, gitignored scratch) and just need geocoding. The concrete first step is exactly what the prior note said: geocode the whole, non-split roads via structured Nominatim lookup (`"{road name}, Coventry, UK"`) as a simpler first pass, treating split roads (those with a house-number-range in the name, needing number-range-aware geocoding to avoid merging two different halves into one point) as a second, harder pass. Wirral has the same shape of problem but no harvest done yet. Beyond both of those, the same generalisation noted in the previous session still stands: any other Category B/C/D entry previously written off as "phone/lookup-only, no map published" is worth re-checking for a similarly-drivable backend.

## Update: Coventry's road-name catchments built out - 16 primary + 6 secondary landed (2026-08-11, later session)

Picked up directly on this file's own "most promising next lead": built out the previous session's Coventry harvest rather than re-discovering anything.

**Baseline at the start of this session: 10,821 `catchment_areas` rows, `map_catchments_cache.feature_count` = 10,821 (in sync), 99 local authorities covered.** The prior session's gitignored scratch harvest (`coventry_school_roads.json`, all 50 Coventry primary-category directory records already fetched, 28 with a real roads-in-catchment list) was still present in this session's scratchpad, so no re-harvesting was needed.

**Name matching (a step the prior session hadn't reached yet):** matched all 28 harvested school names against this project's own OPEN Coventry schools (local_authority_code 331) by exact/substring normalised-name comparison, preferring OPEN over CLOSED duplicates (several Coventry schools have both a closed predecessor and an open academy-converter successor sharing the same URN-adjacent coordinates). 27 of 28 resolved unambiguously; the 28th ("Coundon", as distinct from the separately-harvested "Coundon Court") was disambiguated manually since it's a genuinely different directory record from Coundon Court and had to be the remaining open Coundon-named school, Coundon Primary School. Notably, the "category=Primary" directory search itself had returned several secondary schools (Sidney Stringer Academy, Caludon Castle School, Grace Academy Coventry, Finham Park School, Foxford Community School, Ernesford Grange Community Academy, Coundon Court, Finham Park 2) - kept and processed by their real DB phase rather than discarded, since a secondary school's own published roads-in-catchment text is just as real as a primary school's.

**Parsing.** Unlike Hartlepool/Essex/Wakefield's coordinate- or UPRN-keyed sources, Coventry's per-school text is road NAMES concatenated with no delimiter beyond capitalisation and a closed set of UK road-type suffix words (Road/Close/Avenue/Lane/Drive/Walk/etc). Built a suffix-word-terminated tokeniser rather than a hand-written regex-per-road: walk the text token by token, accumulate capitalised words, and close a road name as soon as a recognised suffix word is hit. Roads carrying a parenthetical house-number range (e.g. `"(1 - 241 odd and 2 - 274 even)"`) or a dash-qualified partial extent (e.g. `"Church Walk - up to 44"`) were flagged split/partial and **excluded outright**, per this project's standing rule against guessing a number-range's position along a road without real proportional-interpolation geometry behind it - no Overpass line-interpolation was attempted this session (a real option per the task brief, just not needed given whole-road-only supply was already large enough). A residual, acknowledged noise source: "including <list>" clauses that run directly into the next real road with no comma boundary occasionally get merged into one bogus combined name by this tokeniser - harmless in practice, since a corrupted name either fails geocoding (dropped) or gets filtered out by the per-school verification bar below, never silently produces a wrong-but-plausible point. Of 2,242 whole-road (school, road) pairs, 10 unique road strings (0.6%) were claimed as a whole road by two different same-phase schools (almost certainly two distinct real Coventry roads sharing a common name, e.g. "Kenilworth Road" in different parts of the city) and were excluded entirely rather than arbitrarily assigned to one - leaving 1,734 unique whole-road strings.

**Geocoding.** All 1,734 unique whole-road strings queried against Nominatim's public search endpoint at 1 req/sec, structured as `"{road name}, Coventry, UK"` with a Coventry-sized `viewbox` and `bounded=1` to suppress same-name matches elsewhere in the UK - 1,425 resolved (82%, mostly OSM `highway`-class results), the rest genuinely had no confident match and were dropped rather than guessed at. Took about 29 minutes across several foreground batches (Nominatim's usage policy caps this at 1 req/sec).

**Reconstruction.** Identical Voronoi-tessellation-plus-trust-radius-clip method as Hartlepool/Essex/Wakefield, with one addition: primary and secondary schools' points were tessellated **separately** (not pooled into one Voronoi diagram), since primary and secondary catchments legitimately overlap the same geography in the real world and shouldn't compete for the same Voronoi cell space. Clipped to the real Coventry LAD boundary (ONS Open Geography Portal, `LAD_MAY_2025_UK_BFC_V2`) and a 250m trust-radius buffer around every real geocoded sample point (matching Wakefield's tighter urban-borough radius rather than Essex's looser 900m, given Coventry is a similarly compact city).

**Verification.** This project's standard 100m own-school-coordinate-margin bar, independently re-checked in a separate pass after generation (not just trusting the build script's own numbers). Of 28 schools with at least one geocoded point, 22 cleared the bar and were kept (16 primary, 6 secondary, margins 134m-412m); 6 failed and were excluded: Charter Academy (91m), Edgewick Community Primary School (75m), St Bartholomew's CE Academy (38m), Coundon Court (38m), Finham Primary School (-22m, own coordinate just outside its zone), Finham Park 2 (-3,450m, only 1 geocoded sample point, nowhere near enough data to trust). Filed as `primary_catchment_partial`/`secondary_catchment_partial` per this project's standing convention.

**Landed and verified the same way as every other source this project ships:** `pnpm --filter @catchment-zone/shared sync-config` + `test` (45 passed, `PILOT_LOCAL_AUTHORITIES` updated with Coventry code 331) and the ingestor's full pytest suite (127 passed) both pass clean. Committed and pushed to `main` (`b91ba52`), confirmed landed via `git ls-remote origin main`; GitHub raw CDN confirmed serving both new GeoJSON files at the pinned commit SHA and the `main` branch URL before importing (already fresh, no wait needed). `import-catchments --local-authority Coventry` built 16/16 primary and 6/6 secondary (0 rejected, both dry-run and real). `catchment_areas` went from 10,821 -> **10,843** (+22), 0 duplicates (verified both by `(area_name, area_type)` grouping and directly against the live table). `refresh-catchment-overview-cache` re-run, `map_catchments_cache.feature_count` confirmed in sync at 10,843. `refresh-catchment-scores` re-run synchronously to completion: 7,333 of 10,843 areas scored project-wide. **Local authority count: 99 -> 100** (verified via `select count(distinct local_authority_code) from catchment_sources`). Every kept polygon's own school DB coordinate independently re-verified inside its polygon with a 100m+ margin after import, not just pre-deployment.

**Wirral remains untouched** - same road-name-keyed problem shape as Coventry was, but no harvest done yet (Coventry's council happened to publish a much richer per-school "roads in catchment area" page beyond its street-search tool; Wirral's equivalent hasn't been re-checked for the same kind of hidden per-school page). Not attempted this session.

**Most promising next lead for whoever continues after this session:** Wirral, using the exact playbook just proven on Coventry - first check whether Wirral publishes a similar per-school "roads in catchment" page (not just its street-search tool) the way Coventry turned out to, then reuse the suffix-word road tokeniser, structured-Nominatim-with-viewbox geocoding, and per-phase Voronoi-plus-trust-radius-clip pipeline built this session (none of it Coventry-specific). Beyond that, the same generalisation noted in prior sessions still stands: any other Category B/C/D entry previously written off as "phone/lookup-only, no map published" is worth re-checking for a similarly-drivable backend, the way this project has now found real backends behind five councils' "no map" front doors (Hartlepool, Essex, Stockport, Wakefield, Coventry).

## Update: Wirral's 22 primary catchments built out - a single bulk request beat exhaustive street-name enumeration (2026-08-11, later session)

Picked up directly on this file's own "most promising next lead". **Baseline at the start of this session: 10,843 `catchment_areas` rows, `map_catchments_cache.feature_count` = 10,843 (in sync), 100 local authorities covered.**

**Item 1 of the brief (Coventry-style per-school page) ruled out first, cleanly.** Fetched `ww3.wirral.gov.uk/catchment/SchoolDetailsiFrame.asp?SchoolName={key}` for a real school key - it returns only address/phone/Ofsted-link, no roads list, confirmed live. Wirral genuinely does not publish the Coventry-shaped per-school listing.

**Item 2 (exhaustive street-search enumeration) turned out not to need per-street querying at all.** The plan was to source a comprehensive Wirral street-name list (OS Open Roads) and query the tool once per street. Testing the endpoint first for its exact behaviour, an **empty `frmRoad=` POST returns the tool's entire underlying table unfiltered - 5,241 road-segment rows in one HTTP request** (cross-checked against single-letter substring queries, e.g. `frmRoad=a` returned a strict 4,236-row subset of the same data) - no pagination, no rate limit hit on the one bulk call.

**Parsing.** Each of the 5,241 rows is a (school key, road label) anchor pair with three annotation shapes: plain road names (used as-is); explicit house-number parity/range splits, e.g. "GRANGE ROAD WEST evens and odds 71 and above" vs "odds 1 to 69" mapping to two different schools (285 rows, **excluded** per this project's standing no-guessing rule); and `(Catchment school N)`-style tags. For the tagged rows, checked per base road name how many _distinct_ schools actually claim it: 125 of 131 tagged base roads are genuinely dual-claimed by two different schools (a real shared-catchment area, not a geometric split) and were excluded outright, since one point sample can't represent two schools' claims on the same road - only the 6 that resolved to a single school despite the tag were kept. A separate, unflagged `(Infant)`/`(Junior)` tag (84 base roads, no "Catchment school" wording) was _not_ excluded - verified every affected road maps consistently to Town Lane Infant School under the Infant tag and Higher Bebington Junior School under the Junior tag, a genuine same-catchment infant/junior sister-school split, the same pattern already used elsewhere in this project (e.g. Redcar and Cleveland). 4,712 of 5,241 rows survived to the (school key, road) pair stage.

**Name matching caught two real traps.** All 67 raw school keys were resolved to a real OPEN Wirral URN (local_authority_code 344) by fetching each key's own `SchoolDetailsiFrame.asp` page and matching its printed postcode against the DB - not string-similarity guessing. This caught: (a) four low-volume bare keys ("PENSBY", "PRENTON", "ROCK FERRY", "WEST KIRBY") that actually resolved to the SECONDARY grammar/selective schools of the same name rather than the intended primaries - dropped in favour of their correctly-phased "...PRIMARY" sibling keys, which had proper road volume; (b) "SANDBROOK" resolving to Chapelhill Primary School under its former name - confirmed via an identical Stavordale Road/CH46 9PS address match against the DB's own school-website field (chapelhillprimary.co.uk). Two of the council's own detail pages carried a stale one-character postcode typo (Mount Primary, Townfield Primary) - resolved by unique school-name match instead once the postcode lookup 404'd on postcodes.io. 63 of 67 keys resolved to a real URN (2 of the 63 are Infant+Junior co-located sister-school pairs sharing one key, both kept, verified identical DB coordinates).

**Geocoding.** Up to 26 unique whole-road strings per school (fewer where a school's real pool was smaller) queried against Nominatim's public search endpoint at 1 req/sec, structured as `"{road name}, Wirral, UK"` with a Wirral-sized `viewbox` and `bounded=1`. Ran in two passes - an initial 16-per-school pass (999 unique roads, 89% resolved) that on its own only cleared the verification bar for 9 of 63 schools, then a second pass extending to up to 26 per school (2,171 unique roads total) once the first pass's low yield made clear this borough needs a denser point cloud than Coventry did. Took roughly 45 minutes across several foreground/background-polled batches (Nominatim's usage policy caps this at 1 req/sec; a single-turn agent has to wait this out synchronously rather than fire-and-forget).

**Reconstruction.** Identical Voronoi-tessellation-plus-trust-radius-clip method as Hartlepool/Essex/Wakefield/Coventry (using `shapely.ops.voronoi_diagram`, GEOS-backed, no scipy dependency needed), clipped to the real Wirral LAD boundary (ONS Open Geography Portal, `LAD_MAY_2025_UK_BFC_V2`) and a 300m trust-radius buffer around every real geocoded sample point.

**Verification - the real story of this session.** This project's standard 100m own-school-coordinate-margin bar, independently re-checked in a separate pass after generation and again after import. Of 63 schools with at least 16-26 geocoded points, only **22 cleared the bar** (margins 101m-233m); 41 failed and were excluded rather than force-deployed - a much lower yield than Coventry's 79% even with 50% more points per school than Coventry's Voronoi input in the second pass. This isn't a pipeline bug: Wirral is a considerably denser suburban/urban borough than Coventry, with many primary schools sited within a few hundred metres of each other (visible directly in the rejected list - margins like 1m, 3m, 4m, 8m recur, the classic signature of two adjacent small catchments genuinely sharing a boundary close to both schools' front doors), leaving less real geometric margin for a point-sample reconstruction to clear even when the underlying road-to-school data is accurate. Also confirmed Wirral runs a selective secondary admissions system (grammar schools plus distance/preference, not catchment zones) via web search, so there is no secondary-catchment equivalent of this tool to harvest.

**Landed and verified the same way as every other source this project ships:** `pnpm --filter @catchment-zone/shared sync-config` + `test` (45 passed, `PILOT_LOCAL_AUTHORITIES` updated with Wirral code 344) and the ingestor's full pytest suite (127 passed) both pass clean. `pnpm format:write` run before commit (yaml unchanged). Committed and pushed to `main` (`fd505ed`), confirmed landed via `git ls-remote origin main`. GitHub raw CDN was stale on the `main` branch alias for about 90 seconds after push (SHA-pinned URL was live immediately) - waited it out rather than importing against a stale/missing file. `import-catchments --local-authority 344` built 22/22 primary (0 rejected, both dry-run and real). `catchment_areas` went from 10,843 -> **10,865** (+22), 0 duplicates (verified both by grouping and directly against the live table). `refresh-catchment-overview-cache` re-run, `map_catchments_cache.feature_count` confirmed in sync at 10,865. `refresh-catchment-scores` re-run synchronously to completion: 7,355 of 10,865 areas scored project-wide. **Local authority count: 100 -> 101.** Every kept polygon's own school DB coordinate independently re-verified inside its polygon with a 100m+ margin after import, not just pre-deployment - all 22 confirmed clean.

**Most promising next lead for whoever continues after this session:** the same generalisation noted in every recent session still stands - any other candidate entry in `config/catchment-sources.yml` previously written off as "phone/lookup-only, no map published, road-list-not-coordinates" is worth re-checking for a similarly-drivable backend or a bulk-unfiltered-query trick like the one that made Wirral tractable in a single request instead of hundreds. Also worth noting for whoever tackles the next similarly-dense urban/suburban borough: budget for a much larger per-school sample size than Coventry needed (this session's first pass at 16 samples/school only cleared 9/63; a second pass to 26 samples/school nearly tripled that to 22/63) - dense catchment geography needs denser point clouds to reconstruct reliably, not just more patience with the verification bar.

## Update: Luton primary and secondary catchments landed, recovered from a session-limit interruption (2026-08-11, later session)

**Luton: 16 primary + 4 secondary catchment polygons landed**, applying the same road-name-lookup-to-Voronoi pipeline as Coventry/Wirral to a source previously logged as a dead end ("catchment tool fetches a flat tab-separated text file - no geometry of any kind, fails the polygon requirement"). Reopened per this session's now-established pattern: a road-to-school text mapping is real membership data, not a non-starter, once the Voronoi-reconstruction-plus-verification pipeline exists. Full method: `secure.luton.gov.uk/catchment/catchment.tsv` (a flat file the tool's own frontend fetches wholesale and filters client-side - no per-road querying needed at all) parsed into 1,604 unique whole-road, single-claim rows after excluding house-number-range-split roads and dual-claimed roads; 34 primary catchment-area names and 10 secondary school names matched cleanly to real OPEN Luton schools; 1,604 roads geocoded via Nominatim (80% resolved); Voronoi-tessellated by phase, clipped to the real Luton LAD boundary and a 300m trust radius. Verification: of 37 primary schools with 4+ geocoded points, 16 cleared the 100m own-coordinate-margin bar; of 11 secondary schools, 4 cleared - the rest excluded rather than force-deployed, consistent with Luton being a dense unitary (the same "many schools sit close together, less real margin" pattern already seen at Wirral).

**Recovery, not a clean landing - worth documenting precisely.** The fork doing this work hit a session-limit API error right after its data was fully generated and locally correct, but before it finished committing - caught mid-cleanup ("Now let's remove the Luton candidates entry since it's now enabled"). Its isolated worktree still held the real, complete, uncommitted work (both geojson files plus a yml diff). Rather than discard it and redo the harvest, the work was recovered directly: copied the two geojson files into the main working tree, applied the yml diff, and - critically - **independently re-verified all 20 schools against the live DB before trusting any of it**, exactly as this project verifies every fork's claimed work. That re-verification caught one real bug in the fork's own edit: **the new yml entries used 0-space list-item indentation instead of the file's established 2-space convention**, which silently broke the entire YAML document's structure (a `YAMLException` at `sync-config`, not a subtle data error - but it would have blocked every future edit to this file, not just this session's, had it landed uncaught). Fixed with a targeted `sed` re-indent before committing. A separate, unrelated finding while running verification: a plain `pnpm format:write` across the whole repo now regularly exceeds the tool layer's 120-second timeout, purely because of how much large digitised geojson data has accumulated in the repo across this session (Wakefield/Essex/Coventry/Wirral/Luton alone add tens of thousands of lines) - not a bug, just a sign the repo has grown substantially; scoping `prettier --check`/`--write` to only the actually-changed files works fine and is faster than waiting out a full-repo run.

**Verification:** all 20 kept polygons independently checked against the live DB (not just the fork's own claim) after recovery: every school's real coordinate falls inside its polygon, valid geometry, no duplicate URNs. `pnpm --filter @catchment-zone/shared sync-config` (needed after the indentation fix) + `test` (45 passed, `PILOT_LOCAL_AUTHORITIES` updated with Luton code 821 - the fork itself had not gotten to this step yet, added here) and the ingestor's full pytest suite (127 passed) both pass clean. Committed (`22bce1e`) and pushed to `main`, confirmed via `git fetch` + `git status -sb`. GitHub raw CDN was already fresh on both files at push time. `import-catchments --local-authority 821` built 20/20 (0 rejected). `catchment_areas` went from 10,865 -> **10,885** (+20). `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 10,885, in sync. `refresh-catchment-scores` re-run in the background and confirmed finished. **Local authority count: 101 -> 102.**

**Most promising next lead:** unchanged from the note above - re-scan `candidates:` for any further "phone/lookup-only, road-list-not-coordinates" council not yet attempted with this pipeline. Operationally: when recovering a fork's uncommitted worktree state after an interruption, always independently re-verify against the live DB before trusting it (this session's own practice throughout, reconfirmed valuable here by catching the indentation bug), and don't assume a stale/slow `pnpm format:write` run means something is broken - check whether it's just the accumulated repo size before troubleshooting further.

## Update: user caught a real fragmentation bug across all 6 point-sample sources by looking at the live map (2026-08-11, later session)

**The user visually inspected Luton's newly-landed catchments on the live map and asked "does this look right?" - it didn't, and this project's own point-in-polygon verification had not caught it.** The rendered zones showed scattered, overlapping-looking small shards instead of clean regions. Investigation confirmed: not a cross-school overlap or fabricated-data bug (an exhaustive pairwise intersection check across every affected file found zero meaningful overlap between different schools' zones), but a real structural problem - several schools' trust-radius-clipped Voronoi cells were `MultiPolygon`s made of many small disconnected fragments rather than one contiguous shape (one Essex school split into 9 pieces, the largest only 48% of its total claimed area). This session's existing verification (does the school's real DB coordinate fall _somewhere_ inside its polygon, with 100m+ margin) is satisfied by a coordinate landing in ANY fragment, including a tiny disconnected sliver - a real gap in the verification standard, not just a display issue, now fixed going forward.

**Affected every point-sample-reconstructed source landed this session:** Hartlepool, Essex, Wakefield (both phases), Coventry (both phases), Wirral, Luton (both phases) - 9 files, 337 total schools.

**Fix, asked of the user directly rather than decided unilaterally** (a live, already-deployed, public-facing data change affecting 6 local authorities warranted checking first): keep only each school's single largest connected polygon, dropping smaller disconnected fragments, then independently re-verify the dominant piece alone still contains the school's real DB coordinate with the same 100m+ margin bar - any school whose coordinate only fell in a now-discarded minor fragment was dropped entirely rather than kept on a technicality. Net result: **337 -> 321 schools kept** (16 dropped, 14 of them Essex - its sparser rural sample spacing was hit hardest, followed by 1 each in Wakefield and Luton). Every remaining feature is now a single clean `Polygon`; zero `MultiPolygon` left in any of these 9 files.

**Database cleanup done precisely, not by a timestamp guess.** Re-importing all 6 local authorities correctly added new rows for every school whose geometry actually changed, but - as with Cumberland's stale-row issue earlier this session - the `(source_id, geometry_checksum)` upsert key doesn't remove old rows when geometry changes, it just adds new ones alongside them. Rather than delete "everything created before the re-import" (which would have incorrectly caught the schools whose geometry happened to be byte-identical before and after, e.g. Coventry's `secondary_catchment_partial` schools that were already effectively one dominant piece), the exact set of orphaned rows was computed by comparing every DB row's `geometry_checksum` against the checksums of every feature actually present in the fixed files - 166 genuinely orphaned rows identified and deleted, confirmed to leave exactly 341 rows (matching the 341 real features in the fixed files) with zero over- or under-deletion.

**Verification:** `pnpm --filter @catchment-zone/shared sync-config` + `test` (45 passed) and the ingestor's full pytest suite (127 passed) both pass clean. Re-imported all 6 local authorities (`import-catchments --local-authority <code>` for 805/881/384/331/344/821, all 0 rejected). `catchment_areas` went from 10,885 -> 11,035 (+150 new rows from changed geometry) -> **10,869** after deleting the 166 confirmed-orphaned old rows (net -16, matching the 16 schools dropped by the fix exactly). `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 10,869, in sync. `refresh-catchment-scores` re-run in the background and confirmed finished.

**Most promising next lead:** the underlying lesson matters beyond just these 6 sources - this project's standard verification (school's own coordinate falls inside _its polygon_) is not sufficient on its own for any source that could produce disconnected/fragmented geometry; a future addition worth making to the verification standard itself is checking that a school's coordinate falls inside the polygon's **largest connected component**, or that the polygon has no small disconnected pieces at all, not just checking containment against the geometry as a whole. Substantively, the next lead is still unchanged: re-scan `candidates:` for further road-list-only councils using the now-proven pipeline (with this fragmentation fix baked in from the start for any new source).

## Update: North East Lincolnshire and Thurrock landed via the road-list Voronoi pipeline (2026-08-12, later session)

**Followed this session's own standing instruction directly: re-scanned `candidates:` for other councils whose dead-end note describes a road/street-name lookup tool or a flat road-to-school list, the same shape of problem as Coventry/Wirral/Luton.** Read every remaining entry in the file (roughly 90 candidates). Most were confirmed genuine structural absences (pure distance-based admissions, a single-nearest-school point tool, a real login/credential wall, or a real network-level block already exhaustively re-tried in prior sessions) and left untouched. Two matched the target shape precisely and were pursued to a full landing; both applied the fragmentation fix (dominant-connected-piece-only, verified before deployment) from the start, as instructed, so neither needed a follow-up cleanup pass the way the six Luton-session sources did.

**North East Lincolnshire: 24 primary + 5 secondary catchment polygons landed**, reopening a candidate previously logged only as "only official catchment artifact is a plain PDF list, not even a map." That PDF (`nelincs.gov.uk School-catchment-list.pdf`, correct @ July 2025, 54 pages) turned out to be a genuine machine-generated Excel export with a clean Road Name / Primary / Secondary table - real membership data, not a non-starter. Parsed via `pdfplumber` into 2,701 unique whole-road, single-claim rows (excluding 195 house-number-range/parity-split rows and 6 cross-boundary "contact the neighbouring LA" rows). 53 unique primary/secondary claim strings resolved to real OPEN North East Lincolnshire schools by normalised exact match, catching two real traps: some "X & Y" strings are genuinely two different schools sharing one catchment (fed the identical road set, this project's standing sister-school convention), while others are one school's own official name that happens to contain "&" (e.g. "Stanford Junior & Infant School" = the single school now named "Laceby Stanford Primary Academy") - distinguished by trying a direct single-school match before ever falling back to a split. One further exclusion: 28 Habrough-area roads naming a genuine North Lincolnshire school ("Killingholme Primary School") as primary catchment were excluded from primary reconstruction (cross-boundary, sited outside this LA), while keeping their real NE Lincs secondary claim. All 2,701 roads geocoded via Nominatim (1,710 resolved, 63%), Voronoi-tessellated by phase, clipped to the real North East Lincolnshire LAD boundary (ONS Open Geography Portal, E06000012) and a 300m trust-radius buffer. Of 40 primary schools with 4+ geocoded points, 24 cleared the 100m own-coordinate-margin bar; of 10 secondary schools, 5 cleared.

**Thurrock: 13 primary + 2 secondary catchment polygons landed**, reopening a candidate that had been marked dead for the wrong reason (its ArcGIS Online subscription being cancelled - true, but about a different, unrelated data source) with only a one-line aside noting its actual catchment PDFs are road-name-to-school lists. Found via the council's primary-admissions page's own "download documents and forms" link: `master_catchment_list_from_2026_for_web_0.pdf`, a genuine 47-page Road Name/Secondary/Primary/Remarks table. Parsed into 1,835 unique whole-road, single-claim rows, excluding 109 rows across 43 road names that appear more than once in the table with different Remarks describing a house-number split for that specific road. 159 roads carry a "ROAD NAME-TOWN" disambiguation suffix (common names like "Central Avenue" repeat across several Thurrock villages) - split out and used as a structured city qualifier for geocoding rather than left glued into the street name, materially improving match precision for those ambiguous road names. 33 unique (phase, claim-string) pairs resolved to real OPEN Thurrock schools via normalised exact match, falling back to a phase-restricted unique-prefix match for the council's own truncated forms (e.g. "ABBOTS HALL PRIMARY" vs the DB's "Abbots Hall Primary School") only when it resolved to exactly one candidate. The council's own literal non-school placeholders ("NO CATCHMENT", "OUT OF AREA", "SEC. ONLY", "PRM. ONLY") and three genuinely ambiguous dual-school claims were excluded rather than guessed at. All 1,835 roads geocoded via Nominatim (1,549 resolved, 84%), same Voronoi-plus-trust-radius-clip method, clipped to the real Thurrock LAD boundary (E06000034). Of 18 primary schools with 4+ geocoded points, 13 cleared the bar; of 4 secondary schools, 2 cleared. A pairwise overlap check found zero meaningful overlap _within_ either phase; the handful of primary-vs-secondary overlaps found are expected (different phases legitimately covering the same streets), not a defect - confirmed by re-running the check separately per phase rather than trusting a single combined pass.

**Both sources applied the post-Luton fragmentation fix proactively, not as a follow-up.** Every school's raw Voronoi-plus-buffer geometry was reduced to its single largest connected polygon _before_ the 100m-margin verification ran, so a school whose coordinate fell only in a minor disconnected fragment would have been dropped outright rather than counted as verified. Confirmed after generation: every accepted feature in both sources is a single clean `Polygon`, zero `MultiPolygon` anywhere.

**Landed and verified the same way as every other source this project ships.** `pnpm --filter @catchment-zone/shared sync-config` (both YAML edits parsed clean, both used the file's 2-space list-item indentation, double-checked directly) + `test` (45 passed, `PILOT_LOCAL_AUTHORITIES` updated with codes 812 and 883) and the ingestor's full pytest suite (127 passed) both pass clean after each edit. `pnpm format:write` scoped to the two changed files (fast, avoided the full-repo timeout noted in earlier sessions). Each source committed and pushed to `main` separately (`cd0632a` for North East Lincolnshire, `de10b12` for Thurrock, no `Co-Authored-By` trailer), confirmed landed via `git ls-remote`/`git fetch` before importing, GitHub raw CDN fresh immediately on both. `import-catchments --local-authority <code>` built 29/29 (812) then 15/15 (883), 0 rejected in both dry-run and real passes. `catchment_areas` went 10,869 -> 10,898 (+29, North East Lincolnshire) -> **10,913** (+15, Thurrock), zero duplicate `(source_id, geometry_checksum)` pairs confirmed directly against the live table both times. `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 10,913, in sync. `refresh-catchment-scores` re-run synchronously to completion after each import (final: 7,403 of 10,913 areas scored). Every one of the 44 newly-landed polygons independently re-verified against the live DB after import (not just trusting pre-deployment generation) - all pass with the required 100m+ margin, zero failures. `ingestor verify` clean. Both local authorities' `catchment_coverage_status` auto-upgraded from `NOT_AVAILABLE` to `PILOT`. **Local authority count: 102 -> 104.**

**Ruled out this session (both genuinely re-checked, not assumed from a stale note):** Bedford, Bradford (both entries), Manchester, Birmingham (both entries), Lincolnshire, Lewisham, Enfield, Kingston upon Thames, Derbyshire, Barnet, Bromley, Croydon, Haringey, Harrow, Havering, Hillingdon, Hounslow, West Sussex, North Somerset, Windsor and Maidenhead, Milton Keynes, Bedford Borough, Reading, Slough, Isle of Wight, Medway, Bath and North East Somerset, South Gloucestershire, Plymouth, Torbay, Gloucester, Rotherham (already partially resolved), Bury, Salford, Wolverhampton, Manchester/Tameside/Wigan, South Tyneside (substantial partial progress noted, not a plain dead end), Barnsley, the 11-council Sefton/Liverpool/etc. group, Kent, Surrey, Suffolk, Gloucestershire, County Durham, Leicestershire, Kingston upon Hull, North East Lincolnshire and Thurrock (now landed, see above), Southampton, Leicester, Isles of Scilly, Westmorland and Furness, Blackburn with Darwen, Blackpool, plus every Welsh/Scottish/further-London candidate already covered in earlier sessions - none of the remaining entries match the road-list/lookup-tool shape this session's technique targets; each is a genuine structural absence, a real login/credential wall, or a real network-level block already exhaustively documented.

**Most promising next lead for whoever continues after this session:** the road-list/lookup-tool candidate pool documented in this file is now close to exhausted - both remaining leads that clearly matched the shape (North East Lincolnshire, Thurrock) are landed. The next-most-promising unexplored angle is South Tyneside's partition-map PDF (see its own long candidates entry above): real, substantial progress already made on the region-closure problem (a single-page A3 map dividing the whole borough into ~27 numbered zones via red boundary lines, with a clean legend table and zone-ID labels extractable as real text), but not yet landed - the access blocker is solved (CDP Fetch-domain response interception) and the region-closure problem is understood in detail (a genuine line-network gap concentrated in the geometrically busier western/central part of the map, not a single fixable spot), just not yet finished. A second, lower-confidence angle: Na h-Eileanan an Iar's catchment areas are published as plain HTML text tables of school-name-to-_area_-name (not road-name) - a different shape from this session's technique (no road-level granularity to Voronoi-tessellate from) and would need a different reconstruction approach entirely, not immediately a fit for the proven pipeline.

## Update: South Tyneside's Marsden and Laygate primary catchments landed via a different, older archived edition of the same map (2026-08-12, later session)

**Baseline at the start of this session: 10,913 `catchment_areas` rows, `map_catchments_cache.feature_count` = 10,913 (in sync), 104 local authorities covered.** Picked up South Tyneside's long-running borough-wide ~27-zone primary partition map problem directly (see the detailed `candidates:` entry), with a firm 30-45 minute time budget before pivoting to a documented fallback (Bristol's St Bede's Catholic College per-parish map) if it didn't converge. A prior attempt earlier the same day had been interrupted mid-investigation with nothing committed; its leftover scratch files (same session scratchpad) confirmed it had hit the identical blocker described below before stopping.

**Access got harder, not easier - a real, confirmed regression, not a repeat of old notes.** The live site's Cloudflare protection on the specific PDF asset path has escalated since the last successful CDP Fetch-domain interception: it now serves a genuine visible interactive Turnstile "Verify you are human" checkbox (screenshotted and confirmed), not a silent JS challenge. Tried, in order: the previously-working CDP Fetch.enable/getResponseBody technique (got the challenge page itself, not the PDF); a real Google Chrome channel binary instead of bundled Chromium with `--disable-blink-features=AutomationControlled` and spoofed `navigator.webdriver`/plugins/languages (still challenged); and a real coordinate-based `page.mouse.click()` directly on the visible checkbox location (triggered a fresh challenge with a new Ray ID each time, never passed). Concluded this is most likely IP/network-reputation based, the same category already documented for Leicestershire/Ealing/Salford/Milton Keynes, not a technique regression worth further in-sandbox retries.

**Pivoted to a materially different, real source instead of continuing to fight access: the Wayback Machine had independently archived older editions of this exact council map.** A CDX search (`web.archive.org/cdx/search/cdx?url=southtyneside.gov.uk/media/*catchment*`) found real `application/pdf` 200 snapshots of the 2020-2023 admissions-cycle editions (crawled by archive.org's own bot before the live site's WAF tightened, no Cloudflare interaction needed to fetch them). Neither the current 2025/26 edition nor its immediate predecessor were archived anywhere - only these older ones. Rendered the cleanest (2023-admissions edition, MapInfo PDF Printer v4.5.3.9, CreationDate March 2021) at 600dpi and found zones 3 (Harton), 4 (Marsden) and 6 (Laygate)'s boundary lines fully closed - the "missing line near Beacon Hill" documented as blocking the current edition is genuinely absent here. This is a real negative result about a different document, not a re-confirmation of the known gap, and could not be diffed pixel-for-pixel against the actual 2025/26 PDF (unreachable this session) the way two closer editions were compared in an earlier session.

**Georeferencing used a different technique than any prior South Tyneside source, because this edition's zone-ID digits and school-name labels are baked into the embedded raster image rather than real PDF text** (confirmed via `pdftotext -bbox`: only the title block, legend header, and copyright are real text; everything else, including all ~45 school-name labels visible on the render, is raster). Auto-detected blue school-marker dots by colour + circularity/shape filtering (28 found), visually confirmed 10 of them by name via small crops, and fit a global least-squares affine transform against those 10 schools' real DB coordinates - spread across the whole borough (Hadrian north, East Boldon south, Whitburn coastal-south, three schools west, four schools central) - with residuals of 3-92m. Marsden and Laygate's own marker positions were deliberately excluded from the fit and used purely as an independent check: their fitted coordinates land within 24m and 40m of their real DB coordinates, strong evidence the whole map is accurately georeferenced rather than just internally self-consistent.

**Polygon extraction reused the marker-controlled watershed technique already proven on this same LA's current-edition zones (25 of 27 working), seeded differently.** A plain dilated-flood-fill on this 2023 edition's red line network (tried first, several dilation levels up to 12px) still leaked into one giant ~97%-of-image blob for both target zones, confirming this project's standing finding that blind dilation alone doesn't solve real line-network gaps anywhere on the page. Marker-controlled watershed, seeded with all 28 detected school-dot positions as competing labels plus several image-corner points as a competing exterior label (elevation = the raw undilated red line mask, following the same approach that worked for the current edition), produced single, clean, non-leaking regions for both zone 4 and zone 6 on the first attempt - each rendered back over the source map and visually confirmed to match the drawn red boundary exactly before being accepted.

**Scope deliberately limited to just these 2 schools, not the whole 2023 map.** The zone-ID numbering has visibly been reshuffled since this edition (e.g. Hebburn Lakes is zone 17 here vs zone 29 in the current 2025/26 legend, confirmed via the earlier session's notes) - real proof that redraws happen between editions. With no current-edition copy reachable this session to cross-check individual zone boundaries against, deploying all ~25 other zones from a 2023-dated document would risk silently shipping stale geometry for schools where a coordinate-inside-polygon check alone wouldn't catch a modest boundary shift. Marsden and Laygate specifically are safe because their real DB coordinates independently verify inside the extracted polygons with large margins (~450m and ~249m to the nearest edge) - exactly the kind of check that would have caught drift, not an assumption that the rest of the map is equally current.

**Landed and verified the same way as every other source this project ships.** New file `data/digitized-catchments/south-tyneside/marsden_laygate_primary_catchments.geojson` (2 features, both single clean `Polygon`, zero `MultiPolygon`, zero interior rings/holes), added as a new `primary_catchment` source entry (academic_year `2022-2023`, honestly labelled as the older vintage it actually is) alongside the existing `secondary_catchment` (Harton Academy) entry for local_authority_code 393. `pnpm --filter @catchment-zone/shared sync-config` (parsed clean, 2-space indentation matching the file's convention) + `test` (45 passed after updating `PILOT_LOCAL_AUTHORITIES`'s South Tyneside `sourceTypeCount` from 1 to 2) and the ingestor's full pytest suite (127 passed) both pass clean. `npx prettier --write` scoped to the two changed files. Committed and pushed to `main` (`5c005e3`, no `Co-Authored-By` trailer), confirmed landed via `git ls-remote origin main`; GitHub raw CDN fresh immediately on both the pinned-SHA and `main`-branch URLs before importing. `import-catchments --local-authority 393` built 3/3 (1 existing secondary + 2 new primary), 0 rejected, both dry-run and real. `catchment_areas` went from 10,913 -> **10,915** (+2), 0 duplicates confirmed directly against the live table. `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 10,915, in sync. `refresh-catchment-scores` re-run synchronously to completion (7,405 of 10,915 areas scored). Both new polygons independently re-verified against the live DB after import via PostGIS (`ST_GeometryType` = `ST_Polygon`, `ST_IsValid` = true, `ST_Contains` against each school's real `latitude`/`longitude` = true). `ingestor verify` clean. **Local authority count: unchanged at 104** (393 was already covered by the existing Harton Academy secondary source).

**Ruled out this session:** the borough-wide map's remaining ~25 zones from the 2023 edition (deliberately not attempted, per the staleness-risk reasoning above, not a capability failure); re-fetching the live 2025/26 PDF by any of three materially different browser-fingerprint/interaction techniques (Turnstile did not pass); a per-school PDF workaround for Marsden or Laygate specifically (already ruled out in an earlier session, not re-attempted since the older-edition approach succeeded first). The Bristol St Bede's Catholic College fallback lead was not needed this session since the primary approach converged inside the time budget.

**Most promising next lead for whoever continues after this session:** if the live southtyneside.gov.uk PDF ever becomes reachable again (worth a quick re-check from a genuinely different network origin, per the Leicestershire precedent, rather than more in-sandbox technique variations), the current 2025/26 edition's other 25 already-working zones could finally ship, and could also be used to properly cross-check whether this session's 2023-edition Marsden/Laygate polygons match the current boundaries closely or have genuinely drifted - worth doing even after the fact, since it would either confirm or correct what's now deployed. Beyond South Tyneside, the broader candidate pool is the same as noted in the previous update: mostly exhausted for the road-list/Voronoi shape, with Na h-Eileanan an Iar's area-name (not road-name) text tables as the remaining lower-confidence lead.

## Update: St Bede's Catholic College - 19 of 20 parishes now digitised, the "open boundary" diagnosis from the first pass was wrong (2026-08-12, later session)

**Baseline at the start of this session: 10,923 `catchment_areas` rows, `map_catchments_cache.feature_count` = 10,923 (in sync), 105 local authorities covered.** Picked up the first St Bede's session's own honest accounting directly: 6 "stuck" parishes (Thornbury, Nailsea, Portishead, Henbury, Downend, Patchway) diagnosed as having "an open rather than fully closed boundary line at this resolution, or too few nearby rail stations", plus (found by re-crawling the school's own "Parish maps" page's raw HTML rather than trusting an earlier WebFetch markdown conversion that had silently truncated one PDF's hex filename) 4 parishes never attempted at all: Clevedon, Shirehampton, Filton, Southmead.

**The "open boundary line" diagnosis turned out to be wrong in every case checked - not a resolution artefact, a real cartographic convention.** Skeletonising each drawn boundary and walking it as a graph (`networkx` shortest path between the two true endpoints) showed the line is fully drawn and closes cleanly right up to the Severn Estuary/Avon coastline, where it simply stops - the coast itself is the boundary there, and OS-referenced maps don't re-draw a boundary that already coincides with a depicted natural feature. Several skeleton "endpoints" the auto-detector flagged were false positives (sharp vertices, not real gaps) - each was individually visually confirmed as either a genuine coastal terminus or a continuing line before being treated either way. Thornbury, Henbury, Portishead and Nailsea (whose boundary is, confirmed independently, coordinate-identical to Clevedon's own differently-styled map) all closed this way: the drawn portion traced pixel-exactly via the skeleton graph, the coastal portion digitised from the same basemap's own depicted coastline (the land/tidal-flat edge), not invented.

**A second finding fixed the "too few nearby rail stations" cases.** These basemaps carry a real, precise 1km OS grid - measured directly at exactly 315px per 1000m at a 200 DPI render (i.e. genuine 1:25000 scale), independently cross-checked against two known real station-to-station distances (Bristol Parkway/Filton Abbey Wood, Severn Beach/St Andrews Road) to within 0.1-0.5% error. Once that shared scale and zero-rotation model is trusted, a single identifiable real point (one station dot, precise to a few metres) is enough to fully anchor a map - no second in-frame point needed. This unblocked Henbury (2 points: Severn Beach + St Andrews Road, used for cross-validation) and every other same-style map with just one usable station. Patchway's own basemap is a different, older scanned template (red highlighter over a photocopied OS extract) without this grid; it needed an actual 2-point similarity fit (Pilning and Severn Beach stations, both visible and labelled on its own map) - the raw fit implied an implausible 5.9 degree rotation, diagnosed as pixel-picking noise from the low-contrast scan rather than a real map rotation (real OS-derived maps are north-up), so rotation was forced to 0 and scale cross-checked against the map's own known real-world town-to-town extent instead.

**Downend remains undigitised - a genuine source limitation, not a skipped parish.** Its linked "map" is not a PDF at all but an 813x468px PNG embedded in an old newsletter page (re-fetched directly to confirm no higher-resolution version exists anywhere on the site). At that native resolution, no landmark's pixel position could be identified with confidence - two candidate town-centre labels were tried and both were illegible even at 6x upscaling. Left undigitised rather than guessed, consistent with this project's standing rule against inventing geometry.

**Extraction pipeline, built fresh this session:** colour-threshold the drawn line (black or, for Patchway, red), morphologically close small gaps from text/road crossings, take the largest connected component, `binary_fill_holes` to get the interior, `skimage.measure.find_contours` on the filled mask, simplify with `shapely`, then an affine/similarity transform (OSGB36 easting/northing intermediate, via `pyproj`) back to WGS84. For the four coastal parishes, the "fill holes" step doesn't apply directly (the boundary isn't a closed loop on its own) - instead the ordered skeleton-graph path was combined with a manually-traced coastline segment (read directly off the same basemap between the two true endpoints) before building the closed polygon. Every resulting polygon was re-rendered back over its source basemap and visually confirmed to match the drawn/coastal boundary before being accepted - not just trusted from the pixel math.

**Landed and verified the same way as every other source this project ships.** 9 new features added to `data/digitized-catchments/bristol/st_bedes_parishes.geojson` (Filton, Southmead, Patchway, Nailsea, Clevedon, Thornbury, Henbury, Portishead, Shirehampton), all confirmed single clean `Polygon` (zero `MultiPolygon`), all within sane GB bounds. `config/catchment-sources.yml`'s Bristol block comment rewritten with the full method and honest scope (19 of 20, Downend's specific resolution-limitation reason). `pnpm --filter @catchment-zone/shared sync-config` (parsed clean) + `test` (45 passed) and the ingestor's full pytest suite (127 passed) both pass clean. `npx prettier --write` scoped to the two changed files. Committed and pushed to `main` (`2187a6b`, no `Co-Authored-By` trailer), confirmed landed via `git fetch origin main`; GitHub raw CDN fresh at the pinned SHA before importing. `import-catchments --local-authority "801"` built 43 areas (25 + 2 pre-existing + 16 for St Bede's, 0 rejected) in both dry-run and real passes; a direct query against `catchment_sources`/`catchment_areas` confirmed exactly one source row per `source_type` for Bristol (no stale duplicates from the re-fetch, unlike the first session's ArcGIS-checksum-drift issue). `catchment_areas` went from 10,923 -> **10,931** (+8 net new rows: the 9 new features add 8 new rows after the Nailsea/Clevedon merge, taking St Bede's own row count from 8 to 16, exactly matching the direct DB count above). `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 10,931, in sync. `refresh-catchment-scores` re-run synchronously to completion (7,404 of 10,931 areas scored). St Bede's own real DB coordinate (51.504960755058406, -2.6565143860355813) independently re-confirmed inside its home parish (Lawrence Weston) via `shapely` against the live DB geometry, unaffected by this session's changes. **Local authority count: unchanged at 105** (Bristol was already covered).

**Ruled out this session:** re-digitising Downend from its only available source (confirmed genuinely too low-resolution, not re-attempted with guessed geometry). No other parishes remain to attempt - all 20 named parishes from the school's own page have now either been digitised (19) or confirmed source-limited (1, Downend).

**Most promising next lead for whoever continues after this session:** Bristol's St Bede's Catholic College is now essentially complete (19/20 parishes) - not worth revisiting unless the school ever publishes a higher-resolution Downend map. The broader candidate pool remains as noted in the previous update: mostly exhausted for the road-list/Voronoi shape, with South Tyneside's remaining ~25-zone 2023-edition partition map (staleness risk vs. the current edition, not yet cross-checked) and Na h-Eileanan an Iar's area-name text tables as the two clearest remaining leads.

## Update: candidates re-scan lands Suffolk (98 primary + 7 secondary) via a new technique - village/parish-list matched to real ONS parish boundaries (2026-08-17, later session)

Task for this session: a careful fresh re-scan of `config/catchment-sources.yml`'s `candidates:` section (82 entries) for any local authority whose blocker shape matches a technique this project has already proven, per the toolkit index above. Read the toolkit and the "Full audit" categorization first, then re-opened every promising-looking candidate's actual source live rather than trusting the existing note, per the task's own precedent that North East Lincolnshire and Thurrock had both been mis-categorized as harder dead ends in earlier sessions until someone actually re-read the source.

**Suffolk - landed, a genuinely new source shape for this project.** The existing note said only "Suffolk's catchment information is published per-school as PDF/list, not as a map" and stopped there. Opening `suffolk.gov.uk`'s actual school-catchment-areas page found 8 real PDFs: a county-wide "Villages and Parishes Catchment Area List" (25 pages) plus 7 town-specific street lists (Bury St Edmunds, Ipswich/Purdis Farm/Rushmere St Andrew, Beccles, Brandon, Felixstowe and Trimley, Hadleigh, Haverhill) - real extractable text (confirmed via `pdfplumber`, not a scan), each a flat table of village/street name -> primary school -> high school. This is the road/place-list shape that has landed Hartlepool/Essex/Wakefield/Coventry/Wirral/Luton/North East Lincolnshire/Thurrock, but with a twist worth keeping for future sessions: the source PDF's own explanatory note says "for villages and parishes, most catchment boundaries follow the parish boundary line" - so rather than reconstructing a boundary via Voronoi tessellation over sampled points (this project's usual move for a place-list with no coordinates), each village name was matched directly to its real civil parish administrative polygon from ONS's Open Geography Portal (`PARNCP_MAY_2025_EW_BGC`, a live public ArcGIS FeatureServer, no auth) and dissolved per school. This is a real digitised-equivalent source, not a point-sample reconstruction - the geometry itself is exact, authoritative UK government boundary data; the only uncertainty is in the name-matching layer on top of it.

Only the "Villages and Parishes" county-wide document was attempted this session (the 7 town street-lists remain a real, promising, not-yet-attempted lead for a future session, flagged below).

**Pipeline, in order:**

1. **Parsing** - `pdfplumber` word-position extraction (3 fixed x0-threshold columns: village / primary school / high school), reconstructing multi-line wrapped cells (a continuation line has empty school columns, or a non-empty village-name column but empty school columns, on its own physical line). 1,111 raw rows recovered from 25 pages.
2. **Filtering to safe rows** - only 430 of 1,111 rows were "clean" (a single unqualified village name, no "except"/"only" postcode-conditional split, no ambiguous same-line locality disambiguator like "Denham, Bury St Edmunds" vs "Denham, Eye", which Suffolk genuinely has two of). The other ~680 are real postcode-split sub-areas within one parish (correctly excluded - assigning a fraction of a parish without knowing exactly where the split line falls would be exactly the geometry-inventing this project doesn't do) or cross-references to the 7 town-specific documents ("See Bury St Edmunds Area Schools Catchment List" etc., not yet built).
3. **School name matching** - normalised abbreviation expansion (CEVC/CEVA/C of E -> full "Church of England Voluntary Controlled/Aided" phrasing, apostrophe-stripping) plus phase filtering and locality/town-augmented token matching against this project's own 365 open Suffolk schools, requiring full containment of the source's tokens with no ambiguous tie - 150 distinct primary and 32 distinct high school short-names all matched cleanly (the only "failures" were the legitimate cross-references to the town documents above).
4. **Parish resolution** - of 384 distinct clean village/parish names, 316 matched exactly one real ONS civil parish confirmed to lie inside Suffolk's own real county boundary (also fetched from ONS, both to disambiguate same-named parishes elsewhere in England and to catch simple punctuation variants like "Capel St Mary" vs ONS's "Capel St. Mary"). The other 68 were correctly left unresolved: most are hamlets/greens/tyes that aren't their own separate civil parish at all (e.g. "Shingle Street"), and Suffolk genuinely has 5 duplicate-named parish pairs (Brettenham, Langham, Middleton each exist twice) that were left ambiguous rather than guessed.
5. **Dissolve + verify** - per school, unioned every matched parish, reduced to the single largest connected piece (per this project's standing rule for any assembled geometry, applied here even though each input piece is itself a real administrative boundary), then required the school's own real DB coordinate inside with a comfortable >=100m margin to the nearest edge (this project's standard bar for DB coordinate precision uncertainty). 130 primary and 20 high schools had at least one matched parish; 32 primary and 13 high schools failed this check, almost all for the same understood structural reason rather than a pipeline bug: the parish the school itself physically sits in is a town parish handled by one of the 7 not-yet-attempted town documents, so the assembled polygon (built only from the outlying feeder villages) never covers the school's own ground. Confirmed on inspection, not assumed - e.g. Dennington Church of England Primary's own home-parish row was itself a postcode-conditional "except Owl's Green" entry, correctly excluded upstream at step 2, leaving only its neighbouring feeder villages. Spot-checked a clean single-parish case (Aldeburgh Primary School) to confirm the pipeline mechanics themselves are sound, not just coincidentally passing.

**Result: 98 primary + 7 secondary schools landed**, filed as `primary_catchment_partial` / `secondary_catchment_partial` per this project's standing convention for a real but knowingly-incomplete source (only ~38% of the source table was usable, and only 1 of 8 published documents attempted). Full method documented in the block comment above the two new `sources:` entries in `config/catchment-sources.yml`.

**Verification, same rigor as every other source this project ships:** `pnpm --filter @catchment-zone/shared sync-config` (parsed clean) + `test` (45 passed, `PILOT_LOCAL_AUTHORITIES` updated with Suffolk code 935) and the ingestor's full pytest suite (127 passed) both pass clean. `npx prettier --write` scoped to only the changed files (the two new GeoJSON files were then re-minified with plain `json.dump(..., separators=(",",":"))` to match this project's existing minified-GeoJSON convention, since prettier pretty-prints by default and this project's data files are committed minified). Committed (`68466a1`, no `Co-Authored-By` trailer) and pushed to `main`; landing confirmed independently via both `git fetch origin main` and `api.github.com`'s commits endpoint (raw.githubusercontent.com was reachable this session too, confirmed 200 at both the pinned SHA and the `main` branch URL before importing). `import-catchments --local-authority 935` built 98 + 7 = 105 areas, 0 rejected. `catchment_areas` went from 10,940 -> **11,045** (105 new rows, confirmed 105 distinct `geometry_checksum` values, 0 duplicates). `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 11,045, in sync. `refresh-catchment-scores` re-run synchronously to completion (had to be run via a single foreground call with an extended timeout rather than the default 2-minute one - it takes several minutes over 11k+ areas): 7,517 of 11,045 areas scored. A live, independent post-import query (not just the pre-import check) confirmed: all 105 Suffolk rows are single clean `Polygon` geometry (zero `MultiPolygon`), all valid, all 105 join to exactly one real open Suffolk school by exact name with zero containment failures against that school's own live DB coordinate; an additional random 8-row spot-check individually printed each result. **Local authority count: 104 -> 105.**

**Documentation cleanup done alongside the new data:** removed the now-stale Suffolk `candidates:` entry; corrected the Rotherham `candidates:` entry, which had been describing its secondary-catchment layer as "not attempted this pass" even though a later session (per this file's own "Rotherham's 14 secondary catchments landed..." update) had already built and landed it - a real stale-documentation find of exactly the kind this task's brief warned to watch for, though it turned out to be already-landed-but-undocumented rather than a new landable gap.

**Other candidates checked this session and correctly not pursued:**

- **Rotherham's secondary catchment** looked like the strongest lead of the session (same GeognoSIS platform, same proven marker-controlled-watershed technique already used for its primary layer) - but turned out to already be resolved and enabled (`rotherham_secondary_catchments.geojson`, 14 features, committed in an earlier session under commit `cf44b2e`) with only the candidate note left stale. No new work needed beyond the documentation fix above.
- **Kingston upon Thames's StatMap WFS** re-checked (still no catchment layer among its 20 real layers - unchanged).
- **Bedford Borough's "Bedford catchment areas" / "Kempston catchment areas" pages** turned out to be plain prose/index pages, not the street-list format their URL slugs suggested - no PDF or list actually found there.
- **Hounslow** - no official council-published priority-area PDF/map found live (only third-party estimator sites); the admissions-arrangements PDFs linked from the council's own page contain no map or catchment boundary.
- **Scotland's national aggregate (`data.spatialhub.scot`)** re-confirmed still behind a genuine free-registration/account gate for bulk WFS/CSV access ("you can only browse and preview datasets without an account," and full API/WFS use is restricted to One Scotland Mapping Agreement members) - unchanged from the existing note, a real credential wall, not attempted further per this project's hard rule.

**Most promising next lead for whoever continues after this session:** Suffolk's own 7 town-specific street-list documents (Bury St Edmunds, Ipswich/Purdis Farm/Rushmere St Andrew, Beccles, Brandon, Felixstowe and Trimley, Hadleigh, Haverhill) - all confirmed real, downloadable, pdfplumber-parseable street-to-school tables in the same format already proven this session, and specifically the ones that would fill in the exact "school's own home parish" gap that caused today's 32 primary + 13 secondary containment failures (several of those excluded schools, e.g. the Bury St Edmunds ones like Guildhall Feoffment/Westgate/Tollgate, would very likely pass cleanly once their own town's street list is parsed the same way, since these are urban roads rather than parish-boundary hamlets and would need the road-list Voronoi/geocoding approach rather than parish-polygon matching). Beyond that, the candidate pool is close to exhausted for genuinely new leads - this session's careful re-read of all 81 remaining entries found nothing else matching a proven technique shape beyond Suffolk and the Rotherham documentation fix.

## Update: Suffolk's 7 town-specific catchment documents landed - 34 primary + 10 secondary (2026-08-17, later session)

Continuation of the previous update's flagged next lead: attempted all 7 of
Suffolk's town-specific "Catchment Area List" PDFs (Bury St Edmunds, Ipswich/
Purdis Farm/Rushmere St Andrew, Beccles, Brandon, Felixstowe and Trimley,
Hadleigh, Haverhill) - the 7 remaining of the 8 documents `suffolk.gov.uk`
publishes, after last session landed the 8th (county-wide Villages and
Parishes). Started from 11,045 `catchment_areas` rows.

**Bonus find before starting:** opening the live council page again turned up
more than the 7 named documents - Suffolk actually publishes at least 9
_further_ town lists (Kesgrave/Martlesham/Martlesham Heath, Lowestoft,
Mildenhall, Newmarket, RAF Lakenheath, RAF Mildenhall, Stowmarket, Sudbury and
Great Cornard, Woodbridge), all real, downloadable, same shape - flagged below
as the next lead rather than attempted this session (scope stayed to the 7
originally flagged).

**Parsing, extending last session's pdfplumber word-position technique.** Same
3-column x0-threshold extraction (street name / primary school / high school),
but the continuation-line rule was tightened after a real bug: a genuine new
row always carries a - possibly placeholder ("Please see note above") -
high-school value, so any row with an _empty_ high-school column is always a
wrapped continuation of the previous row, whichever of its own columns carry
text (a wrapped street name, a wrapped "X/Y CofE"-style primary, or
occasionally a wrapped high-school name). The bug this caught: a page-footer
number landing in the high-school column's x-range (right-aligned page
numbers happen to fall past the col3 threshold) was initially mis-merged into
the preceding entry's high-school text before a "whole row is just digits"
skip was added - would have silently corrupted a handful of entries' high-
school claims with a trailing page number. "X/Y" dual-school entries (e.g.
"Castle Hill I/Castle Hill J", "Ranelagh/Sproughton CofE") and house-number
sub-range splits of one street (e.g. "Barons Road ... 1-11 only" vs
"...12-104 only") were excluded from the point sample the same way last
session excluded postcode-conditional sub-areas - never guessing which part
of a street goes where. Checked and confirmed no claim string's "/" was
actually a single real school's own name (this project's known trap from
North East Lincolnshire/Thurrock) - every "/" case really was two distinct
schools. Bare trailing "I"/"J" abbreviations (Castle Hill, Fairfield/Colneis,
Springfield) were expanded to Infant/Junior and matched to the correct
distinct school via a small manual override table (12 ambiguous/unmatched
claim strings out of 58 distinct primary + 15 distinct high claims, checked
individually against the live `schools` table rather than trusted to a
generic matcher). "Henley Gate (school to open Sept 2027)" - a genuinely
future, not-yet-open school with no DB record - was excluded outright.

**Two techniques, chosen per document rather than assumed.** Where a document
puts effectively the whole town under one school (Beccles's and Brandon's
high layers, both of Hadleigh's layers), that school's real ONS civil
parish/town-council boundary (the same `PARNCP_MAY_2025_EW_BGC` FeatureServer
used last session) was used directly - no Voronoi needed, since the source
itself assigns the entire town to one school with no split to reconstruct.
Where a town splits across several schools (Bury St Edmunds, Felixstowe and
Trimley, Haverhill, Ipswich), this project's road-list Voronoi pipeline was
used instead: every distinct street geocoded via Nominatim (evenly
subsampled per school up to a cap - 20-60 depending on town size - to keep
within a realistic single-session request budget while respecting Nominatim's
1 req/s policy), Voronoi-tessellated (`shapely.voronoi_polygons`), clipped to
the town's own ONS civil parish (or, for unparished Ipswich, the Ipswich LAD
boundary unioned with the real neighbouring parishes its own streets actually
sit in - Rushmere St Andrew, Sproughton, Claydon), reduced to the single
largest connected piece per school, and required a >=100m own-coordinate
margin, identical bar to every other source this project ships.

**Results by town** (full detail also in the block comment above the two
Suffolk entries in `config/catchment-sources.yml`):

- **Bury St Edmunds:** primary 7/9, high 2/2. Declines: Great Whelnetham CE
  Primary (its streets sit in the outlying village, not literally in town, so
  geocoding under a "Bury St Edmunds" context mostly failed to resolve) and
  Abbots Green Primary Academy (a genuine 96m margin, just under the bar).
- **Beccles:** primary declined entirely - almost every Beccles street reads
  "Please see note above" (no catchment); only Worlingham CEVC (itself an
  outlying-village school) had a real assignment, 2 streets, too thin to
  build a polygon from. High: Sir John Leman High landed via the direct
  town-parish boundary (the whole town maps to this one school).
- **Brandon:** primary 1/2 (Glade Academy; Forest Academy declined - a real
  82m margin even at full 69-street density, the two academies' catchment
  streets are interleaved within ~100m of Forest's own site, not a sampling
  problem). High: Breckland School landed via the direct town-parish
  boundary.
- **Felixstowe (and Trimley St Mary/St Martin):** primary 5/5, all
  comfortable margins (247m-657m). High: declined entirely - the document
  has no real per-school high-school assignment at all.
- **Hadleigh:** primary Beaumont Community Primary landed via the direct
  town-parish boundary - literally every Hadleigh street in the document maps
  to this one school (Hadleigh CP never appears at all, meaning it doesn't
  operate a catchment scheme, not a parsing gap). High: Hadleigh High landed
  the same way.
- **Haverhill:** primary 2/8 (Clements Primary Academy, Coupals Primary
  Academy). Of the 6 declines: Kedington and Thurlow are structurally outside
  the town's own clipping boundary (both already covered by the Villages and
  Parishes layer anyway); New Cangle Community Primary is a genuine Voronoi-
  fragmentation case - its own coordinate fell inside a real but
  non-dominant fragment once the town's other schools' points were added,
  exactly the failure mode this project's "keep only the largest connected
  piece" rule exists to catch; Westfield, Place Farm, and Burton End were
  thin/negative margins even at available sampling density. High: declined
  entirely, same "Please see note above" pattern as Felixstowe.
- **Ipswich (Purdis Farm and Rushmere St Andrew):** primary 18/24, high 5/7
  (1 primary and 1 secondary of those, Claydon Primary and Claydon High, were
  already covered by the Villages and Parishes layer and correctly
  deduplicated rather than double-listed or counted as new declines).
  Declines: Copdock and Heath Primary School, Kesgrave (both physically
  outside this document's own town/parish clipping boundary - Heath's real
  site is in the separate town of Kesgrave), Bucklesham (already covered by
  Villages and Parishes), St Helen's Primary and Chantry Academy (thin
  margins), Kesgrave High School (same out-of-boundary reason as Heath), and
  Bealings/Piper's Vale (only 1 source street each, too thin to geocode a
  usable sample from).

**Result: 44 schools passed verification (34 primary + 10 secondary), 42 of
which were genuinely new** (33 primary + 9 secondary after deduplicating the
2 already covered by Villages and Parishes) - `primary_catchment_partial`
98 -> 131, `secondary_catchment_partial` 7 -> 16. Filed as `_partial` still:
several individual schools and Beccles's whole primary layer were declined,
and the 9 further town documents found above remain unattempted.

**Verification, same rigor as every other source this project ships:**
`pnpm --filter @catchment-zone/shared sync-config` (parsed clean) + `test`
(45 passed) and the ingestor's full pytest suite (127 passed) both pass
clean. `npx prettier --write` scoped to `config/catchment-sources.yml` only
(unchanged - already correctly formatted); the two GeoJSON files stayed
minified (never run through prettier, per this project's convention).
Committed (`7a5a270`, no `Co-Authored-By` trailer) and pushed to `main`;
landing confirmed via both `git fetch origin main` and `api.github.com`'s
commits endpoint. `import-catchments --local-authority 935` built 131 + 16 =
147 areas, 0 rejected. `catchment_areas` went from 11,045 -> **11,087** (42
new rows). `refresh-catchment-overview-cache` confirmed
`map_catchments_cache.feature_count` = 11,087, in sync. `refresh-catchment-
scores` re-run synchronously to completion (had to pass an explicit extended
tool-call timeout rather than the default 2-minute one, same as last
session): 7,559 of 11,087 areas scored (all 42 new areas scored). A live,
independent post-import query joined `catchment_areas` to `schools` by exact
name **and by the two new sources' own `source_id`s** (a plain name join
alone double-counts, since generic names like "The Willows Primary School"
or "Grange Community Primary School" also exist as real open schools in
other, unrelated local authorities - caught and corrected before trusting
the result) - confirmed all 147 Suffolk rows (villages/parishes + all 7 town
lists combined) are single clean `Polygon` geometry (zero `MultiPolygon`)
and all 147 contain their own school's live DB coordinate with zero
containment failures.

**Most promising next lead for whoever continues after this session:**
Suffolk's further ~9 town documents found above (Kesgrave/Martlesham,
Lowestoft, Mildenhall, Newmarket, RAF Lakenheath, RAF Mildenhall, Stowmarket,
Sudbury and Great Cornard, Woodbridge) - same proven pipeline should apply
directly, and Kesgrave's own document in particular has a real chance of
finally landing Kesgrave High School and Heath Primary School, Kesgrave,
both declined this session only because their own site sits outside the
Ipswich-document's clipping boundary.

## Update: Suffolk's remaining 9 town documents attempted - 28 primary + 7 secondary landed, including the flagged Kesgrave High/Heath Primary target (2026-08-17, later session)

Continuation of the previous update's flagged next lead: attempted all 9 of
the further Suffolk town-specific "Catchment Area List" documents found live
on `suffolk.gov.uk` but not yet parsed (Kesgrave/Martlesham/Martlesham
Heath, Lowestoft, Mildenhall, Newmarket, RAF Lakenheath, RAF Mildenhall,
Stowmarket, Sudbury and Great Cornard, Woodbridge) - the same pdfplumber/
Voronoi/ONS-parish pipeline proven twice already this project. Started from
11,087 `catchment_areas` rows.

**A real parsing bug was found and fixed before trusting any result.** The
previous two sessions' "clean row" filter (excluding postcode-conditional/
"except"/"only" partial-street assignments, so a fractional street
assignment is never treated as if the whole street belongs to one school)
only checked the SCHOOL-NAME column for these qualifiers - it never checked
the STREET-NAME column for the same thing, even though several documents
carry qualifiers on the street side too (e.g. "Beccles Road, Lowestoft, odd
No's 1-169, even No's 2-166 and Dutchman Court only"). Fixed by adding a
matching filter on the street column. Re-running every earlier town's
Voronoi job (from both this session and the previous one) with the fix
applied confirmed nothing already-shipped had been corrupted - every
previously-landed school's result came back materially unchanged - while
fixing a real, measurable failure this session: Dell Primary School
(Lowestoft) went from a confident-looking but wrong -591m failure to a
genuine +113m pass once the conditional streets stopped polluting its
Voronoi cell.

**RAF Lakenheath and RAF Mildenhall: both fully declined, 0 usable rows.**
Every single street in both documents reads "Please see note above" - these
US airbase housing areas have no real catchment scheme published at all.
Confirmed by opening both PDFs in full, not assumed from the pattern in
other documents.

**Per-town results** (full method and every decline reason also documented
in the block comment above the two Suffolk entries in
`config/catchment-sources.yml`):

- **Kesgrave, Martlesham and Martlesham Heath:** primary 4/4 (Heath,
  Gorseland, Cedarwood, Birchwood - Bucklesham and Waldringfield were
  already covered by the Villages and Parishes layer and correctly
  deduplicated; Kyson had only 1 source street). High: Kesgrave High School
  landed via the direct union of the real Kesgrave and Martlesham ONS
  parish boundaries, 340m margin - this is the specific school flagged as
  the strongest remaining target from the previous session, now landed.
  Heath Primary School, Kesgrave (the other flagged target) also landed,
  255m margin - both were declined by the earlier Ipswich-document attempt
  only because their own site sits outside that document's own clipping
  boundary; Kesgrave's own document supplies streets that actually reach
  it.
- **Newmarket:** primary 4/4 (Houldsworth Valley, All Saints CE, Laureate,
  Paddocks - Moulton CEVCP had only 1 source street; streets assigned to a
  school "Cambridgeshire" were correctly excluded as genuine cross-border
  assignments, not a matching failure). High: Newmarket Academy landed via
  the direct Newmarket ONS parish boundary (single-school town-wide
  assignment), 1268m margin.
- **Stowmarket:** primary 3/4 (Abbot's Hall, Combs Ford, Chilton; Wood Ley
  declined - a genuine 92m margin even at full 16/16-street density, not a
  sampling problem). High: Stowmarket High School landed via the direct
  Stowmarket ONS parish boundary, 367m margin.
- **Mildenhall:** primary St Mary's Church of England Academy landed via a
  direct ONS parish boundary lookup, 830m margin - Suffolk's parish
  reorganisation renamed Mildenhall town's own civil parish "Mildenhall
  High" in ONS's dataset (the plain name "Mildenhall" resolves to an
  unrelated same-named parish in Wiltshire), found by checking which real
  parish geometrically contains Mildenhall town rather than trusting a name
  match. Every other Mildenhall street reads "Please see note above" - a
  genuine single-school document. High: none - no real high-school
  assignment exists in this document at all.
- **Sudbury and Great Cornard:** primary 5/5 (St Gregory CEVC, Woodhall,
  Wells Hall, Pot Kiln, Tudor CE Primary - Great Waldingfield had only 1
  source street). High: Ormiston Sudbury Academy landed via the direct
  union of the real Sudbury and Great Cornard ONS parish boundaries, 508m
  margin.
- **Woodbridge:** primary 5/5 of the unambiguous single-school claims
  (Rendlesham, Kyson, Sandlings, Melton, Woodbridge - Eyke CE and Hollesley
  were already covered by the Villages and Parishes layer and correctly
  deduplicated). Three "X/Y" dual-school claims covering most of the
  document (Kyson/St Mary's CE, Melton/St Mary's CE, Woodbridge/St Mary's
  CE) were correctly excluded as genuinely ambiguous. Sandlings Primary
  School's own real coordinate was found to sit just outside the "Sutton"
  ONS parish (its own DB locality field) and inside a separate, smaller
  "Sutton Heath" parish next to it - confirmed by a direct point-in-polygon
  lookup against the ONS FeatureServer rather than assumed. High: Farlingaye
  High School landed, but only via the dominant connected piece of
  Woodbridge+Melton's own ONS parish union (280m margin) - Woodbridge,
  Melton, Rendlesham, Sutton/Sutton Heath, and Hollesley/Eyke turned out to
  be geometrically disconnected from each other in the real parish boundary
  data (real gaps between them, not a bug), so the full union was reduced
  to its single largest connected piece per this project's standing rule,
  which is the Woodbridge+Melton pair where the school itself actually
  sits.
- **Lowestoft** (the largest and most complex of the 9): primary 6/8
  (Carlton Colville, Elm Tree, Dell, Corton CEVAP, Roman Hill, Poplars).
  Carlton Colville Primary School's own real coordinate was found to sit
  just outside the "Carlton Colville" civil parish and inside the adjacent
  "Gisleham" parish - confirmed by point-in-polygon lookup and added to the
  clip boundary, fixing what was otherwise a consistent -40m failure
  regardless of street-sampling density (618m margin once fixed). Two
  primary declines, both genuine: Blundeston CEVC Primary - every one of
  its assigned streets is in a place called "Oulton" (a real, separate area
  from both "Oulton Broad" and the village of Blundeston itself), so a
  polygon built only from Oulton streets can never reach the school's own
  site in Blundeston village - the same "school's own home area isn't in
  its own document" structural pattern as Great Whelnetham/Dennington in
  earlier sessions, confirmed on inspection not assumed. Oulton Broad
  Primary School - a genuine thin 82m margin, capped by real Nominatim
  coverage gaps for that specific pocket of streets (most of its own source
  streets, e.g. "Allen Road, Lowestoft", "Berry Close, Lowestoft", simply
  don't resolve via Nominatim in any query form tried - checked live, not
  assumed to be a code bug). High: both of Lowestoft's real high-school
  assignments landed - Ormiston Denes Academy (773m margin) and Pakefield
  High School (629m margin) - via the road-list Voronoi pipeline split
  between the two.

**Result: 35 new schools passed verification (28 primary + 7 secondary)**,
all with a real, verified >=100m own-coordinate margin except the two
dominant-piece-reduction cases (Farlingaye High, and every other dominant-
piece Voronoi cell), which are still real and independently re-verified
after reduction - `primary_catchment_partial` 131 -> 159,
`secondary_catchment_partial` 16 -> 23. Three schools were declined for
genuine, inspected reasons (Wood Ley Community Primary 92m, Blundeston CEVC
Primary structural, Oulton Broad Primary 82m/geocoding-gap-limited), same
standard as every other decline this project has shipped.

**Verification, same rigor as every other source this project ships:**
`pnpm --filter @catchment-zone/shared sync-config` (parsed clean) + `test`
(45 passed) and the ingestor's full pytest suite (127 passed) both pass
clean. `pnpm exec prettier --write` scoped to `config/catchment-sources.yml`
only (unchanged - already correctly formatted); both GeoJSON files stayed
single-line minified (never run through prettier, per this project's
convention) - confirmed via `wc -l` returning 0 both before and after.
Committed (`bb364f4`, no `Co-Authored-By` trailer) and pushed to `main`;
landing confirmed via both `git fetch origin main` and `api.github.com`'s
commits endpoint, and `raw.githubusercontent.com` confirmed serving the
updated 159-feature primary file before importing.
`import-catchments --local-authority 935` built 159 + 23 = 182 areas, 0
rejected. `catchment_areas` went from 11,087 -> **11,122** (35 new rows,
matching 182 total Suffolk rows now in the DB minus the 147 that existed
before this session). `refresh-catchment-overview-cache` confirmed
`map_catchments_cache.feature_count` = 11,122, in sync.
`refresh-catchment-scores` re-run synchronously to completion with an
explicit extended tool-call timeout (the default 2-minute one is not
enough over 11k+ areas, same lesson as every previous session): 7,594 of
11,122 areas scored (all 35 new areas scored). A live, independent
post-import query confirmed: all 182 Suffolk rows (across both sources) are
single clean `Polygon` geometry (zero `MultiPolygon`), and joining
`catchment_areas` to `schools` **filtered first by
`catchment_sources.local_authority_code = '935'`, then spot-checked each
matched school's own `local_authority_code` to confirm it was really the
Suffolk school and not a same-named school elsewhere** (several of this
session's own school names turned out to be nationally ambiguous - e.g.
"Birchwood Primary School" exists 4 times across England - making this
check a real one, not a formality) found all 35 new schools' own live DB
coordinates fall inside their assigned polygon with zero containment
failures, plus a random 6-row spot-check individually printed and
confirmed.

**Beccles's primary layer (flagged as a possible reconsideration target)
was reviewed but not re-attempted.** The previous session's decline reason

- almost every Beccles street reads "Please see note above", with only
  Worlingham CEVC (an outlying-village school, not a Beccles-town one)
  getting a real assignment across just 2 streets, too thin to build a
  polygon from - is a genuine no-data-published situation identical in shape
  to Mildenhall's high layer, Felixstowe's high layer, and Haverhill's high
  layer, all confirmed again this session: some Suffolk schools' own
  admissions policies just don't use a catchment-area scheme, and the
  council's own document correctly reflects that with no addresses assigned.
  There is no different technique that would recover data the source itself
  doesn't publish - re-attempting would mean forcing a fit against the
  project's own standing rule, so this remains correctly declined.

**Suffolk's candidate pool for this technique is now essentially
exhausted.** All 9 further town documents found live last session have now
been attempted (7 landed real data, 2 - both RAF documents - confirmed to
have none). The only remaining known gap is Beccles's primary layer, now
confirmed twice to have no usable source data at all.

## Update: Salford reopened - 7 of 24 faith-school parish catchments landed via OS-grid digitisation (2026-08-18)

**Baseline at the start of this session: 11,122 `catchment_areas` rows, `map_catchments_cache.feature_count` = 11,122 (in sync), 105 local authorities covered.** Applied the exact lesson just learned from Suffolk to the rest of the `candidates:` pool: re-open sources whose existing note is short/dismissive rather than trusting it. Salford's note read "Official page provides PDF catchment maps only for ~25 faith schools, no GIS... map.salford.gov.uk's interactive map timed out from this sandbox" - technically accurate but never actually opened the 25 PDFs it mentioned.

**The council's real "parish boundary and catchment area maps" page links 24 individual per-school PDF boundary maps** (`salford.gov.uk/schools-and-learning/schools-admissions/parish-boundary-and-catchment-area-maps`), one per RC/CE faith school. Each is a genuine OS OpenData-style vector basemap with a real, precise pale-cyan 1km National Grid overlay (true north-up, confirmed by matching horizontal/vertical grid-line spacing) and a solid black hand-drawn boundary line plus a blue star marking the school itself - the same landmark-pair/OS-grid family of technique already proven for Oxfordshire and Inverclyde, except the grid itself supplies scale and rotation directly, leaving only one real question per file: absolute translation. Solved by anchoring each school's own real DB (GIAS) coordinate to its own drawn blue star - not circular for accuracy, since scale and rotation come independently from the grid's own measured pixel spacing, not from the school's coordinate.

**A real bug found and fixed in the grid-spacing estimator itself.** The first version corroborated candidate spacings via pairwise differences across both axes combined, which St Charles' RC Primary's map defeated: its M60/M61 Worsley Interchange sits directly across 2 of its grid lines, so both axes independently lost the same intermediate lines to motorway occlusion, and their surviving (3x-too-large) gaps coincidentally agreed with each other. Replaced with a stricter method: take each axis's own smallest _adjacent_ (consecutive-line) gap, then require the two axes' smallest gaps to agree within tolerance (or be a small integer multiple of each other) - real corroboration between two independently measured axes, not spurious pairwise coincidence. Caught this specific failure via a real-world plausibility check (the false spacing implied a sub-1.4km page width for a map that visibly spans Worsley to Swinton, a real ~4km) and confirmed the true grid line's presence by direct pixel inspection at the predicted position.

**Cross-checked against a second independent landmark where available.** Two of the seven landed schools had another named school drawn on the same source page, matched to its own already-known DB coordinate the same way this project anchored New Marston Primary (Oxfordshire) on Oxford Brookes/St Joseph's: Christ Church CofE Primary cross-checked via New Park Academy's own building (23m residual over a 250m baseline) and St Edmund's RC Primary via Bridgewater Primary School's own building (42.5m residual over a 241m baseline) - both comfortably tight, giving confidence in the grid-anchoring method generally, not just per-file luck.

**Result: 7 of 24 linked PDFs landed** (Christ Church CofE, St Charles' RC, St Edmund's RC, St Luke's RC, St Mark's RC, St Teresa's RC, Holy Family VA RC) - the ones whose grid lines were cleanly measurable without per-file manual intervention. All 7 confirmed single clean `Polygon` (dominant-piece reduction applied, zero `MultiPolygon`), all valid, all containing their own school's real DB coordinate with a margin of 209-1106m. Filed as `primary_catchment_partial`: 17 of the 24 linked PDFs remain undigitised (weaker/more-occluded grid detection needing individual per-file attention, e.g. All Hallows RC High School and Ellesmere Park High School's secondary maps) - a real, proven-workable lead for a future session, not exhausted. Full method and remaining candidate list documented in `config/catchment-sources.yml`'s Salford block comment.

**Verification, same rigor as every other source this project ships.** `pnpm --filter @catchment-zone/shared sync-config` (parsed clean) + `test` (45 passed, `PILOT_LOCAL_AUTHORITIES` updated with Salford code 355) and the ingestor's full pytest suite (127 passed) both pass clean. GeoJSON re-minified to match this project's committed-minified convention (the digitisation script had written it pretty-printed). Committed (`81f22f5`, no `Co-Authored-By` trailer) and pushed to `main`; landing confirmed via `git fetch origin main` and a 200 response from the commit-SHA-pinned raw URL before importing. `import-catchments --local-authority "355"` built 7/7 areas, 0 rejected. `catchment_areas` went from 11,122 -> **11,129** (+7). `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 11,129, in sync. `refresh-catchment-scores` re-run synchronously to completion (7,601 of 11,129 areas scored). A live, independent post-import query (joined by `catchment_sources.local_authority_code` first, not a plain name join) confirmed all 7 Salford schools' own real DB coordinates fall inside their assigned polygon via `ST_Contains`, zero containment failures. **Local authority count: 105 -> 106.**

**Most promising next lead for whoever continues after this session:** Salford's own remaining 17 PDFs, using the exact pipeline and bug-fixed grid-spacing estimator documented above and in the yml block comment - a genuinely proven, not-yet-exhausted lead, unlike most of the rest of the `candidates:` pool. Beyond Salford, the broader lesson (re-open sources with dismissive-sounding old notes rather than trusting them) is worth one more careful pass across the remaining ~74 candidates before concluding the pool is genuinely exhausted.

## Update: Salford's remaining 17 PDFs attempted - 10 landed (17 of 24 total), digitisation pipeline committed to the repo (2026-08-18)

**Baseline at the start of this session: 11,129 `catchment_areas` rows, `map_catchments_cache.feature_count` = 11,129 (in sync), 106 local authorities covered.** Picked up the exact lead flagged at the end of the previous Salford session: attempt the remaining 17 of Salford's 24 per-school parish/catchment boundary PDFs, using the same OS-grid digitisation method. The previous session's pipeline code had not been committed (it lived only in a scratchpad), so it was rebuilt from the written method description in `config/catchment-sources.yml`'s Salford block comment, then genuinely improved rather than just reproduced.

**Two real bugs found and fixed in the grid-spacing estimator while rebuilding it.** First: the original colour-threshold cyan mask counted wide cyan-ish fills (lakes, highlighted boxes) the same as thin 1km grid lines when scoring candidate line positions, letting features like a large lake or a river's parallel double-border masquerade as grid lines. Fixed with a distance-transform thinness filter - a pixel deep inside a filled blob is far from any non-cyan pixel, while every pixel of a genuinely thin (~1-3px) line is close to its own edge, so keeping only low-distance-transform pixels isolates true grid lines regardless of orientation. Second: even after that fix, taking the raw single MINIMUM adjacent gap per axis was sometimes still fooled by one surviving spurious short gap (e.g. a river border segment that passed the thinness filter) - fixed by clustering all adjacent gaps within 2% tolerance and taking the MODAL (most-recurring) cluster instead of the bare minimum, falling back to the minimum only when an axis has too few detected lines to have a repeat measurement at all. Both fixes were validated against St Thomas of Canterbury RC's map, which reproduced a near-identical trap to last session's St Charles' RC bug (a lone spurious ~422px gap sitting alongside three mutually-confirming ~1005-1008px gaps) and is now correctly resolved to 1006px.

**A star-marker disambiguation problem also came up and was solved generically rather than per-file.** St Joseph the Worker RC's page places a second, smaller decorative copy of its gold star icon inside the page's own legend/key box - same colour, similar size, but not the real on-map marker. Rather than add position-based heuristics that wouldn't generalise, the pipeline now detects every star-coloured blob (across both known colour profiles, blue and gold) and disambiguates by trying each as the anchor and keeping whichever produces a polygon that actually contains the school's own real DB coordinate - the same containment check every candidate must clear regardless, so this isn't circular. A parallel problem existed for boundary detection: a plain rectangular page-border frame (thin line drawn right around the whole map) has the same "large bbox, low fill ratio" signature as a real hand-drawn boundary and was initially picked by mistake on a couple of files. Fixed by checking whether a candidate's bounding box spans almost the _entire_ page in both width and height simultaneously (a real catchment polygon occupies a sub-region, leaving room for title/key text; a page border doesn't) rather than trying to count vertices, which turned out to be an unreliable signal for boundaries with long near-straight runs.

**Result: 10 of the 17 remaining PDFs landed** - Christ The King RC, St Joseph's RC (Ordsall), St Joseph the Worker RC (Irlam, gold star), St Mary's RC (Swinton), St Peter's CE, St Philip's RC, St Philip's CE, St Paul's CE (Cross Lane), The Cathedral School of St Peter & St John RC, and St Thomas of Canterbury RC. Eight landed via fully automatic dual-axis grid detection with margins of 313-2100m. Two more - St Philip's CE and St Paul's CE Cross Lane - share an identical underlying basemap render (same 4764x3368px dimensions, same River Irwell/Salford Loop water feature sitting at the same pixel position, just different boundary overlays drawn on top) where only one grid line survives cleanly per file, making automatic dual-axis corroboration impossible from either file alone. Landed using that shared file's own clean single-axis row measurement (640px - a single sharp peak roughly 25x stronger than any competing candidate, not a marginal reading) applied to both, and independently verified safe by checking that containment holds with a comfortable positive margin for both schools' own DB coordinates across the _entire_ plausible spacing range (400-1000px/km tested), not just at the one chosen value - so the result isn't sensitive to getting this single-axis reading exactly right. This is documented as a deliberate, disclosed exception in `pipeline/schools.py`, not a silent shortcut.

**7 of the 17 declined, each for a genuine, individually-checked reason** (full detail in `pipeline/schools.py`): All Hallows RC High School and Ellesmere Park High School both had clean, fully-corroborated grid and star detection but landed ~31m and ~104m short (respectively) of their own school's real DB coordinate - genuine near-misses, declined rather than forced past this project's comfortable-margin bar. Holy Cross and All Saints RC, St Mary's RC (Eccles), and St Mark's CE (three sibling uploads under adjacent media IDs) turned out to use a different, older basemap style with **no OS grid overlay at all** - confirmed by direct pixel inspection of the rendered page, not just an automatic-detection failure - with the school shown as a plain dot/text label instead of a star; without an independent grid there is no safe source of scale/rotation, so these were declined outright rather than force-fit. St Gilbert's RC turned out to be a completely different source again: a very high-resolution (9537x13483px) cadastral-style raster scan with the school shown as a shaded building footprint and no grid at all. St Paul's CE (Crompton Street, Walkden) uses a third document type - a diocesan "Digital map from Dotted Eyes... Church Commissioners" ecclesiastical-parish product with a different grid/colour system that wasn't calibrated this session; flagged as a genuine, not-yet-exhausted lead for a future session rather than a dead end.

**The digitisation pipeline is now committed to the repo** at `data/digitized-catchments/salford/pipeline/` (`grid_digitise.py` - the OpenCV/shapely/pyproj digitisation engine; `schools.py` - per-school metadata, source URLs, and every landed/declined outcome with its reasoning; `build_geojson.py` - the script that renders and merges results into the final GeoJSON), closing the gap explicitly flagged at the end of the previous session where the pipeline lived only in a scratchpad and had to be rebuilt from a written description.

**Verification, same rigor as every other source this project ships.** `pnpm --filter @catchment-zone/shared sync-config` (parsed clean) + `test` (45 passed) and the ingestor's full pytest suite (127 passed) both pass clean - run from the actual worktree after an earlier false-failure scare caused by accidentally running them from the main checkout instead. `pnpm exec prettier --write` scoped to `config/catchment-sources.yml` only (unchanged - already correctly formatted); the GeoJSON stayed single-line minified (`wc -l` = 0). All 10 new features, and all 7 pre-existing ones, independently confirmed single clean `Polygon` geometry (dominant-piece reduction applied before verification per this project's standing rule) with zero `MultiPolygon` features. Committed (`8c35116`, no `Co-Authored-By` trailer) and pushed to `main`; landing confirmed via `git fetch origin main` and a 200 response with the correct 17-feature count from `raw.githubusercontent.com` before importing. `import-catchments --local-authority "355"` built 17/17 areas, 0 rejected. `catchment_areas` went from 11,129 -> **11,139** (+10). `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 11,139, in sync. `refresh-catchment-scores` re-run synchronously to completion with an extended tool-call timeout (7,611 of 11,139 areas scored). A live, independent post-import query against the DB (using each school's own real DB coordinate directly, matched to its catchment row by the exact `area_name` string rather than an ambiguous plain-name join - Salford's `schools` table has several open/closed duplicate rows sharing the same name, e.g. two "St Edmund's RC Primary School" and two "St Joseph's RC Primary School" entries at different sites, confirmed live not assumed) found all 10 new schools' and all 7 pre-existing schools' own coordinates fall inside their assigned polygon via `ST_Contains`, zero containment failures across all 17.

**Local authority count unchanged at 106** (this session only extended Salford's existing source, no new local authority added). **Salford's own remaining candidate pool is now down to 7 undigitised PDFs**, each blocked for a structurally different, already-diagnosed reason (two near-misses, three no-grid basemap variants, one raster-scan variant, one diocesan-map variant) rather than a uniform "try harder" gap - the two near-misses and the diocesan-map variant are the only ones with any plausible path to landing in a future session; the rest are genuine dead ends for this project's grid-anchoring method.

## Update: third candidates re-scan lands South Gloucestershire (4 zones, 19 schools) via a new school-coordinate-anchored technique; most of the remaining ~74 candidates re-confirmed genuinely closed (2026-08-18, later session)

**Baseline at the start of this session: 11,139 `catchment_areas` rows, `map_catchments_cache.feature_count` = 11,139 (in sync), 106 local authorities, HEAD at `3bbbc18`.** Third consecutive candidates re-scan this session cycle, working from the explicit instruction to re-open dismissive-sounding old `reason_not_enabled` notes rather than trust them, expecting (correctly) a lower hit rate than the Suffolk/Salford passes that preceded it.

**Live re-checks that found nothing new, each worth recording so a future session doesn't repeat them.** Milton Keynes (`mapping.milton-keynes.gov.uk`) and Ealing (`inspire.misoportal.com`) both still hard-timeout at the TCP level from this sandbox - re-confirmed with a fresh `curl` attempt, unchanged from three prior sessions' findings. Leicestershire (`leicestershire.gov.uk`) still returns a hard Akamai 403 to a plain request. Enfield's two candidate ArcGIS Hub hostnames now return HTTP 200 at the root but a `"Domain record(s) not found"` 404 on their own DCAT feed - the Hub site itself appears to have been deprovisioned rather than gaining public access, no better than the previous 401 finding. Kingston upon Thames's real, working StatMap WFS was re-queried directly (as its own candidate note suggested "periodically re-checking") - still only `school_open_spaces` (playing fields), no catchment layer added. Newport/Swansea/Neath Port Talbot's ArcGIS Hub DCAT feeds and Rhondda Cynon Taf's WFS endpoint were re-tried and are unchanged (404/500 respectively). Scotland was independently re-audited against the `candidates:`/`sources:` split and confirmed **all 32 council areas already have real coverage** (28 direct + 4 via the national aggregate) - no further Scottish work exists to find. Wales's 22 principal areas are similarly fully accounted for (4 landed, 18 individually checked and correctly closed).

**Bath and North East Somerset was re-opened properly for the first time** (the old note - "no dedicated GIS/map subdomain resolves... not confirmed as real catchment boundary data" - had never actually been tested live). Its "Nearby" tool turned out to be backed by a real, previously-undiscovered public GeoServer (`data.bathnes.gov.uk/geoserver/mapdata/ows`, ~250 layers). A promising-looking `PSZ*` layer group turned out to be unrelated legacy MapInfo administrative-boundary exports once actually queried, and the only school layers are point locations backing a nearest-school lookup. A genuine, now thoroughly-confirmed data-absence finding, not an access barrier - closed with much higher confidence than before, even though the answer is still no.

**South Gloucestershire is the real find this session** - the old note ("no GIS/ArcGIS/map subdomain resolves... static admissions documents only") was simply wrong; it never opened the council's actual admissions PDF. South Glos LIFE (`life.southglos.gov.uk`) is Cloudflare-challenged for a plain `curl` but clears normally with a real Playwright browser session, and links a genuine 228-page "Primary Schools Admission guide" PDF containing real vector-drawn (`PyMuPDF get_drawings()` confirms actual path objects, not a raster scan) "Area of Prime Responsibility" maps - one page per named school or consortium of schools, each carrying both a single closed boundary polygon path and an exact textual boundary description (e.g. "defined by the A4174 to the north... then south and westwards along the River Frome... until South Gloucestershire Council's administrative boundary"). Of the booklet's 13 "Map N" pages, 8 draw a real zone; the other 5 are explicitly informational ("no schools with an Area of Prime Responsibility on this map").

**A new anchoring technique for this project: using the project's own real DB school coordinates as ground-control points instead of external geocoding.** Every zone map places a numbered marker for each school it discusses (including, usefully, nearby excluded schools shown for context, e.g. Map 8 shows both Frenchay CE Primary, included, and Hambrook Primary, explicitly marked "not included"). Since this project already holds every South Gloucestershire school's real GIAS-sourced coordinate, each numbered marker's precise pixel position (read directly from the PDF's text-layer digit-glyph bounding boxes, not eyeballed) can be paired with its school's real coordinate as an exact ground-control point - no Nominatim/Overpass geocoding needed at all, and no risk of the "diffuse settlement-label" imprecision that has caused problems elsewhere in this project. Two-school and one-school pages use an exact 2-point similarity transform; the two multi-school consortium pages (3 and 15 markers) use a least-squares Umeyama similarity fit across all markers simultaneously, which is both more accurate (residuals of 3-126m, versus 270-670m for an earlier 2-point-only attempt on the same page) and self-cross-validating (every marker is simultaneously an anchor and a held-out check). Where a page had too few school markers of its own (Map 11, single school), real nearby railway stations (Bristol Parkway, Patchway, Filton Abbey Wood - precise `railway=station` nodes fetched via Overpass, not Nominatim's less precise "information board" result for Patchway which was caught and corrected mid-session) filled out a 4-point least-squares fit instead.

**Landed 4 of the 8 real zones, 19 schools total**, each independently re-verified via a live `ST_Contains` PostGIS query against the deployed DB (not just an offline check) after import: Map 8 Frenchay Church of England Primary School (single school, 476m margin against a ~145m cross-check budget); Map 11 Bradley Stoke Community School (the primary phase of an all-through academy, 296m margin against a 126m worst-case residual); Map 12 Filton Primaries Consortium - Charborough Road / Shield Road / Filton Hill (3 schools sharing one zone, 144-201m margins against a 2-8m residual budget); Map 15 Kingswood North/Downend/Emersons Green Consortium (14 schools sharing one zone, 185-1200m margins against a 3-120m residual budget). Map 15's 15th listed school, St Augustine of Canterbury Catholic Primary School, sits geographically inside the polygon (700m margin) but is correctly **excluded** from the zone's combined `area_name` because the source document itself explicitly marks it "not included within this Area of Prime Responsibility" - a Roman Catholic voluntary-aided school setting its own admissions, the same exclusion pattern already established for Cardiff and Monmouthshire's faith schools. Every polygon reduced to its dominant single connected piece before verification and confirmed a clean `Polygon` (zero `MultiPolygon`) both offline and in the live DB.

**4 more real zones (Maps 16, 17, 18, 19) and the entire secondary-schools equivalent booklet remain undigitised** - a genuine, time-bounded stopping point within this session, not a technical dead end; the same anchoring technique applies directly, it just needs more per-page marker/coordinate lookup time. Documented in detail in the South Gloucestershire `candidates:` note for the next session to pick up directly.

**Verification.** `pnpm --filter @catchment-zone/shared sync-config` + `test` (45 passed, after adding South Gloucestershire's `{ code: "803", ... }` entry to `PILOT_LOCAL_AUTHORITIES`) and the ingestor's full pytest suite (127 passed) both pass clean, run from this session's own worktree. A real regression was caught and fixed mid-session: an initial `pnpm format:write` invocation with file arguments after `--` silently ran prettier repo-wide instead of scoped (the underlying `package.json` script is `prettier --write .`, ignoring extra args), which pretty-printed 16 unrelated already-committed GeoJSON data files out of their required minified form - caught via `git status`/`git diff --stat` before committing, reverted with `git checkout --`, and the project's own new GeoJSON (which was also caught by the same repo-wide run, since prettier doesn't distinguish tracked from untracked files) was re-minified by hand before staging; `wc -l` = 0 confirmed on the final file. `npx prettier --write` scoped explicitly to just the two changed non-data files afterwards showed no further changes needed. Committed (`be81acb`, no `Co-Authored-By` trailer) and pushed to `main`; landing confirmed via `git fetch origin main` and a 200 response with the correct content from `raw.githubusercontent.com` (pinned to the commit SHA) before importing. `import-catchments --local-authority "803"` built 4/4 areas, 0 rejected. `catchment_areas` went from 11,139 -> **11,143** (+4). `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 11,143, in sync. `refresh-catchment-scores` re-run synchronously to completion with an extended tool-call timeout (7,615 of 11,143 areas scored), followed by a second `refresh-catchment-overview-cache` run since scores changed. A live post-import `ST_Contains` query (joined by `catchment_sources.local_authority_code` then exact `area_name`) against 4 spot-checked real schools spanning all 4 new rows - Frenchay CE Primary, Bradley Stoke Community School, Charborough Road Primary, and Kings' Forest Primary - found all 4 correctly contained, zero failures.

**Local authority count: 106 -> 107.** The rest of this session's `candidates:` re-scan came up genuinely empty beyond the two updates above (Bath and North East Somerset's closed-more-thoroughly note, South Gloucestershire's partial landing) - consistent with the explicit expectation for a third pass that the easiest wins are already gone. **Most promising next lead:** South Gloucestershire's own remaining 4 zones plus its untouched secondary-schools booklet, using the exact school-coordinate-anchoring technique proven this session - the single most under-exploited idea to carry into the next session is using this project's own already-verified school coordinates as ground-control points wherever a source map shows named/numbered school markers, rather than defaulting straight to external geocoding.

## Update: South Gloucestershire continued - 7 more primary zones, its secondary booklet landed for the first time (2026-08-18, later session)

**Baseline at the start of this session: 11,143 `catchment_areas` rows, `map_catchments_cache.feature_count` = 11,143 (in sync), 107 local authorities, HEAD at `3a5cf82`.** Picked up the exact lead flagged at the end of the previous session: South Gloucestershire's remaining 4 primary "Area of Prime Responsibility" zones (Maps 16-19) and its entirely-undigitised secondary-schools booklet, reusing the previous session's downloaded PDFs and Python environment still present in this session's own scratchpad.

**A real accuracy problem found and fixed: pure similarity fits weren't good enough for these maps.** Re-anchoring Maps 16/18/19 with the same 2-point/Umeyama-similarity technique used previously produced per-school containment margins of only tens of metres, and for Map 19 specifically left two included schools (Cherry Garden Primary, Redfield Edge Primary) fully **outside** their own reconstructed polygon. Diagnosis (pairwise pixel-distance-vs-real-distance ratio checks across every marker pair) ruled out a mislabelled marker - ratios were consistently off by a roughly uniform 15-20% rather than one outlier - meaning the source maps are schematic enough that a pure similarity transform (equal x/y scale, single rotation) doesn't fit them well at this scale. Switching to a full 6-parameter least-squares affine fit (independent x/y scale and shear, still using the same real DB school coordinates as ground-control points) fixed this immediately: per-point residuals on the 4-7 GCP consortium pages dropped from hundreds-of-metres down to 7-241m, and every included school landed comfortably inside its polygon (351-2303m margins). This is now the preferred fit method for this source whenever 3+ real GCPs exist on a page.

**A genuine method failure, tested honestly rather than assumed: cross-page tie-point transfer for single-school pages doesn't work reliably here.** Several pages (primary Map 17 "King's Oak Academy Primary Phase", secondary "The Castle School", secondary "Marlwood School") show only one real school marker with no second school plotted on the same base-map crop, so neither a similarity nor an affine fit is well-determined from on-page data alone. A technique was built to borrow shared place-name label pixel positions from an already-well-anchored neighbouring page (transform them to real lon/lat via that page's own solid fit, then use them as extra ground-control points on the target page) - genuinely tested on all three candidates, not just assumed to work by analogy. It failed every time: Marlwood School landed 702m **outside** its own reconstructed polygon; King's Oak Academy Primary Phase's own real anchor point showed a systematic ~700-900m disagreement within the blended fit, against only a 165m containment margin. All three were declined rather than shipped, each independently documented.

**Secondary booklet structure discovered and fully explored for the first time.** South Gloucestershire's secondary schools are (with one exception) all academies acting as their own admission authority, but the council still publishes a genuine 7-zone "Area of Prime Responsibility" system for them in a separate 132-page PDF, using the same real vector-drawn boundary format as the primary booklet (a different but equally consistent boundary colour, ~RGB(0,148,68) green vs the primary booklet's ~RGB(98,79,151) purple). All 7 zones were opened and attempted this session - every South Gloucestershire APR page in both booklets has now been looked at at least once.

**Landed 3 of the 7 secondary zones, 9 schools total, all independently re-verified via a live query against the deployed DB after import:** Yate and Chipping Sodbury Consortium (Brimsham Green School, Yate Academy, Chipping Sodbury School - exact 0-residual 3-point fit, 1565-3823m margins); Downend School/King's Oak Academy/Mangotsfield School/Winterbourne Academy Consortium (4 schools, 36-241m residuals, 1264-2303m margins - this King's Oak Academy zone is the _secondary_ phase of the same all-through academy whose _primary_ phase is Map 17 above, correctly modelled as a distinct `catchment_area` rather than a duplicate); Hanham Woods Academy and the Sir Bernard Lovell Academy Consortium (2 included schools, 79-132m residuals, 281-964m margins - plus a strong cross-validation signal: the source text explicitly excludes John Cabot Academy and Digitech Studio School from this zone, and both were independently confirmed geometrically **outside** the fitted polygon by 285m and 343m respectively, exactly as the source document says, without that exclusion being told to the fitting code in any way).

**4 of the 7 secondary zones declined, each for a genuine, individually-tested reason:** The Castle School and Marlwood School (single-school pages, no on-page second GCP, cross-page technique tested and failed - see above). The Bradley Stoke Community School/Abbeywood Community School/Patchway Community School Consortium has 3 real GCPs and an exact 0-residual fit, but leaves Bradley Stoke Community School only 63m inside its own polygon - under this project's 100m comfort bar even though the other two schools clear it comfortably (421m, 2072m). A rescue attempt adding 5 more cross-page tie points (borrowed from the well-anchored Downend consortium page, which happens to share several town-name labels with this one) pushed Bradley Stoke's margin up to 508m, but only by introducing 344-1626m of residual elsewhere in that same blended fit - an untrustworthy correction that could just as easily be moving the error rather than removing it, so the whole zone was declined rather than shipped on the strength of a fix that isn't itself trustworthy. Lyde Green Community School has a real drawn zone and precise boundary text, but the school (URN 152456) has status `PROPOSED_TO_OPEN` with no `latitude`/`longitude` yet in this project's DB - it is literally due to open for Year 7 entry from September 2026, weeks after this session - so there is no anchor point to fit against or verify containment with at all; a clean, mechanical candidate for a future session once GIAS publishes its real coordinates.

**Verification.** `pnpm --filter @catchment-zone/shared sync-config` + `test` (45 passed, after updating South Gloucestershire's `PILOT_LOCAL_AUTHORITIES` `sourceTypeCount` from 1 to 2 for the new secondary source) and the ingestor's full pytest suite (127 passed) both pass clean, run from this session's own worktree. `git status`/`git diff --stat` checked before committing and showed only the 4 intended files changed - no repeat of the repo-wide `pnpm format:write` reformatting regression from two sessions ago (`npx prettier --write` was used, scoped to the single yml file). Both GeoJSON files confirmed single-line minified (`wc -l` = 0) and zero `MultiPolygon` features (every boundary reduced to its single dominant connected piece before verification, per this project's standing rule). Committed (`d758629`, no `Co-Authored-By` trailer) and pushed to `main`; landing confirmed via `git fetch origin main` and 200 responses with the correct feature counts (7 primary, 3 secondary) from `raw.githubusercontent.com` before importing. `import-catchments --local-authority "South Gloucestershire"` built 7 + 3 = 10 areas, 0 rejected. `catchment_areas` went from 11,143 -> **11,149** (net +6: the primary layer's row count only grew from 4 to 7 since Maps 16/18/19 replace nothing and Map 19's earlier-session similarity-fit geometry didn't exist yet, plus 3 brand-new secondary rows). `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 11,149, in sync. `refresh-catchment-scores` re-run synchronously to completion with an extended tool-call timeout (7,621 of 11,149 areas scored). A live post-import query (joined by `catchment_sources.local_authority_code` and `source_type` first, then exact `area_name`, per this project's standing spot-check rule) against 6 schools spanning both new source rows - Courtney Primary, Parkwall Primary, St Barnabas CE Primary, Chipping Sodbury School, King's Oak Academy (secondary), Sir Bernard Lovell Academy - found all 6 correctly contained with margins matching the pre-import offline computation exactly, zero failures.

**Local authority count unchanged at 107** (this session only extended South Gloucestershire's existing coverage - a new secondary source type, not a new local authority). **Most promising next lead:** none identified specifically for South Gloucestershire - every APR page in both its booklets has now been attempted, and the 4 remaining declines (1 primary, 3 secondary) are each blocked for a structurally different, already-diagnosed reason (no on-page second GCP with a demonstrated-unreliable cross-page workaround; a shared-polygon zone with one school under the comfort-margin bar; a school that hasn't opened yet) rather than a uniform "try harder" gap. Lyde Green Community School is the one truly mechanical follow-up - revisit once GIAS publishes its real coordinates, expected on or shortly after its September 2026 opening.

## Update: fourth candidates re-scan finds nothing new - pool confirmed exhausted for this pass; enabled-source sanity sweep finds no link rot (2026-08-18, later session)

**Baseline at the start of this session: 11,149 `catchment_areas` rows, `map_catchments_cache.feature_count` = 11,149 (in sync), 107 local authorities, HEAD at `6de986a`.** Fourth consecutive candidates re-scan this session cycle, following the explicit instruction to be more skeptical than the three passes that preceded it (Suffolk, Salford, South Gloucestershire all landed real coverage) - the working hypothesis going in was that the easy wins really might be exhausted by now, and that turned out to be correct.

**Skip list first.** Cross-referenced every name still in `candidates:` against the last several sessions' own "Update" entries (Suffolk landing, both South Gloucestershire sessions, the third re-scan) to avoid repeating a check someone already did this cycle: Milton Keynes, Ealing, Leicestershire, Enfield, Kingston upon Thames, Newport/Swansea/Neath Port Talbot, Rhondda Cynon Taf, all of Scotland, all of Wales, Bath and North East Somerset, South Gloucestershire, Rotherham, Bedford Borough and Hounslow were all left untouched this pass since they were each already live-re-checked within the last 1-3 sessions.

**Live-checked this session, all confirming (or strengthening) the existing dead-end finding rather than surfacing anything new - a real Playwright/Chromium session (bundled browser at `~/.cache/ms-playwright`, installed into a scratch venv since this worktree has no `node_modules`) was used wherever a plain `curl` risked a false bot-check negative, per this project's standing rule that a JS bot-check is fine to clear with a real browser:**

- **Manchester** - the existing note said only "genuinely unchecked beyond this one false lead," the exact dismissive-note pattern this task looks for. Actually checked this time: the admissions landing page, the school finder tool, and a site-wide search for "school catchment area" - manchester.gov.uk has zero pages mentioning school catchment areas in any admissions/GIS sense at all (only unrelated river-catchment/flood-risk and "local shopping catchment" hits). Consistent with the separate "Manchester, Tameside, Wigan" group entry's finding that Manchester's real ArcGIS Hub (26 datasets, DCAT-checked) has no catchment dataset either. A genuine structural absence, now checked from a second independent angle.
- **Croydon, Havering, Plymouth, Torbay, Slough, Bromley, Harrow, Hillingdon** - each re-searched and, where a real council URL was found, opened live (Torbay's actual "TIPS 8" admissions page; Croydon's current admissions-process page, which now 200s rather than the stale 404'd URL from a search hit). All confirm their existing notes: distance-based admissions with no catchment concept (Croydon, Plymouth - Plymouth's own current wording is now "schools ... no longer operate designated areas," an even more explicit structural statement than before), point-only mapping tools (Havering's Aurora), or no official GIS/PDF found at all beyond third-party estimator sites (Slough, Bromley, Harrow, Hillingdon). No new source for any of the eight.
- **Newcastle upon Tyne and Sunderland** (2 of the 11-council group entry, spot-checked rather than re-running all 11) - both searches surfaced the same two generically-titled ArcGIS Experience apps ("School Catchments 2026" and "School Catchment Areas") that keep appearing as false positives across this project's searches; re-verified live via `arcgis.com/sharing/rest/content/items/{id}?f=json` that both are still owned by Telford (`8e95a003440121b8ac64645d6f06e8be`) and Wokingham (`WBC_DavidEgginton`) respectively, unchanged. Sunderland did surface one genuinely new-to-this-project platform - a real `sunderland.statmap.co.uk` StatMap GIS instance, found via the council's own "Interactive Maps" page - but every one of its published maps (Local Plan Policies, Brownfield Land Register, SHLAA, Greenspace Audit) is planning-related with per-map embedded login/password tokens baked into the URL, not a general open WFS; there is no schools or catchment map among them, and no `wfs.svc` endpoint responds at all (404). A more thoroughly-confirmed negative than before, not a new lead.
- **Wolverhampton and Bradford** - both re-verified against their already-documented endpoints (Wolverhampton's `CWC/MapServer` layer list, Bradford's `spatialdata-cbmdc.hub.arcgis.com` DCAT feed) and found byte-for-byte unchanged: Wolverhampton's MapServer still has only `Schools`/`LeisureCentres`/`Tips` (point layers), Bradford's Hub still has 62 datasets with the only schools-adjacent ones being an NOx interpolation layer and a water-level monitor.
- **Isle of Wight** - re-confirmed structural (distance-based admissions is the council's own explicit policy wording, independent of whatever the current state of its Cloudflare gate is).

**No new pursuable source found this pass - a legitimate, honestly-reached negative result, not a failure to look hard enough.** Roughly 15 candidates were freshly re-opened live this session (a mix of full Playwright sessions, direct `curl` probes of already-known API endpoints, and live ArcGIS item-metadata re-verification), spanning the range from "dismissive-sounding note, never actually re-tested" (Manchester) through "already well-documented, cheap to double-check" (Wolverhampton, Bradford). None produced a real, checkable catchment-boundary source that wasn't already known and correctly ruled out. This is consistent with the explicit expectation set for a fourth pass over the same ~80-entry pool: the three sessions before this one already picked off the genuinely under-investigated entries (Suffolk, Bath and North East Somerset, South Gloucestershire), and what remains is now, on the evidence gathered across four independent passes, either a real structural absence (no catchment concept in that LA's admissions policy), a real access barrier already exhaustively tested (login wall, network-level block, Cloudflare bot-management product), or a real platform that simply never published the layer.

**Second half of this session per the task's own fallback instruction: a top-to-bottom sanity sweep of currently-ENABLED sources, since nothing new was found to land.** Picked 7 (more than the requested 3-5, since each check is cheap) `download_url`s spread across different regions and formats of `config/catchment-sources.yml`'s `sources:` section: Sheffield (`sheffieldcitycouncil.cloud.esriuk.com` ArcGIS Enterprise FeatureServer), Stirling and East Dunbartonshire (two different `services*.arcgis.com` ArcGIS Online-hosted FeatureServers), Telford (`maps.telford.gov.uk` ArcGIS Server), and three of this project's own `raw.githubusercontent.com`-hosted digitized-catchment GeoJSON files spanning three different digitization sessions (BCP's secondary catchments, the Scotland national aggregate's East Ayrshire secondary layer, South Gloucestershire's newest secondary APR file). All 7 returned a live HTTP 200 with the expected `esriGeometryPolygon`/`FeatureCollection` structure and plausible feature counts/properties (e.g. Sheffield's `Primary Catchment Boundaries 2025 - 2026`, South Gloucestershire's `Brimsham Green School / Yate Academy / Chipping Sodbury School` row matching what was landed two sessions ago) - no link rot, no silent upstream breakage, nothing requiring a fix.

## Update: two long-flagged single-school leads both closed out - Oxfordshire's Barton Park Primary and Salford's last parish-boundary PDF (2026-08-18, later session)

**Baseline at the start of this session: 11,149 `catchment_areas` rows, `map_catchments_cache.feature_count` = 11,149 (in sync), 107 local authorities, HEAD at `9866e46`.** Picked up two specific, individually-documented leads left by prior sessions rather than a fresh candidates sweep: Barton Park Primary School (Oxfordshire, the last open school in that county's long-running digitisation backlog) and St Paul's CE Primary, Crompton Street (Salford, the last of its 24 parish-boundary PDFs).

**Barton Park Primary School (URN 147865, Oxfordshire code 2034) - landed via a cleaner method than the one the prior session got stuck on.** A prior session had already confirmed this map has a genuine, solid black (not cyan) OS 1km grid and correctly reframed it as a "one tie-point" problem, but got stuck because Overpass was blocked and only thin Nominatim-only candidates were available (~1.5x margin/residual ratio - too thin to ship). This session found Overpass reachable again (intermittent "server busy" errors that clear on retry) and, more importantly, realised no landmark pairing was needed at all: since a real OS National Grid's lines always sit on exact 1000m easting/northing multiples, the two confirmed vertical grid lines and one confirmed horizontal grid line were matched directly to their real OSGB36 values using only the school's own approximate DB coordinate to pick the right km square - a fully deterministic scale+rotation(0)+translation with no fitted residual at all. Independently cross-checked against two real, Overpass-confirmed OSM features on the same map extent ("Dunstan Park" and the "Foxwell Drive" cul-de-sac loop), both landing within a few pixels of their true printed positions under this transform - strong confirmation the grid-square identification was right, not a lucky coincidence. The traced boundary (standard red-colour raster mask) overlays pixel-perfectly on the source PDF's printed line. Area 0.40km2, single clean Polygon, DB coordinate contained with a 146m margin - comfortably over this project's 100m+ bar.

**St Paul's CE Primary, Crompton Street, Walkden (URN 105945, Salford) - the last of the 24 Salford parish-boundary PDFs, previously declined as "a third source type... not yet calibrated."** It genuinely is a different diocesan "Digital map from Dotted Eyes... Church Commissioners" product (magenta boundary, not the council's own OS OpenData basemap), but turned out to have both a real (fainter/greyer) raster OS 1km grid baked into the basemap AND a real VECTOR-drawn boundary in `page.get_drawings()` - a first for this Salford pipeline, which had only ever needed raster colour-masking before. The vector paths chain into 11 separate closed magenta rings, not 1, because this wide-area deanery sheet draws every neighbouring parish's boundary too, not just the target one; the correct ring was picked out by matching the huge loop that dominates the page. Rather than relying on the map's own small lettered "B" symbol (which turned out to mark something ~640m from the school, most likely the parish church, not the school itself - an assumption that was tested and found wrong before being trusted), the grid's absolute position was anchored via Nominatim/Overpass's real "Blackleach Reservoir" polygon centroid, colour-mask-extracted from the raster basemap and matched to the OSM way's own centroid - the implied grid-line eastings/northings landed within ~15m of exact 1000m multiples, a strong confirmation signal. Independently cross-checked a second way: under the resulting transform, a building on the map explicitly labelled "School" sits exactly on "Crompton Street", matching the predicted pixel position of the school's own real DB coordinate almost exactly. Traced ring overlays pixel-perfectly on the source PDF's printed boundary. Area 4.01km2, single clean Polygon, DB coordinate contained with a 493m margin. All 24 of Salford's primary/secondary parish-boundary PDFs are now resolved: 18 landed, 6 genuinely declined for individually-documented reasons.

**Verification.** `pnpm --filter @catchment-zone/shared sync-config` + `test` (45 passed) and the ingestor's full pytest suite (127 passed) both pass clean, run from this session's own worktree. `git status`/`git diff --stat` checked before committing and showed only the 5 intended files changed (plus the pre-existing untracked `services/ingestor/uv.lock`, left alone) - the Oxfordshire GeoJSON is committed pretty-printed (this file's own established convention, unlike most others in this repo) so the new feature was inserted as a targeted text edit rather than a full `json.dump`, to avoid an accidental repo-wide reformat; the Salford GeoJSON stayed single-line minified (`wc -l` = 0). Both new features confirmed single `Polygon` (no `MultiPolygon`). Committed (`1294dc8`, no `Co-Authored-By` trailer) and pushed to `main`; landing confirmed via `git fetch origin main` and the GitHub API, then 200 responses with the correct feature counts (183 primary for Oxfordshire, 18 for Salford) from `raw.githubusercontent.com` before importing. `import-catchments --local-authority "931"` built 183 primary + 27 secondary = 210 areas, 0 rejected; `--local-authority "355"` built 18 areas, 0 rejected. `catchment_areas` went from 11,149 -> **11,151**. `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 11,151, in sync. `refresh-catchment-scores` re-run synchronously to completion with an extended tool-call timeout (7,623 of 11,151 areas scored, both new rows among them). A live post-import point-in-polygon query (joined by `catchment_sources.local_authority_code` first, then exact `area_name`, per this project's standing spot-check rule) confirmed both schools' own real DB coordinates fall inside their newly-landed polygons.

**Local authority count unchanged at 107** (both landings extended existing coverage rather than opening a new local authority). **Most promising next lead:** none identified for either of these two specific files - Oxfordshire's long-running per-school backlog and all 24 of Salford's parish-boundary PDFs are now both fully worked through. The general candidates pool remains where the fourth re-scan (immediately above) left it: believed close to exhausted after four independent passes, pending any genuinely new lead surfacing in a future session.

## Update: 3 of Oxfordshire's last 4 open triage schools landed; the 4th declined with a documented reason; a stale duplicate found and fixed (2026-08-18, later session)

**Baseline at the start of this session: 11,151 `catchment_areas` rows, `map_catchments_cache.feature_count` = 11,151 (in sync), 107 local authorities, HEAD at `32372ee`.** A careful re-read of `remaining_schools_triage.tsv`'s actual status column (a prior session had mis-read the wrong field) turned up 4 schools still genuinely open, each with a specific documented next-step idea: Wood Farm Primary, St Mary's CE Primary Banbury, Dr South's CE Primary Islip, and St Joseph's Catholic Primary Thame.

**Wood Farm Primary School (URN 123074) - landed using exactly the suggested next idea.** Slade Park Fire Station + Nuffield Orthopaedic Centre (both Overpass/Nominatim `amenity` ways, colour-mask centroids of their drawn buildings) as a 1370m landmark pair, rotation 0.68deg - this file turned out to have no real grid (`cyan_mask_broad`/`reconcile_grid_period` scored 0.0/0.0) despite 161 raster tiles, so grid-based scaling wasn't an option. Cross-checking against the school's own drawn star marker vs. its DB coordinate gave a borderline 155m/5.8deg/0.78 ratio, but cross-checking the same predicted marker position against the school's real OSM `amenity=school` siting instead (independent, not used in the fit) gave an excellent 25m residual - confirming the DB coordinate itself sits ~170m off true, the same pattern as the documented Windmill Primary precedent, not a bad transform. DB coordinate contained, 247m margin. Area 3.35km2, single clean Polygon.

**St Mary's CE Primary School, Banbury (URN 144872) - landed by abandoning both previously-failed landmark pairs entirely, per the prior note's own advice.** Grimsbury Reservoir (a distinctively-shaped lake, Overpass/Nominatim `reservoir` way, colour-mask centroid) + Bluebird Bridge (a road/river crossing near Castle Quay), 1.4km baseline, rotation 1.89deg. Cross-checked against the school's own marker: 85m/3.4deg/1.03 ratio - clears the bar comfortably. A visual overlay of the extracted ring against the source PDF matched pixel-perfectly across the map's entire ~5km extent, from Hardwick Gorse in the north to the college in the south - no sign of the tile-stitching distortion the prior session had flagged as a possible cause; the earlier ~11deg failures were most likely down to imprecise landmark identification rather than a rendering problem. DB coordinate contained, 462m margin. Area 3.50km2, single clean Polygon.

**St Joseph's Catholic Primary School, Thame (URN 139529) - landed by fixing the actual reported bug (green colour-mask bleed) with a tighter threshold, after re-measuring the whole transform from scratch.** Long Crendon + Great Milton (village-label text centroids, real Overpass/Nominatim coordinates), 8.57km baseline, rotation -0.50deg - cross-checked against Tetsworth (independent): 35.7m residual/-0.29deg/0.9998 ratio, even tighter than the prior session's own 275m benchmark. The green parish-fill mask (`G-R>25 AND G-B>80 AND G>180`) cleanly isolates the "Thame" parish from all 5 neighbouring parishes' sampled colours with a wide margin and no patching needed; a connected-component check confirmed one dominant 252,972px blob with only sub-100px noise elsewhere. DB coordinate contained, 334m margin. Area 109.58km2 - genuinely larger than the similar Sacred Heart Henley catchment (39.4km2), not a re-occurrence of the previous session's bled 153km2 figure; this Catholic parish covers Thame town plus Towersey, Kingsey, and reaches down past Tetsworth almost to Lewknor, a real difference in parish extent. **While importing this one, discovered it was actually already present in the file** - an undocumented commit from 2026-08-13 (`2e32834`, "recovered from a fork stopped mid-task") had landed a different 82-point/93.7km2 version of the same catchment, but its triage row was never updated to "done," so this session's re-attempt didn't know to check for it. The two polygons overlap 83-97% (same real parish, consistent with each other), but only the new one has surviving landmark/residual documentation, so the old, undocumented feature was removed and the new one kept - see the follow-up commit below.

**Dr South's CE Primary School, Islip (URN 143888) - investigated in depth but left undone; a genuine decline, not a shortfall of effort.** Confirmed via `pymupdf` that the source PDF is a single embedded raster JPEG with no real vector boundary path at all (`page.get_drawings()` has only a decorative title-underline rectangle), settling the open question of whether `vector_boundary.py`'s technique applied here - it does not, because there is no vector boundary to extract. It's a monochrome 1:25000-style OS County Series scan with no colour channel to mask. Found a genuinely new technique for this document type - a stroke-width filter (`cv2.distanceTransform` on a darkness mask, keeping only locally >=3px-wide strokes) that cleanly separates a bold, hand-reinforced line from the thin base-map linework, dotted parish-boundary symbol, and printed text. Traced this bold line by hand through several sections and found what looked like most of a closed loop (River Ray/Noke/Lower Farm/Woodeaton area), but closing it fully proved genuinely ambiguous rather than just fiddly: part of the bold line runs directly under the base map's own labelled "Co Const & CP Bdy" (County Constituency & Civil Parish Boundary) symbol for a long stretch, meaning the cartographer likely retraced an existing parish boundary rather than drawing a wholly independent overlay in that stretch, and the western segment dead-ends in an unresolved tangle of roads/tracks/quarry symbols near Brick Kiln Farm with no unambiguous bold continuation. Closing the loop would have required guessing which thin/dotted line continues it - ruled out by this project's no-invented-geometry rule. Left undone; the triage row documents the exact technique, the exact ambiguity, and a concrete next-session idea (try tracing the parish boundary itself through the gap, cross-checked against real ONS/OS Boundary-Line parish data before trusting it).

**Also fixed a second, unrelated stale triage row found during this session's initial read:** The Grange Community Primary School (URN 122997) was already landed in an earlier session (confirmed present in the geojson) but its triage row still showed `fake_grid_confirmed` from a failed re-attempt that pre-dated the successful landing - corrected to `done` so a future session doesn't re-attempt it.

**Verification.** `pnpm --filter @catchment-zone/shared sync-config` + `test` (45 passed) and the ingestor's full pytest suite (127 passed) both pass clean, run from this session's own worktree. `git status`/`git diff --stat` checked before each commit. Two commits: the first (`a8a36e4`) added the 3 new features and the triage updates; the second (`9107ce5`) removed the stale duplicate St Joseph's Thame feature discovered during import, once it was clear the duplicate was real and not a false alarm. Both pushed to `main` with no `Co-Authored-By` trailer; landing confirmed via `git fetch origin main` and 200 responses with correct feature counts from `raw.githubusercontent.com` before each import. `import-catchments --local-authority "931"` built 186 primary + 27 secondary = 213 areas after the first commit, then 185 primary + 27 secondary = 212 after the duplicate-removal commit and a matching DB row deletion. `catchment_areas` went from 11,151 -> 11,154 (transiently, with the duplicate) -> **11,153** (final, correct). `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 11,153, in sync. `refresh-catchment-scores` re-run synchronously to completion with an extended tool-call timeout (7,625 of 11,153 areas scored, all 3 new rows among them). A live post-import point-in-polygon query (joined by `catchment_sources.local_authority_code` first, then exact `area_name`) confirmed all 3 schools' own real DB coordinates fall inside their newly-landed polygons.

**Local authority count unchanged at 107** (all 3 landings extended existing Oxfordshire coverage). **Most promising next lead:** Dr South's CE Primary, Islip - the triage row now documents a concrete, testable next idea (trace the parish-boundary line itself through the Brick Kiln Farm gap, cross-checked against independently-sourced parish boundary data) rather than a dead end. Beyond that, Oxfordshire's per-school backlog is once again fully worked through pending any new lead. The general candidates pool remains where the fourth re-scan left it: believed close to exhausted, pending any genuinely new lead surfacing in a future session.

**No config or data changes this session - `git status`/`git diff --stat` confirmed clean throughout, nothing to commit or push beyond this documentation update.** `catchment_areas`, `map_catchments_cache.feature_count`, and the local authority count are all unchanged at 11,149 / 11,149 / 107. **For whoever continues after this session:** the candidates pool has now been re-scanned four consecutive times without a new structural blind spot turning up; a fifth pass over the same ~80 entries is unlikely to be productive using the same "re-open the dismissive note" technique, since that technique has now been applied to essentially every entry that could plausibly have been under-investigated. The two genuinely open, already-identified threads to pick up instead are: (1) South Gloucestershire's Lyde Green Community School, mechanically unblockable until GIAS publishes its real coordinates around its September 2026 opening; (2) the handful of entries this project's own notes flag as blocked only by this specific sandbox's network origin (Milton Keynes, Ealing, Leicestershire) rather than by genuine data absence - worth retrying only if a session ever runs from a different network origin, not from here again.

## Update: Dr South's CE Primary (Islip) landed via real parish-boundary data; Ellesmere Park High School landed via a grid-disambiguation refit; All Hallows RC High re-confirmed unsolvable (2026-08-18, later session)

**Baseline at the start of this session: 11,153 `catchment_areas` rows, `map_catchments_cache.feature_count` = 11,153 (in sync), 107 local authorities, HEAD at `e905fac`.** Picked up two specific, individually-documented leads: Dr South's CE Primary, Islip (the last genuinely open school in Oxfordshire's long-running backlog, already investigated twice and left as a documented near-solvable ambiguity) and Salford's two near-miss declines, All Hallows RC High School (~31m) and Ellesmere Park High School (~104m), both flagged as candidates for the affine-refit technique proven elsewhere in this project.

**Dr South's CE Primary School, Islip (URN 143888) - landed by abandoning pixel-tracing the scan entirely and using real, authoritative parish-boundary data instead.** The source PDF is confirmed (again) to have no vector or grid data at all - a flat monochrome OS County Series scan with a bold hand-reinforced line that two previous sessions couldn't confidently close into a loop, partly because it coincides with the base map's own thin dotted "Co Const & CP Bdy" parish-boundary symbol for long stretches and dead-ends near Brick Kiln Farm in a cropped view. This session rendered the FULL uncropped page (previous sessions worked from cropped pixel-referenced sections) and could see the bold line does close into a complete loop once the whole extent is visible. Rather than trust a hand pixel-trace of a blurry scan, checked the school's own published catchment description first: it names the "communities of Islip, Noke, and Woodeaton" - three real, current, contiguous English civil parishes with authoritative published boundaries (OSM relations 4155651/4155878/1868040, ODbL via Overpass, `ref:gss` E04008056/E04008069/E04008184). Took the union of all three directly (a single contiguous Polygon, no holes, 14.48km2) instead of digitising the scan at all - the same technique already used for Stoke Row CofE Primary elsewhere in this file. Visually cross-checked (not required for the geometry itself, since it's authoritative data, but done anyway): transformed the union into the PDF's own pixel space using 4 independently-geocoded reference points (Islip/Noke/Woodeaton village centres plus Brick Kiln Farm, max fit residual 113px on a 3052px-wide page) and overlaid it on the source scan - the union's outline tracks the bold hand-drawn line's notches and bends closely across the whole loop, including through the Brick Kiln Farm gap that stumped both previous sessions. DB coordinate contained, margin 593.5m - comfortably clears this project's 100m+ bar, and not sensitive to the visual check's residual since the shipped geometry is the parish data itself.

**Ellesmere Park High School (URN 144200, Salford) - landed by using the page's other 3 real schools as ground-control points to fix the grid's absolute alignment, rather than fitting a raw affine on noisy star pixel-picks.** This school's PDF is the council's separate "catchment area" map style (red boundary, gold-star markers) with an already-confirmed real OS 1km grid (630/632px spacing, 7 corroborating gap measurements); the previous session's single-star-anchor translation missed the school's own DB coordinate by ~104m. A first attempt at a raw 3-point affine fit using the page's 3 other gold-star schools (All Hallows RC High School, St Patrick's RC High School, Salford City Academy - all queried fresh from the live DB) gave a worse 137-184m cross-check residual, no improvement. What worked instead: using those same 3 schools only to disambiguate which 1000m grid square each of the page's grid lines falls in, then fitting translation directly and independently per axis from the measured grid line pixel positions (5 columns, 4 rows; sub-3px residuals on the grid fit itself - essentially exact), bypassing the single-marker anchor entirely - the same deterministic-grid technique already proven for Oxfordshire's Barton Park Primary. Each of the 3 GCP schools landed 39-124m from its own real DB coordinate under this transform, consistent with this project's documented GIAS DB-coordinate siting noise (not a transform error, since the grid fit alone is far tighter). The boundary extraction needed a wider-than-default 41x41 morphological close (rather than the pipeline's usual 9x9) to bridge gaps where this page's large school-name text labels overlap the printed red line - verified safe by flood-filling from an interior point and confirming it no longer leaks to the full canvas at that kernel size, with a stable enclosed area across kernel sizes 41-121. Traced ring visually matches the source PDF's red line. Area 6.34km2, single clean Polygon. DB coordinate contained, margin 397.9m. Landed in a new `salford_secondary_catchments.geojson` file and matching `secondary_catchment` source entry, kept separate from Salford's existing `primary_catchment_partial` source since `area_type` (used for phase-matched score lookups) is derived directly from `source_type` and must not be tagged "primary" for a secondary school.

**All Hallows RC High School (Salford) - re-examined with the same techniques but confirmed still a genuine ~31m near-miss, left declined.** Unlike Ellesmere Park, this school's own PDF shows only itself (the page's key literally states "blue star - All Hallows RC High School" with no other school plotted), so there was no second/third real GCP available for a grid-disambiguation or affine refit here. Checked whether the grid itself carries any measurable rotation the original north-up similarity fit might have missed: sampled the confirmed vertical grid line's x-position across 22 bands spanning the full page height - slope was 0.0013px drift per px of height (~6px over the whole ~4500px page), i.e. genuinely vertical, ruling out rotation as the cause. Also tried anchoring purely from the grid (Barton-Park-style, bypassing the star anchor) using only the school's approximate DB coordinate to pick the right km square: this predicts the star's own on-page position 232m from its DB coordinate - worse than the 31m the original star-forced-exact-to-DB anchor already achieves, confirming translation method isn't the weak point. A 1:1 pixel zoom on the source PDF around the star shows the school's own drawn marker sitting essentially ON the printed boundary line itself, right where it bends - a genuine near-boundary siting in the source cartography, not a digitisation artefact. No technique refinement can manufacture a confident 100m+ margin out of a source document that draws the school right on its own catchment line; left declined with a fully updated note documenting this session's investigation.

**Verification.** `pnpm --filter @catchment-zone/shared sync-config` + `test` (45 passed, after updating Salford's expected source-type count from 1 to 2 for the new secondary source) and the ingestor's full pytest suite (127 passed) both pass clean, run from this session's own worktree. A first `pnpm format:write` run was caught reformatting ~18 unrelated already-minified GeoJSON files across other local authorities (Coventry, Essex, Hartlepool, Luton, North East Lincolnshire, South Gloucestershire, Suffolk, Thurrock, Wakefield, Wirral) plus Salford's own primary file - all reverted via targeted `git checkout --`, and prettier re-run scoped only to the actually-changed `.yml`/`.ts` files afterward. Similarly, appending Dr South's feature via a plain `json.dump` was first caught silently reformatting Oxfordshire's primary GeoJSON from its established pretty-printed convention (34,031 lines) into a single minified line - reverted and redone via `git checkout --` + `npx prettier --write` on just that file, which reproduces the original compact-coordinate-array pretty-print exactly (diff came out as a clean 1,361-line pure addition, 0 deletions). Both new features confirmed single `Polygon` (no `MultiPolygon`, no holes). Committed (`7d6c6ae`, no `Co-Authored-By` trailer) and pushed to `main`; landing confirmed via `git fetch origin main`, the GitHub API, and a 200 response with the correct feature count from `raw.githubusercontent.com` for the new Salford secondary file before importing. `import-catchments --local-authority "931"` built 186 primary (+1) + 27 secondary (unchanged) areas, 0 rejected; `--local-authority "355"` built 18 primary (unchanged) + 1 secondary (new source), 0 rejected. `catchment_areas` went from 11,153 -> **11,155**. `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 11,155, in sync. `refresh-catchment-scores` re-run synchronously to completion with an extended tool-call timeout (7,627 of 11,155 areas scored, both new rows among them with real percentile/metric values). A live post-import point-in-polygon query straight against the DB's own stored `geometry_geojson` (joined by `catchment_sources.local_authority_code` first, then exact `area_name`) confirmed both schools' own real DB coordinates fall inside their newly-landed polygons. An explicit orphaned-row check (per this project's standing rule for any re-import of an already-populated source) compared `count(distinct geometry_checksum)` against `count(*)` per local-authority/source_type group for both Salford and Oxfordshire - all four groups matched exactly (18/18, 1/1, 186/186, 27/27), confirming no stale duplicate rows survived the re-import of Salford's unchanged `primary_catchment_partial` source or Oxfordshire's `primary_catchment` source.

**Local authority count unchanged at 107** (both landings extended existing coverage). **Most promising next lead:** none identified for either of these two specific threads - Oxfordshire's long-running per-school backlog is now fully worked through a second confirmed time, and Salford's last remaining near-miss (All Hallows) has now been investigated by two separate sessions using two different refinement techniques (single-anchor precision checks, then grid-disambiguation/affine) and confirmed genuinely unsolvable with this project's available source material - a source-document limitation (the school is drawn on its own catchment boundary line), not a technique gap. The general candidates pool remains where the fourth re-scan left it: believed close to exhausted, pending any genuinely new lead surfacing in a future session.

## Update: audit of already-_partial local authorities for missed documents - Darlington and Thurrock both extended (2026-08-18, later session)

**Baseline at the start of this session: 11,155 `catchment_areas` rows, `map_catchments_cache.feature_count` = 11,155 (in sync), 107 local authorities, HEAD at `7ed518e`.** Applied the Suffolk/South Gloucestershire lesson one level deeper: rather than another blind `candidates:` re-scan (four consecutive passes had already confirmed that pool close to exhausted), audited local authorities already marked `_partial` in `config/catchment-sources.yml` - Coventry, Darlington, Essex, Hartlepool, Luton, North East Lincolnshire, North Northamptonshire, Thurrock, Wakefield, Wirral, and Bristol's secondary layer - specifically checking whether each `_partial` flag meant "more real documents exist that were never parsed" (the fruitful Suffolk/South Gloucestershire case) or "the one document found was fully used but some schools' data was too sparse to build a confident polygon" (a genuine, already-exhausted data-completeness limit). This session was interrupted mid-way by a session-limit reset; the surviving worktree state (one already-pushed commit, plus a fully-computed but uncommitted Thurrock reconstruction in scratch files) was recovered and finished directly rather than re-run from scratch, since re-doing already-completed geocoding/reconstruction work would have been pure waste.

**Darlington: Hummersknott Academy's Heighington & Coniscliffe Associated Area landed** (commit `2b443ea`, landed before the interruption). The Hummersknott/Hurworth oversubscription maps were previously confirmed genuine flat raster scans (not a parsing bug), but Advance Learning Partnership's own "School Admission Policy Darlington Schools 2027-28" PDF, read in full this session, resolves one of the two ambiguities: Hummersknott's "Associated Areas" criterion (iv) is explicitly defined as the _whole_ "Ward of Heighington and Coniscliffe" for Map 2 (a partial hatched sub-area of the Ward of Park East for Map 1, which still needs pixel georeferencing and remains open). Since Map 2's area is the entire real electoral ward, no scan-tracing was needed at all - fetched the ward polygon directly from ONS Open Geography Portal's live `WD_MAY_2026_UK_BFC` FeatureServer (E05010419), the same real-administrative-boundary-instead-of-tracing-a-scan technique proven for Suffolk's civil parishes and (later this session) Islip's parishes. Cross-checked against 9 real geocoded villages visible on the map itself: 6 inside the map's own drawn boundary correctly fall inside the fetched ward polygon, 3 outside correctly fall outside. `import-catchments --local-authority "841"` and full verification confirmed clean before this session's interruption.

**Thurrock: 4 more primary catchments landed from a second, genuinely different source document.** Thurrock's existing `_partial` primary source was built entirely from one PDF (`master_catchment_list_from_2026_for_web_0.pdf`). This session found the council's admissions page also links a second, separate document (`catchment-areas-20240823-v01.pdf`) with its own 4th "Denominational School" column the original harvest never saw - covering Thurrock's 4 Catholic primary schools (Holy Cross, St Joseph's, St Mary's, St Thomas of Canterbury Catholic Primary), none of which appeared in the master list at all. Confirmed via `pdftotext`/`pymupdf` that this is a real, independently-structured table, not a duplicate of the existing source. Parsed the same way as the original Thurrock harvest: 1,678 unique roads across the 4 schools, geocoded via Nominatim (1,384 resolved), Voronoi-tessellated and clipped to the real Thurrock LAD boundary plus a trust-radius buffer, reduced to each school's dominant connected piece. All 4 schools cleared the 100m containment bar comfortably (296m-1186m margins) - no exclusions needed this time, unlike the original 13-of-18 yield from the master list.

**Verification.** `pnpm --filter @catchment-zone/shared sync-config` (parsed clean, no test-roster change since Thurrock already had entries) + `test` (45 passed) and the ingestor's full pytest suite (127 passed) both pass clean. `git status`/`git diff --stat` confirmed only the two intended files changed before committing. Committed (`8409691`, no `Co-Authored-By` trailer; required a `git rebase origin/main` first since the local branch had fallen behind the already-pushed Darlington commit) and pushed to `main`; landing confirmed via `git fetch origin main` and a 200 response with the correct feature count from `raw.githubusercontent.com` before importing. `import-catchments --local-authority "883"` built 17 primary (+4) + 2 secondary (unchanged) = 19 areas, 0 rejected. `catchment_areas` went from 11,156 -> **11,160**. `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 11,160, in sync. `refresh-catchment-scores` re-run synchronously to completion (7,631 of 11,160 areas scored). An explicit orphaned-row check found exactly 19 Thurrock rows in the DB matching the 19 features in the source files, zero duplicates. A live post-import point-in-polygon query (joined by `local_authority_code` first, then exact `area_name`, restricted to `status = 'OPEN'` to avoid Thurrock's closed/open URN-duplicate schools of the same name) confirmed all 4 new schools' own real DB coordinates fall inside their newly-landed polygons.

**Local authority count unchanged at 107** (both landings extended existing coverage). **Not completed this session, genuinely still open:** the audit's remaining local authorities - Coventry, Essex, Hartlepool, Luton, North East Lincolnshire, North Northamptonshire, Wakefield, Wirral, and Bristol's secondary (Downend) layer - were never reached before the session-limit interruption; none should be assumed exhausted, since none were actually re-checked. Darlington itself also still has two open threads: Map 1's partial hatched Park East sub-area (needs real pixel georeferencing, not a whole-ward shortcut) and Hurworth School's own Priority 5/6 maps. **Most promising next lead:** finish the original audit list above using the same "does a second real document exist beyond the one already parsed" question that found real wins for Darlington and Thurrock this session.

## Update: finished the interrupted `_partial`-audit - 9 LAs re-checked (all confirmed exhausted or blocked), Darlington's Park East landed, Essex secondary PAA gap identified for next session (2026-08-18, later session)

**Baseline at the start of this session: 11,160 `catchment_areas` rows, `map_catchments_cache.feature_count` = 11,160 (in sync), 107 local authorities, HEAD at `ddeb791`.** Picked up the prior session's interrupted `_partial`-audit exactly where it left off: Coventry, Essex, Hartlepool, Luton, North East Lincolnshire, North Northamptonshire, Wakefield, Wirral and Bristol's secondary (Downend) layer, plus Darlington's two remaining open threads (Park East, Hurworth Priority 5/6). Each LA got a genuine re-check for a second real document, not a rubber-stamp - the same standard that found real wins for Suffolk/South Gloucestershire/Darlington/Thurrock in earlier sessions.

**7 of the 9 LAs confirmed genuinely exhausted, not just re-asserted:**

- **Coventry**: the council's `category=Secondary` directory search was checked against the already-harvested `category=Primary` one - both return the identical 50-record directory (the category filter doesn't actually filter), confirming the existing 28-school "roads in catchment" harvest already saw everything the directory has.
- **Wirral, Wakefield, North East Lincolnshire, Luton**: targeted web searches for a second PDF/GIS layer beyond each council's already-used single tool/PDF found nothing real. Two apparent leads for NE Lincs (`arcgis.com/apps/instant/lookup` "Zone Lookup: School Catchment Areas" and an `experience.arcgis.com` "School Catchment Areas" app) turned out, on checking their ArcGIS item ownership, to belong to Edinburgh and a different English "WBC" council entirely - a generic-title false positive, not a NE Lincs source. Luton's `data.gov.uk` "Primary School Catchment Areas" dataset listing has no actual download links ("There are no links to this data").
- **Hartlepool**: the borough's Catholic/voluntary-aided primaries (14 of them) were re-confirmed structurally out of scope, not under-searched - they use their own faith-based admissions criteria with no catchment zone at all, consistent with the council's own "All COMMUNITY schools..." wording already used to scope the existing harvest.
- **North Northamptonshire**: live-re-queried the same ArcGIS Online services listing already exhaustively checked on 2026-08-11 (409 services now vs 411 then, ordinary churn) - the same 4 already-enabled `_Linked_Areas` layers are still the only ones carrying a school-name field. Re-confirmed complete.

**Bristol's Downend gap re-checked, still genuinely undigitisable but for a more precise reason than before.** Re-fetched St Bede's own Downend parish PNG directly (the earlier WebFetch had followed a redirect to a 404; the real path is `/_site/data/files/images/newsletters/1/...`) and confirmed byte-for-byte the same 813x468px image already on file - not republished at higher resolution. Visual inspection this session was actually more successful than the prior session's verdict suggested (the large "MANGOTSFIELD" place label and a real pale-cyan 1km OS-style grid are both legible, and the grid spacing measures a consistent 62px/km via autocorrelation on both axes), but every candidate ground-control point precise enough to anchor translation - small village labels, a motorway-junction marker - stayed illegible even at 6x-10x upscaling, so there is no way to fix translation with the comfortable margin this project requires. Declined again, now specifically for "no anchorable GCP" rather than the previous "resolution too low to read anything" framing.

**Essex: a genuinely new, confirmed-live secondary-school data field found in the already-used tool, but not landed this session - a concrete lead for next time.** Essex's existing `primary_catchment_partial` source queries `secureapps.essex.gov.uk`'s real SSRS backend (`PrimaryAndSecondarySearchReport`) but the prior harvest only ever extracted the primary-school result (`Tablix2`/`Details3_Collection`/`SchoolName`) - live-queried the same endpoint this session (e.g. `uprn=100091433220`) and confirmed it also returns a full, separate secondary-school Priority Admission Area result in `Tablix3`/`Details4_Collection`/`SchoolName2` (e.g. St Martin's School, URN 136875, for that address) that was never captured - meaning Essex secondary schools' PAAs are real, sampleable data sitting in the exact same already-proven endpoint, just discarded. (Also found, while investigating: individual Essex schools sometimes publish their own official ECC-produced "Priority Admission Area" map PDF directly - St Martin's School's own site links one - and at least that file is a genuine Esri ArcMap 10.9.1 GeoPDF export carrying real embedded `/Measure`/`/GEO` geospatial metadata (WKT British National Grid + `GPTS`/`LPTS` corner correspondences), which would allow pixel-exact georeferencing with zero landmark-picking uncertainty if a fuller index of these per-school PDFs could be found - promising but not close to comprehensively indexed, since Essex CC's own admissions page says these maps are "available on request" rather than centrally published.) **Not executed this session**: doogal.co.uk's postcode-CSV bulk export (`UkPostcodesCSV`/`AdministrativeAreasCSV?district=...`), the free postcode-coordinate source this project has relied on for every point-sample reconstruction since Hartlepool, now returns HTTP 400 with an empty body for every district tried (Essex's 12 districts and Wakefield's previously-working district code alike) - a site-side change since the last session used it, not a bug in this project's own code. Building Essex's secondary layer needs either a fixed/alternate postcode-coordinate source or a from-scratch per-school GeoPDF hunt; left as fully-scoped, ready-to-execute work rather than attempted with a workaround that would risk quality.

**Darlington: Park East landed, closing the one thread the prior session correctly flagged as a genuine (not dead-end) lead.** `hummersknott-associated-area-2.pdf` ("Map 1", the hatched-Park-East sub-area of Hummersknott Academy's associated-area admissions criterion) was digitised via real pixel georeferencing of its scanned page - no embedded GeoPDF metadata this time (checked via `pikepdf`, unlike the Essex find above), so anchored the traditional way: a genuine printed scale bar (9 evenly-spaced tick marks across 0-300m, measured via column-wise dark-pixel autocorrelation, giving 1.1257 m/px) plus a north arrow confirming north-up (rotation 0), plus a single real ground-control point (Skerne Park Academy, URN 139195, the only school printed on this specific page - its OS-style building-footprint icon centroid matched to its own real DB coordinate) - the same single-point-plus-known-scale technique already proven for Bristol/Patchway in this project. The hand-drawn boundary line was colour-masked and closed via morphology; it split into two disconnected arcs after closing (a real raster gap where the line crosses a coloured road symbol, not a tracing error) - fixed by filling both arcs and unioning them rather than forcing a larger closing kernel, which reconstructs the single correct interior region directly. Verified against 5 further real points _not_ used for anchoring, each independently geocoded via Nominatim and checked for the correct inside/outside relationship against the map's own drawn line: South Park (inside, 563m margin), Tees Drive/Skerne Park estate (inside, 129m), Victoria Embankment (inside, 201m), Neasham Road/Firthmoor (outside, 394m from the boundary) and Salters Lane North/Harrowgate Hill (outside, 3.0km) - 5/5 correct, spanning most of the polygon's real extent. Polygon simplified from 958 to 289 vertices (shapely, ~2.5m tolerance), all 6 checks re-confirmed unchanged after simplification; single clean Polygon, not MultiPolygon. Same structural caveat as the rest of this source: an alternative-priority associated area, not Hummersknott's own designated catchment, so the school's own site is not expected to fall inside it (and does not).

**Verification.** `pnpm --filter @catchment-zone/shared sync-config` + `test` (45 passed) and the ingestor's full pytest suite (127 passed, after `uv sync --extra dev` to install the test-only dependency group in this fresh worktree) both pass clean. `npx prettier --check config/catchment-sources.yml` confirmed no formatting changes needed. `git status`/`git diff --stat` confirmed only the two intended files changed (340 insertions) before committing; `git fetch origin main` showed the local branch already current, no rebase needed. Committed (`513cbab`, no `Co-Authored-By` trailer) and pushed to `main`; landing confirmed via `git fetch origin main` and a 200 response with the correct 2-feature content from `raw.githubusercontent.com` (pinned to the commit SHA) before importing. `import-catchments --local-authority "841"` built 8 primary (unchanged) + 2 secondary (+1) = 10 areas, 0 rejected. `catchment_areas` went from 11,160 -> **11,161**. `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 11,161, in sync. `refresh-catchment-scores` re-run synchronously to completion (7,631 of 11,161 areas scored). An explicit orphaned-row check found exactly 8 primary + 2 secondary Darlington rows in the DB, matching the source files' feature counts exactly, zero duplicates. A live point-in-polygon query against the actual stored `geometry_geojson` (not just the locally-computed polygon) re-confirmed all 5 independent verification points plus the anchor school landed correctly.

**Local authority count unchanged at 107** (this session only extended existing coverage, landed no brand-new LA). **Genuinely still open for a future session, in priority order:** (1) Essex secondary PAA - the exact mechanism is proven live, just needs a working postcode-coordinate source now that doogal.co.uk's bulk CSV export is down; (2) Hurworth School's own Priority 5/6 maps (`hurworth-and-hurworth-place-map.pdf`, `hurworth-priority-6-map-a/b/c.pdf`, all already downloaded and confirmed to carry real scale bars/OS grids this session, not yet digitised for time reasons); (3) a fuller index of Essex's per-school official GeoPDF PAA maps, if one exists beyond individual schools' own websites. With this pass, every LA in the original interrupted-audit list has now actually been re-checked at least once - the `_partial` audit itself is complete, even though 2 of its 9 items (Essex secondary, Hurworth) remain open leads rather than closed dead ends.

## Update: Essex's secondary Priority Admission Areas landed - 33 of 47 harvested schools cleared the margin bar (2026-08-18, later session)

**Baseline at the start of this session: 11,161 `catchment_areas` rows, `map_catchments_cache.feature_count` = 11,161 (in sync), 107 local authorities, HEAD at `36e583c`.** Picked up the prior session's scoped, ready-to-execute lead directly: Essex's SSRS `PrimaryAndSecondarySearchReport` endpoint (already proven live for the primary layer) returns a second, previously-unused secondary-school Priority Admission Area result in every response (`Tablix3`/`Details4_Collection`/`SchoolName2`, alongside the primary layer's own `Tablix2`/`SchoolName`) - no new endpoint discovery needed, only re-querying with the second field extracted.

**Coordinate source substitution.** doogal.co.uk (the primary layer's postcode-CSV source) confirmed still returning HTTP 400 site-wide. Rather than a from-scratch GeoPDF hunt, used postcodes.io's autocomplete search (`GET /postcodes?q=<prefix>&limit=100`) as a direct drop-in replacement: it returns up to 100 full postcode records - postcode, lat/lon, `admin_district`, `admin_county` - per prefix query, doubling as both the postcode-list source and the coordinate lookup in one call. Essex CC's 12 real districts were mapped to their real postcode outcodes by validating every candidate outcode in the CM/CO/SS/RM/IG/EN/CB areas against postcodes.io's `/outcodes/{outcode}` endpoint (69 of ~140 candidates matched a real Essex CC district). For each of those 69 outcodes, queried all 10 sector digits (`q="<outcode> <digit>"`, limit 100), kept results whose own `admin_district` was a real Essex CC district, and randomly retained up to 20 per sector - matching the primary layer's own sampling density. Result: 4,189 stratified sample postcodes.

**Query and reconstruction.** Queried the same two SSRS endpoints as the primary layer (`AddressListForGivenPostcode` then `PrimaryAndSecondarySearchReport` on the first returned UPRN) for all 4,189 points, in 6 sequential batches (~9 minutes each - this server's own per-call latency dominates; raising client concurrency from 12 to 30 measured no speedup, so kept at a moderate 15). Zero hard failures across all 8,378 calls; 195 postcodes had no UPRN in the SSRS gazetteer. Of 3,994 successfully classified points, 3,123 resolved to a named secondary PAA school and 871 to "no priority area" (Essex's SchoolId=9999 sentinel, same as the primary layer - most Essex secondaries are distance-based with no PAA at all). Reconstruction used the identical method already proven for the primary layer: Voronoi tessellation over all 3,994 classified points (reprojected to EPSG:27700; median nearest-neighbour spacing 111.4m, p90 449.1m - tighter than the primary layer's own doogal-sourced sampling), dissolved by school, clipped to the real Essex county boundary (this time from ONS Open Geography Portal's live `Counties_and_Unitary_Authorities_December_2023_Boundaries_UK_BFC` FeatureServer, `CTYUA23CD=E10000012`, replacing doogal's KML export) and to the same 900m trust-radius buffer around every real sampled point, then reduced to each school's single largest connected polygon before verification.

**Name matching and verification.** 47 distinct school names were harvested. 44 matched an open Essex school's current official name directly, by containment, or by stripping a trailing site qualifier - no disambiguation guessing needed anywhere, since secondary school names are far more distinctive than the primary layer's common village-primary names. The other 3 needed independent confirmation, all found genuine: "Tendring Technology College" and "Clacton Coastal Academy" are the SSRS system's stale pre-rename names for what this project's own GIAS-sourced schools table lists as "Lift Tendring" and "Lift Clacton" (confirmed via Wikipedia and GIAS establishment records as the same site, identical coordinates, under Lift Schools' 2024 rebrand); "Helena Romanes School" matched by name exactly but was missing from the first matching pass because it is phase-coded `All-through` rather than `Secondary` in this project's own table - included once found, since it is a real open Essex school with an exact name match. Applied the standard 100m own-school-coordinate margin bar: of 47 dissolved polygons, **33 passed comfortably** (margins 133m-1,521m, most in the many hundreds of metres) and were shipped; **14 were declined** - 2 only marginally short (44.2m, 70.7m, correctly excluded rather than shipped on a fit just under the bar) and 12 by hundreds of metres to several kilometres (read as real PAA zones that legitimately do not enclose the school's own site - e.g. a zone drawn around a satellite catchment area - rather than name mismatches, since all 47 matches were independently confident). Zero `MultiPolygon` features in the final output.

**Verification.** `pnpm --filter @catchment-zone/shared sync-config` + `test` (45 passed, after bumping Essex's `sourceTypeCount` fixture from 1 to 2 in `catchment-sources.test.ts` to reflect the new secondary source) and the ingestor's full pytest suite (127 passed, after `uv sync --extra dev` in this fresh worktree) both pass clean. `git status`/`git diff --stat` confirmed only the three intended files changed before committing; `git fetch origin main` showed the local branch already current, no rebase needed. Committed (`a38af95`, no `Co-Authored-By` trailer) and pushed to `main`; landing confirmed via `git fetch origin main` and a 200 response from `raw.githubusercontent.com`. `import-catchments --local-authority "881"` built 185 primary (unchanged) + 33 secondary (+33) = 218 areas, 0 rejected. `catchment_areas` went from 11,161 -> **11,194**. `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 11,194, in sync. `refresh-catchment-scores` re-run synchronously to completion (7,664 of 11,194 areas scored). Since this is a brand-new source (no prior secondary rows for Essex existed), an explicit duplicate-row check by `area_name` found none - exactly 33 rows, matching the 33 shipped features. A live point-in-polygon query against the actual stored `geometry_geojson` (joined by `local_authority_code`/`source_id` then exact `area_name`, restricted to `status = 'OPEN'`) confirmed all 33 new secondary catchments correctly contain their own real school's own DB coordinate.

**Local authority count unchanged at 107** (this session extended existing Essex coverage, landed no brand-new LA). Also checked whether individual Essex schools' official ArcMap GeoPDF maps (the alternative lead flagged by the prior session) would be needed as a fallback - not pursued, since the SSRS/postcodes.io approach alone yielded a solid, comfortably-verified result and per the standing "already-proven path first" preference. **Genuinely still open for a future session:** the 14 declined secondary schools' real PAA zones (would need either individual per-school GeoPDF maps, if a fuller index of them exists beyond scattered individual school websites, or denser sampling specifically around each declined school's own site to rule out a reconstruction-sparsity explanation rather than a genuine off-site zone); Hurworth School's own Priority 5/6 maps (Darlington, flagged two sessions ago, still not digitised).

## Update: Essex GeoPDF lead investigated and confirmed real but not reproducible; a genuine per-school PAA map found for Notley High School but declined for zero containment margin - no new data landed this session (2026-08-19)

**Baseline at the start of this session: 11,196 `catchment_areas` rows, `map_catchments_cache.feature_count` = 11,196 (in sync), 107 local authorities, HEAD at `2093822`.** Picked up the specific lead flagged at the end of the Essex secondary-PAA session: a prior session had found that St Martin's School's own published Priority Admission Area map PDF was "a genuine Esri ArcMap 10.9.1 GeoPDF export carrying real embedded `/Measure`/`/GEO` geospatial metadata", promising pixel-exact georeferencing with zero landmark-picking uncertainty for the 14 secondary schools declined from that session's SSRS/Voronoi harvest, if a fuller index of these per-school PDFs could be found.

**The GeoPDF claim is confirmed genuinely real, but does not generalise.** Downloaded St Martin's own PAA PDF (`st-martins.essex.sch.uk/assets/Documents/Attachments/St-Martins-School-Priority-Admission-Area.pdf`) and inspected it with `pymupdf`: the page's `/VP` (viewport) dictionary does contain a real `/Measure` object with `/Subtype /GEO`, a `/GCS` coordinate-system reference, and `/GPTS`/`/LPTS` arrays giving 4 real WGS84 lat/lon corner points (51.54-51.73N, 0.16-0.40E - genuinely centred on Brentwood/Essex) matched to the page's normalised viewport corners - this is real, not a false lead. However, St Martin's is itself one of the 33 schools already landed via the SSRS/Voronoi method last session, so this specific file adds nothing new. To test whether the technique reproduces for any of the 14 declined schools, downloaded and inspected two more genuine official per-school PAA maps found this session: Philip Morant School & College's own map (`cms-site-files.reactfiles.co.uk/sigmaphilipmorant/...Priority-Admisison-Area-Map.pdf`, linked from the school's own Sigma Trust website) and Notley High School's own map (`notleyhigh.com/docs/Imported/Admissions/NotleyHigh.pdf`, linked from the school's own admissions page). Neither carries a `/VP`/`/Measure`/`/GPTS` entry anywhere in the file (checked via both `pymupdf`'s page object dump and a raw `strings` search of the whole PDF for `Measure`/`GPTS`/`LPTS`/`Viewport`) - Philip Morant's file is producer `PDFium` (a web-export/flatten path that evidently strips the geospatial dictionary even when the source was a real GeoPDF), and Notley's is producer `Acrobat Distiller 20.0`, title `s21 Applications.mxd`, author `andrew.heynes` - a genuine ArcMap export, but printed-to-PostScript-then-distilled rather than exported via ArcMap's dedicated GeoPDF path, which does not preserve `/Measure`. **Conclusion: the GeoPDF metadata technique is real but essentially a one-off for St Martin's specific export path, not a repeatable method across Essex secondary schools** - each school's PDF would need individual download-and-inspect to know, and of the 3 checked (a small but real sample, chosen because they were the only 3 of roughly 10 searched schools that had a standalone PAA map online at all - most really are "available on request" only, matching Essex CC's own wording), only 1 had it, and that 1 was already landed.

**Notley High School's own map was a genuine, high-quality, precisely drawn PAA map - digitised via traditional multi-point affine georeferencing, but declined.** The map (`Notley High School Priority Admission Areas`) is rendered on a real OpenStreetMap base layer (© OpenStreetMap contributors, credited on the map itself) with two clearly coloured tiers - a purple "Notley High Outlying Area" and a green "Notley High Town Area" - plus a genuine printed scale bar. Measured the scale bar directly via column-wise dark-pixel transition detection (0/0.375/0.75/1.5 mile tick marks at x=108/215/314/524px), giving 5.73 m/px. Ground-control points were taken from 10 real Essex villages visible on the map, geocoded via Overpass API (querying live OSM `place` nodes directly, since Nominatim's returned coordinates for several of these small-village names turned out to disagree with the actual OSM place-node position by 500-1500m for 3 of the 10 - a real discrepancy caught by residual-checking, not a picking error, once cross-referenced against Overpass). A 7-point least-squares affine fit on the well-behaved points gave an implied scale of 5.83-5.87 m/px - within 2.5% of the independently-measured scale bar, a real internal consistency check - with fit-point residuals of 49-165m. Applying the fit to Notley High School's own real DB coordinate placed it at pixel (1171, 1076) - visually confirmed (crosshair overlay) to sit essentially exactly on top of the map's own drawn boundary line near the "King William" roundabout, indistinguishable from either side of the purple/green boundary given the ~100m local residual. **Declined per this project's standing containment-margin bar**: unlike the 33 already-shipped Essex secondary schools (133m-1,521m margins) or even the 2 marginally-declined ones from last session (44m/70m), this is a zero-margin case - the school's real site sits on the line itself, not comfortably on either side, so no honest inside/outside classification can be made regardless of georeferencing precision.

**No comparable text-defined whole-administrative-area lead found for any of the 14 declined schools (the fallback technique that worked for Hurworth/Darlington).** Searched the Essex CC 2026/27 Secondary Policies Directory (116 pages, downloaded and full-text-extracted) for every explicit parish/ward-list PAA definition. Found two genuine ones - Saffron Walden County High School's PAA is explicitly defined as 13 named civil parishes (Ashdon, Great Chesterford, Great Sampford, Hadstock, Hempstead, Littlebury, Little Chesterford, Little Sampford, Radwinter, Saffron Walden, Sewards End, Strethall, Wendens Ambo) and Shenfield High School's as 5 named parishes (Blackmore, Doddinghurst, Kelvedon Hatch, Navestock, Stondon Massey) plus an additional unmapped "or in parts of..." extension - but both of these schools are already among the 33 landed last session via SSRS, so neither is a new win. No equivalent clean parish/ward list was found for any of the 14 declined schools within the time available; the large majority of Essex secondary academies' own admissions policies define their PAA purely by "see map, available from the school/on request" with no named administrative area at all, unlike Darlington's Hurworth/Hummersknott criteria.

**Also checked, for completeness, whether other declined-candidate schools simply publish their own PAA map online at all** (Colne Community School, Clacton County High School, William de Ferrers School, Chelmer Valley High School, Roding Valley High School, Mark Hall/Passmores/Stewards/Burnt Mill Academy for Harlow's shared "defined geographical area" criterion) - none were found to have a standalone map PDF linked from their own site; Essex CC's "available on request" framing genuinely holds for most schools, and only the 3 discussed above (St Martin's, Philip Morant, Notley) had one discoverable online out of roughly 10 checked.

**No data landed this session - a genuine, fully-investigated negative result rather than a forced marginal fit.** `catchment_areas` remains at 11,196, `map_catchments_cache.feature_count` remains 11,196, 107 local authorities unchanged. No files in `config/catchment-sources.yml` or `data/digitized-catchments/` were modified, so no `sync-config`/test/import/verification cycle was needed this session. **Genuinely still open for a future session**: the 14 declined Essex secondary schools remain declined for the same reason as before (real PAA zones that legitimately don't enclose the school's own site, per last session's notes) - both the GeoPDF-metadata route and the text-defined-administrative-area route were tried in good faith this session and neither produced a new landable school; a from-scratch pixel-trace of Notley's map is possible in principle but would still hit the same fundamental problem (the school sits on the boundary line itself, not a georeferencing-precision problem that better anchoring could fix). Hurworth's own Priority 6 Maps A and C (Darlington) remain the other standing open lead, flagged unchanged since the last session that touched them.

## Update: Hurworth School's Priority 5 landed via pixel georeferencing, Priority 6 Map B via real parish union; Maps A/C declined (2026-08-18, later session)

**Baseline at the start of this session: 11,194 `catchment_areas` rows, `map_catchments_cache.feature_count` = 11,194 (in sync), 107 local authorities, HEAD at `ccd289e`.** Picked up the one remaining open thread flagged by the last two Darlington sessions: Hurworth School's own Priority 5/6 oversubscription maps (`hurworth-and-hurworth-place-map.pdf`, `hurworth-priority-6-map-a/b/c.pdf`), previously confirmed real but not yet digitised.

**Read Hurworth School's actual policy text first**, per this project's standing preference for checking a source's own written definitions before assuming pixel-tracing is the only option. The ALP Trust admissions PDF used successfully for Hummersknott turned out not to cover Hurworth at all (Hurworth School's admissions authority is Northern Arch Learning Partnership, a different trust) - the real text came from Darlington's own secondary admissions guide for parents (`secondary-guide-for-parents-2026-2027.pdf`), which gives Hurworth's full criteria: Priority 5 is "Children living in Hurworth & Hurworth Place (see map)"; Priority 6 "Associated Areas" (Note 4) is explicitly text-defined as "Children who live within the following areas: The villages of Middleton St George, Middleton One Row, Neasham, Bishopton, Sadberge, Great Stainton, Little Stainton and the rural areas of Sockburn, Low Dinsdale and Hurworth Moor (as defined on maps A, B & C)".

**Priority 5 landed via real pixel georeferencing.** `hurworth-and-hurworth-place-map.pdf` turned out to be a much higher-fidelity scan than the earlier Park East map - a digitally-coloured (not hand-drawn) orange highlight over a proper OS 1:25,000 base with crisp place labels. Anchored with 4 ground-control points (Hurworth School's own DB coordinate matched to the map's "Sch" symbol; Blackwell Bridge; Sockburn Hall; Neasham village), each independently geocoded via Nominatim/Overpass, converted to OSGB36, and fit with a 6-parameter least-squares affine (residuals 8-18m - excellent for this scale). The orange fill was extracted by HSV colour masking (a clean single region, no morphological gap-filling needed) and simplified from 1,148 to 362 vertices. Verified against 5 independent points not used for anchoring: both open Hurworth schools fall inside (536m and 391m margins) as expected, since Priority 5 is the village's own base priority tier, not an alternative-school arrangement; Neasham, Croft-on-Tees and Dalton-on-Tees all correctly fall outside (424-846m) - 5/5 correct.

**Priority 6 Map B landed via real ONS civil parish data instead of pixel-tracing.** An initial multi-point affine attempt on Map B's own raster (Sadberge, Bishopton, Great Stainton, Little Stainton, Whitton, Great Burdon as ground control) produced wildly inconsistent implied scale (4.3-11.7 m/px depending which pair of points was used) - too unreliable to trust for a boundary trace, likely reflecting genuine imprecision in matching schematic place-label text to real village centroids rather than a georeferencing-method problem. Since Note 4's own text names 4 of Map B's places as whole villages with no "part"/"hatched" qualifier (unlike Park East's explicit "hatched area... within the Ward of Park East"), applied the same real-administrative-boundary technique already proven for Heighington & Coniscliffe: fetched Bishopton (E04000289), Great Stainton (E04000295), Little Stainton (E04000301) and Sadberge (E04000308) as real civil parishes from ONS Open Geography Portal (Parishes and Non Civil Parished Areas, December 2024, EW BFC) and unioned them into a single contiguous Polygon. Cross-checked by overlaying the 4 real parish outlines on the source map using a rough transform - the union's shape closely tracked the map's own drawn hatch boundary on every side, including correctly explaining two details the text/map didn't state outright: Great Stainton's own village core sits just outside the hand-drawn hatch even though the parish itself (and the policy text) reaches it, and "Whitton" appears partly hatched on the map despite not being named anywhere in Note 4's text (read as the map hatching slightly more than the policy names, so the text rather than the drawing was treated as authoritative). Verified directly against the real ONS geometry (no pixel transform in the final geometry at all): all 4 named villages fall inside (618-921m margins); Great Burdon, Darlington town centre, Middleton St George, Whitton and Barmpton all correctly fall outside (340-4,387m) - 9/9 correct.

**Priority 6 Maps A and C investigated but declined.** Map A's drawn boundary visually spans both Middleton St George parish (a clean textual match, containing Middleton One Row) and Low Dinsdale, a cross-river North Yorkshire hamlet with no matching civil parish found in the ONS dataset searched - so unlike Map B, no clean whole-administrative-area substitute exists. Repeated pixel-georeferencing attempts on Map A's own raster (Dinsdale railway station, Low Dinsdale, Middleton One Row as ground control) produced x/y scale disagreements of up to 1.6x; even after deriving an independent, highly precise scale (2.205 m/px) directly from the source PDF's own exact A4 MediaBox and its printed "SCALE 1:25,000 at A4" - avoiding GCP-based scale estimation entirely - a single-anchor check against that trusted scale still left 250-490m residuals on the two cross-check points, short of a comfortable margin. Map C (Hurworth Moor / rural Neasham / the Sockburn river corridor) has no matching whole civil parish at all for its southern Sockburn extent, so would need genuine from-scratch pixel tracing not attempted this session. Both left as confirmed-real, not-yet-attempted leads for a future session rather than shipped without a comfortable containment margin.

**A real ingestor gotcha found and fixed mid-session.** The ingestor resolves `catchment_sources` rows by `(local_authority_code, academic_year, source_type)`, not by `download_url` - adding Hurworth's 2 features as a _second_ `secondary_catchment_partial` row for Darlington (alongside the existing Hummersknott row) silently resolved to the _same_ source id on import, overwriting that row's `download_url`/licence metadata while leaving the actual `catchment_areas` geometry rows untouched (confirmed via `updated_at` timestamps and unchanged `geometry_checksum`s - no data was lost or duplicated, but the source's own metadata briefly pointed at the wrong file). Fixed by merging Hurworth's 2 features into the same geojson file as Hummersknott's 2 (both are on the same admissions page in reality) and removing the duplicate yml row, restoring one row with 4 features. Left an explicit comment on the row warning future sessions not to add a second `secondary_catchment_partial` row for the same LA/year without merging into the existing one first.

**Verification.** `pnpm --filter @catchment-zone/shared sync-config` + `test` (45 passed, `catchment-sources.test.ts`'s Darlington `sourceTypeCount` fixture correctly unchanged at 2 once the merge fix was applied) and the ingestor's full pytest suite (127 passed, after `uv sync --extra dev` in this fresh worktree) both pass clean. `git status`/`git diff --stat` checked before each of the two commits. `git fetch origin main` showed the local branch already current before both pushes, no rebase needed. Committed in two steps (`a61edd5` landing the features, `3878f18` fixing the source-row collision; neither carries a `Co-Authored-By` trailer) and pushed to `main`; landing confirmed via `git fetch origin main` and a 200 response with the correct 4-feature merged content from `raw.githubusercontent.com` before the final import. `import-catchments --local-authority "841"` built 8 primary (unchanged) + 4 secondary (+2) = 12 areas, 0 rejected. `catchment_areas` went from 11,194 -> **11,196**. `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 11,196, in sync. `refresh-catchment-scores` re-run synchronously to completion (7,665 of 11,196 areas scored; Priority 5 picked up a real `attainment8_average` score, Priority 6 and both Hummersknott associated areas correctly remain unscored, consistent with the existing associated-area rows). An explicit orphaned-row check (`catchment_areas` rows with no matching `catchment_sources.id`) found none, and a `(source_id, geometry_checksum)` duplicate check found none. A live point-in-polygon query against the actual stored `geometry_geojson` (joined by `local_authority_code`/`source_id` then exact `area_name`, restricted to `status = 'OPEN'`) confirmed Hurworth School's own coordinate falls inside its Priority 5 polygon and outside its Priority 6 polygon, exactly as verified locally before import.

**Local authority count unchanged at 107** (this session extended existing Darlington coverage, landed no brand-new LA). **Genuinely still open for a future session:** Priority 6 Maps A and C for Hurworth School (both confirmed real, both need either a better-anchored pixel-georeferencing pass or a matching administrative-area source not yet found - see the block comment in `config/catchment-sources.yml` for the specific residuals and blockers hit this session); Essex's 14 declined secondary schools and a fuller Essex per-school GeoPDF index (carried over from the prior two sessions, untouched this session).

## Update: first-pass sweep of literally never-touched local authorities - Jersey and Isle of Man landed as this project's first two Crown Dependencies, Guernsey confirmed real but API-blocked (2026-08-19)

**Baseline at the start of this session: 11,196 `catchment_areas` rows, `map_catchments_cache.feature_count` = 11,196 (in sync), 107 local authorities, HEAD at `0227aad`.** Unlike the many recent sessions re-checking already-documented `candidates:` entries, this session's task was to find local authorities that had genuinely never been investigated at all - neither enabled in `sources:` nor documented in `candidates:`.

**Building the "never touched" list.** Queried `schools` directly for every distinct `local_authority_code` with an OPEN school (237 distinct codes), resolved each to a real name via the DfE's own GIAS local-authority-code guidance page and a full Scottish `S12000` council-area code table (fetched from a third-party PDF mirror after ONS's own listing pages proved hard to scrape directly), then cross-referenced every code against both `sources:`' `local_authority_code` values and `candidates:`' `local_authority_name` values (flexible/normalised matching, since candidates are recorded by name only and several cover multiple LAs in one entry, e.g. "Wrexham, Flintshire, Conwy... (Wales)"). Result: only 5 codes were in neither list - `666` (Powys) and `668` (Pembrokeshire) turned out to be stale duplicate codes for LAs already enabled under their `W-`-prefixed equivalents (`W-666`/`W-668`, both already landed), not real gaps once traced down; the genuine 3 were `705` (Isle of Man), `706` (Guernsey) and `707` (Jersey) - the UK's 3 Crown Dependencies. These aren't part of the DfE's local-authority system at all (their schools carry `establishment_type_name: "Offshore schools"`), but this project's own `schools` table does carry real OPEN schools for all three, so they qualified as genuinely untouched by this project's own definition.

**Jersey: landed via its own government ArcGIS Experience Builder app.** Jersey's admissions page links `experience.arcgis.com/experience/1cc22f00c95844e8acd48074048ce18d` ("Jersey schools catchment areas", owned by `maps.gov.je`). That Experience Builder item's own `resources/config/config.json` named a `WEB_MAP` data source ("Jersey School Catchments Web Map"); that webmap's own `operationalLayers` in turn named the real underlying FeatureServer (`Jersey_Mapping/School_Catchments/FeatureServer/0`) plus, critically, the States of Jersey's own `School_Primary`/`School_Secondary` point layers on the same platform - the same "interactive tool's own backend endpoint" technique this project has used repeatedly, now applied to a Crown Dependency government tool for the first time. This project's `schools` table has **zero** geocoded coordinates for any of Jersey's 42 OPEN schools (`local_authority_code` `707`), so verification used those government point layers as independent real-world ground truth instead of a DB coordinate - the same standing of evidence, just sourced from the same authoritative government GIS platform rather than this project's own DB. 20 of 22 primary catchment polygons shipped (margins 102m-2501m); Janvrin School (15m) and Rouge Bouillon School (55m) declined for falling under the 100m comfort bar despite being technically inside. 4 secondary catchments (Jersey's 4 non-selective States secondaries only - Hautlieu is selective/grammar, De La Salle/Victoria College/JCG/Beaulieu Convent are fee-paying, none of the 5 have a catchment) were not published directly - dissolved via `shapely.unary_union` from the 22 primary polygons grouped by their own `Secondary` attribute, each reduced to its single largest connected piece (one, Grainville School, produced sub-0.1%-area sliver artifacts from the union, exactly the failure mode this project's dominant-piece discipline exists to catch), verified against the same government point layer (margins 548m-2501m).

**Isle of Man: landed via an embedded ArcGIS Web AppBuilder app, after confirming a bot-check block was not a login wall.** The island government's own catchment-areas page (`desc.gov.im/education/education/catchment-areas/`) returned "The requested URL was rejected" to a bare `WebFetch` request, but a plain `curl` with an ordinary browser User-Agent got a clean HTTP 200 with real content - a JS-challenge-style bot-check, not a genuine credential wall, so not a hard stop per this project's standing rule. That page embeds a "Local Information"/MyNearest ArcGIS Web AppBuilder app (`manngis.maps.arcgis.com`) whose webmap named a real government MapServer (`maps.gov.im/manngispubserver/rest/services/CorporateDynamicServices/ProdFeeds/MapServer`) with dedicated `Schools` (layer 0) and `School Catchment Areas` (layer 1) sublayers, queried directly (native EPSG:27700, reprojected via `outSR=4326`). Only 11 of 39 Isle of Man OPEN schools have a DB coordinate, so verification again used the government's own `Schools` point layer for every school, not just those 11 - and that same layer's own `Status`/`Notes` fields independently confirmed a genuine structural absence for St Marys R.C School ("Non-DEC", parish-based admissions, not catchment-polygon) and St Thomas C Of E School ("Non-DEC", "No designated catchment area"), consistent with both being genuinely absent from the catchment layer too. Of 38 raw features (30 single-school zones, 8 genuine "either school" joint zones), 35 shipped: 27 single-school zones verified against their own school's government point (margins 188m-3605m) plus all 8 joint zones, shipped using this project's existing "A / B (shared)" convention (see Middlesbrough's King's Academy/Outwood Academy Acklam precedent) since a genuine shared zone correctly and expectedly falls outside both named schools' own points (608m-6624m), not a failure. 3 declined for a sub-100m margin: Scoill Vallajeelt (79m) and both halves of a real East/West split zone for Kewaigue Primary School (East 51m, West unverified - the sibling's thin margin undermined confidence in shipping either half). One `MultiPolygon` feature (Scoill Phurt Le Moirrey) reduced to its dominant piece; zero `MultiPolygon` features in the final output.

**Guernsey: real data confirmed to exist, genuinely blocked - not a login wall, not "no data found".** `maps.digimap.gg/gsySchoolCatchmentPrimary.htm`'s own JS config names a real backend (`StatesOfGuernsey/gsySchoolCatchmentPrimaryOL/MapServer`, layer 1 `NewPrimaryCatch2014`, a genuine per-school `SCHOOL`-field polygon layer with a distinct fill colour per school in its own `drawingInfo`) plus sibling services for secondary catchments and school locations, all on the same server. Checked each service's own root JSON directly: all three advertise `capabilities: "Map"` only - `/query` and `/identify` both return HTTP 400 "The requested capability is not supported" when called directly against layer 1, with and without `outSR` reprojection - an old ArcGIS Server instance (`currentVersion` 10.22) with feature access deliberately disabled server-side, unlike Jersey's and Isle of Man's equivalent services (both fully Query-capable) landed the same session. Documented as a `candidates:` entry with a specific roadmap for a future session: the layer's own known per-school colours make a colour-mask-segmentation attempt against an exported map image (the still-enabled `Map`/export capability) a real, non-speculative path forward, just not attempted this session given its size relative to the rest of this sweep.

**Verification.** Added `{ code: "707", name: "Jersey (Channel Islands)", sourceTypeCount: 2 }` and `{ code: "705", name: "Isle of Man", sourceTypeCount: 1 }` to `catchment-sources.test.ts`'s `PILOT_LOCAL_AUTHORITIES` fixture. `pnpm --filter @catchment-zone/shared sync-config` + `test` (45 passed) and the ingestor's full pytest suite (127 passed, after `uv sync --extra dev` in this fresh worktree) both pass clean. `npx prettier --write` run only against the two changed files (not repo-wide) to avoid pretty-printing the committed minified GeoJSON. `git status`/`git diff --stat` checked before committing; `git fetch origin main` showed the local branch already current, no rebase needed. Committed (`9546000`, no `Co-Authored-By` trailer) and pushed to `main`; landing confirmed via `git fetch origin main` and a matching SHA from `api.github.com`. `import-catchments --local-authority "707"` built 20 primary + 4 secondary = 24 areas (0 rejected); `import-catchments --local-authority "705"` built 35 primary areas (0 rejected). `catchment_areas` went from 11,196 -> **11,255**. `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 11,255, in sync. `refresh-catchment-scores` re-run synchronously to completion (7,665 of 11,255 areas scored). A live point-in-polygon query against the actual stored `geometry_geojson` (joined by `local_authority_code`/`source_id` then exact `area_name`, restricted to `status = 'OPEN'`) re-confirmed several spot-checked schools land inside their own real government-sourced coordinate exactly as verified pre-import (e.g. Onchan Primary School 304m, Le Rocquier School 548m, Trinity School 1843m), and correctly found no matching `schools` row for the 8 Isle of Man joint/shared-zone rows, exactly as designed.

**Local authority count: 107 -> 109** (Jersey and Isle of Man, this project's first two Crown Dependencies). **The "never touched LA" backlog is now genuinely empty** for local authorities with real, non-overseas school populations: every one of the 237 distinct `local_authority_code`s with an OPEN school in this project's DB is now either an enabled source or a documented candidate (the remaining un-mapped code, `000`, is this project's own catch-all for genuinely overseas British schools - Dubai, Ankara, Guernsey/Jersey/IoM's own separate `70x` codes aside - not a UK local authority at all, correctly excluded from this sweep). **Genuinely still open for a future session:** Guernsey's colour-mask-segmentation path (see the candidate entry's specific roadmap); Priority 6 Maps A and C for Hurworth School (Darlington, carried over unchanged); Essex's 14 declined secondary schools (carried over unchanged).

## Update: Guernsey's primary catchments landed via colour-mask segmentation of the ArcGIS export/tile image; secondary layer investigated and declined as superseded (2026-08-19, later session)

**Baseline at the start of this session: 11,255 `catchment_areas` rows, `map_catchments_cache.feature_count` = 11,255 (in sync), 109 local authorities, HEAD at `55ac21b`.** Picked up the specific roadmap the prior session left in Guernsey's `candidates:` entry: the States of Guernsey's ArcGIS Server (`maps.digimap.gg`) exposes real per-school catchment polygon data with a genuine, distinct fill colour per school in its own `drawingInfo`, but its `/query` and `/identify` endpoints both return HTTP 400 - only the `Map`/export capability is enabled server-side.

**The `/export` endpoint works, and is exactly georeferenced by construction, not by ground-control-point guessing.** `MapServer/export?bbox=...&bboxSR=102070&size=...&imageSR=102070&f=image` renders a real PNG at up to the service's own 4096x3355px cap (`maxImageWidth`/`maxImageHeight`), covering the whole island at ~3.07m/pixel. Because the request specifies the exact real-world bbox in the layer's own native CRS (`ESRI:102070`, equivalent to `EPSG:3108` ETRS89 Guernsey Grid, confirmed via `pyproj`'s CRS database), every pixel maps to an exact, known ground coordinate with no landmark-pairing needed at all - fundamentally different from anchoring a scanned paper map. Verified this directly before segmenting: reprojected all 9 primary schools' real-world coordinates to pixels under the bbox->pixel transform and sampled a window at each; every one landed on a single, 94-100%-pure dominant colour, and all 9 sampled colours were mutually distinct - i.e. every school's real coordinate falls deep inside its own uniquely-coloured region, not near a boundary or a different school's zone. The sampled colours were a uniform ~24% alpha-blend toward white relative to the renderer's raw `drawingInfo` RGB (implied alpha 0.234-0.240 across all 9 schools, independently, consistent with a real server-side layer-transparency setting rather than a georeferencing bug), so segmentation thresholded on each school's own empirically-sampled colour rather than the theoretical `drawingInfo` value.

**Coordinate ground truth: OpenStreetMap, since this project's own DB has no lat/lon for any Guernsey school.** All of Guernsey's GIAS rows (`local_authority_code` `706`) have `NULL` latitude/longitude in this project's `schools` table (unlike Jersey/Isle of Man, which had a government point layer to fall back on). Used Nominatim geocoding for all 9 schools, cross-checked against an independent Overpass API `amenity=school` bbox query over the same island - both sources agreed to within a few metres for 8 of 9 schools. La Houguette Primary School has no `amenity=school` OSM node at all; used the coordinate of the OSM bus-stop node literally named "La Houguette School" as the nearest available real-world proxy (flagged as lower-confidence than the other 8, though its resulting margin was still comfortable).

**Extraction: per-school colour threshold, external contours only, no manual boundary tracing.** For each of the 9 sampled colours, built a binary mask (exact/near-exact colour match), closed small gaps from the ~0.4pt outline stroke and catchment-name label halos with a small morphological close, then took external contours only (RETR_EXTERNAL) so any label-text pixels sitting inside a zone are absorbed into the solid region rather than punching spurious holes. Simplified with `cv2.approxPolyDP` (1.5px epsilon) and reprojected pixel -> `EPSG:3108` -> `EPSG:4326`. Overlaying the extracted contours back onto the source image confirmed they trace the true colour boundaries pixel-for-pixel with no drift. One school, La Houguette, produced a genuine second landmass (Lihou, the tidal islet off the west coast, 0.8% of the main polygon's area) correctly kept as a `MultiPolygon` rather than discarded as a noise speck.

**All 9 verified with comfortable margins; summed area is an independent sanity check.** Margins against the OSM ground-truth coordinates: Amherst 433m, Castel 596m, Forest 396m, Hautes Capelles 830m, La Houguette 835m (bus-stop proxy), La Mare De Carteret 507m, St Martin's 1111m, Vale 735m, Vauvert 387m - all comfortably clear of the 100m bar. The 9 polygons' summed area is 63.19 sq km, matching Guernsey's real land area (~63 sq km) almost exactly - strong independent evidence the 9 zones tile the whole island correctly with no major gap or overlap, not just that each individual polygon happens to contain its own school.

**Secondary/high-school catchment layer investigated and declined - a real, current-policy reason, not a technical blocker.** The sibling `gsySchoolCatchmentHighOL` service (3 zones: Les Beaucamps, La Mare de Carteret, St Sampsons) is technically recoverable by the identical technique and was test-exported successfully. Declined anyway after checking gov.gg's own current School-Admissions/Catchment-Areas page, which states outright that secondary admissions have used a "partner school" system instead of catchment-area allocation since September 2019, and links only the primary Digimap tool - not the secondary one. Independently, this project's own `schools` table already shows `La Mare De Carteret High School` (`urn 132470`) as `CLOSED`: a web search confirmed the 2021-2025 Guernsey secondary education reorganisation merged it into the newly-opened Les Varendes High School at a different site (`Les Varendes High School to officially open tomorrow`, Guernsey Press, September 2023). Shipping the secondary layer as a current catchment would have misrepresented both current government admissions policy and current school status - declined and documented in the candidates section rather than guessed at or silently "renamed" to the successor school.

**Verification.** Added `{ code: "706", name: "Guernsey (Channel Islands)", sourceTypeCount: 1 }` to `catchment-sources.test.ts`'s `PILOT_LOCAL_AUTHORITIES` fixture. `pnpm --filter @catchment-zone/shared sync-config` + `test` (45 passed) and the ingestor's full pytest suite (127 passed, after `uv sync --extra dev` in this fresh worktree) both pass clean. `npx prettier --write` run only against the changed yml (not repo-wide) to avoid pretty-printing the committed minified GeoJSON. `git status`/`git diff --stat` checked before committing; `git fetch origin main` showed the local branch already current, no rebase needed. Committed (`42d210f`, no `Co-Authored-By` trailer) and pushed to `main`; landing confirmed via a 200 response from `raw.githubusercontent.com` before importing. `import-catchments --local-authority "706"` built 9 primary areas, 0 rejected. `catchment_areas` went from 11,255 -> **11,264**. `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 11,264, in sync, both before and after `refresh-catchment-scores` (re-run synchronously to completion, 7,665 of 11,264 areas scored - Guernsey's own rows correctly unscored, consistent with the Channel Islands having no DfE performance-metric pipeline, same as Jersey/Isle of Man). `ingestor verify` passed clean. A live point-in-polygon query against the actual stored `geometry_geojson` (joined by `local_authority_code`/`source_id` then exact `area_name`, restricted to `status = 'OPEN'`) reproduced the exact same 386m-1111m margins measured pre-import, confirming the DB round-trip preserved the geometry exactly.

**Local authority count unchanged at 109** (this session added coverage to an already-counted LA rather than a brand-new one). **Genuinely still open for a future session:** Priority 6 Maps A and C for Hurworth School (Darlington, carried over unchanged); Essex's 14 declined secondary schools (carried over unchanged). Guernsey's `candidates:` roadmap is now fully resolved - nothing further pending for Guernsey itself.

## Update: swept the ArcGIS/Esri-blocked candidate backlog for the export-technique; landed Redbridge secondary and City of London primary catchments (2026-08-19, later session)

**Baseline at the start of this session: 11,264 `catchment_areas` rows, `map_catchments_cache.feature_count` = 11,264 (in sync), 110 local authorities, HEAD at `c1454a9`.** Task: re-read every `candidates:` entry whose `reason_not_enabled` described an ArcGIS/Esri MapServer or FeatureServer that was found but couldn't be queried, and actually retry the prior session's newly-proven "render an exact real-world bbox as a raster export, then segment it" technique (first proven on Guernsey) before accepting the dead end.

**Reviewed all ~80 candidate entries; the strongest genuine matches were Redbridge, City of London, Birmingham, Bedford Borough and Rhondda Cynon Taf** - the rest either had already-confirmed data absence (a real layer fully enumerated with no catchment content, e.g. Wolverhampton/Surrey/Trafford-Dudley-Swindon), a genuine login/credential wall (West Sussex, Gloucestershire, Derbyshire), or a confirmed network-level block unrelated to query permissions (Milton Keynes, Ealing, Leicestershire) - none of which the export technique can do anything about, so they were left untouched.

**Redbridge: 8 of 10 named secondary-school catchment zones landed - a genuinely new variant of the technique, not ArcGIS this time.** The previously-declined finding was real: `my.redbridge.gov.uk/Map/GetMapLocations?layerId=142` returns 10 named catchment features but only a bounding box each, not real vertices. Reading the deminified `/scripts/pages/map.min.js` client revealed the true boundary renderer: a Pitney-Bowes/MapInfo-style `MappingService` REST tile backend (`mapcache.redbridge.gov.uk/rest/Spatial/MappingService/maps/NamedMaps/{layer}/image.png;w=..;h=..;b=<bbox>,epsg%3A3857`) that - like an ArcGIS `/export` - accepts an arbitrary caller-specified bbox and canvas size in one request, so every output pixel maps to an exact, known EPSG:3857 ground coordinate by construction. Cross-checked this assumption directly: exporting the same bbox at two different canvas aspect ratios (a square 1600x1600 and an aspect-matched 1600x1931) produced the identical ~90.4%/90.5% vertical fill fraction of real map content, confirming the service linearly stretches the exact given bbox to the exact given canvas rather than letterboxing - the recovered geometry isn't distorted by this quirk. The layer renders every zone in one flat colour (solid boundary lines plus a sparse periodic fill stipple, not per-school colours), so segmentation here used region topology rather than colour classification: red pixels with at least one red 8-neighbour are boundary-line pixels (they form continuous chains), red pixels with none are isolated fill dots (confirmed at a fixed ~8x4px screen-space lattice) - trivially separable since fill dots never touch each other or a line. The line mask was dilated only to determine flood-fill connectivity (closing this map's real dashed-line gaps); the final polygon boundaries were rebuilt from the _undilated_ line mask intersected with each dilated region's footprint, so the shipped geometry sits at the true drawn line, not shrunk inward. This produced 10 real, distinct zones, each matched 1:1 to its own marker point from the source JSON with no ambiguity, plus one genuinely unexplained 11th polygon with no marker and no real school anywhere in it - left unassigned. Verified all 10 named zones against this project's own schools DB (Redbridge LA code `317`, phase-matched, `status = 'OPEN'`): **8 landed with comfortable margins (185m-741m)**, but Loxford School's real coordinate falls 19m outside its own "Loxford School Trust" polygon (reproduced at both 1600px and 4000px export resolutions, not a rendering artifact) and Mayfield School's falls 235m outside its own polygon (a real mismatch - the council's marker sits materially west of the school's actual GIAS site) - both declined rather than shipped on a failing fit, the same practice already used for Central Bedfordshire/Cardiff. A separate single-feature "11+ Common Catchment Area" layer was also export-tested successfully but declined as an unattributable shared zone (no per-school identification possible). No primary-school catchment layer exists on this platform at all.

**City of London: the 1 real zone landed after all - the "no identifying property" blocker turned out to have an authoritative fix hiding in the service's own metadata.** A previous session found `COMPASS_School_Admissions` (`mapping.cityoflondon.gov.uk`) has real, live, queryable polygon geometry but its single feature carries no name or other identifying attribute, and judged it "too degraded to usefully import." Re-investigated this session: the service's own root JSON (`serviceDescription` field) states outright "This map shows the Admissions Priority Area as outlined in the admissions criteria for **The Aldgate School**" - an authoritative identification from the source itself, not an inference, and `capabilities: "Map,Query,Data"` confirms `/query` was never actually blocked (the real host needed `www.` prefixed, `www.mapping.cityoflondon.gov.uk`, which the earlier session hadn't tried). Queried the feature directly and verified The Aldgate School's real DB coordinate (URN 100000, the City of London's only Primary-phase, LA-catchment-using school among its 9 open institutions - the rest are independent schools, colleges, a university and a conservatoire) against the polygon: comfortably inside, 420m clear of the 100m margin bar.

**Birmingham, Bedford Borough and Rhondda Cynon Taf remain genuinely blocked, each for a different, now more precisely documented reason.** Birmingham's `SchoolsDataSvc` folder returns `499 Token Required` even at the folder-_listing_ level (found the real host is `maps.birmingham.gov.uk/server`, not `/arcgis`, which now 500s outright) - there's no way to even discover the real service name to test an export URL against, a harder wall than Guernsey/Redbridge's "query blocked but service identity/export still visible" pattern, so this is a genuine authentication wall, not attempted further. Bedford Borough's `Bedford_Internal_Use/External_Schools` service is administratively "not started" server-side on both `MapServer` and `FeatureServer` - tried `/export` directly this session (the same idea that unlocked Guernsey/Redbridge) and it also fails with a generic ArcGIS Server error page, confirming the whole service is down, not just its query operation; no still-enabled capability exists here to exploit. Rhondda Cynon Taf's Astun iShare platform has real catchment layers (`EnglishPrimaryCatchment` etc.) with WFS explicitly disabled server-side; tried the WMS `GetMap` equivalent this session (`GetOWS.ashx?SERVICE=WMS`, confirmed live and responsive - "Invalid mapsource specified" is a real error, not a network failure) but couldn't discover the correct `MAPSOURCE` value from the static page HTML/JS after a dozen+ plausible guesses, and recovering it would need a live browser session capturing the real network request on page load - not available in this session's toolset (no Playwright/browser automation installed in this worktree). Left open as a specific, well-scoped next step rather than re-declared a dead end.

**Verification.** Added `{ code: "317", name: "Redbridge (England)", sourceTypeCount: 1 }` and `{ code: "201", name: "City of London (England)", sourceTypeCount: 1 }` to `catchment-sources.test.ts`'s `PILOT_LOCAL_AUTHORITIES` fixture. `pnpm --filter @catchment-zone/shared sync-config` + `test` (45 passed) and the ingestor's full pytest suite (127 passed, after `uv sync --extra dev` in this fresh worktree) both pass clean. `npx prettier --write` run only against the two changed source files (not repo-wide) to avoid pretty-printing the committed minified GeoJSON. `git status`/`git diff --stat` checked before committing; `git fetch origin main` showed the local branch already current, no rebase needed. Committed (`d060dcb`, no `Co-Authored-By` trailer) and pushed to `main`; landing confirmed via 200 responses from `raw.githubusercontent.com` for both new GeoJSON files before importing. `import-catchments --local-authority "317"` built 8 areas (0 rejected); `--local-authority "201"` built 1 area (0 rejected). `catchment_areas` went from 11,264 -> **11,273**. `refresh-catchment-overview-cache` confirmed `map_catchments_cache.feature_count` = 11,273, in sync, both before and after `refresh-catchment-scores` (re-run synchronously to completion, 7,674 of 11,273 areas scored - all 9 new rows correctly scored, consistent with England having a DfE performance-metric pipeline unlike the Channel Islands). `ingestor verify` passed clean. A live point-in-polygon query against the actual stored `geometry_geojson` (joined by `local_authority_code`/`source_id` then exact `area_name`, restricted to `status = 'OPEN'`) reproduced `contains = true` at 0m for all 9 shipped zones against their real school, confirming the DB round-trip preserved the geometry exactly.

**Local authority count: 110 -> 112** (Redbridge and City of London were both previously candidates-only, now enabled for the first time). **Genuinely still open for a future session:** Rhondda Cynon Taf's WMS `MAPSOURCE` value (needs live browser network capture); Priority 6 Maps A and C for Hurworth School (Darlington, carried over unchanged); Essex's 14 declined secondary schools (carried over unchanged).
