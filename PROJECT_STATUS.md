# Project status

Updated 2026-08-06. Reflects what has actually been run and verified on
disk, not what is intended.

## Completed and verified

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
