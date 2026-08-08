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
