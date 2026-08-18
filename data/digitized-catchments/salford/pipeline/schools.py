"""Metadata for Salford's per-school parish/catchment boundary PDFs.

Each entry maps a school to its source PDF (on salford.gov.uk), its real
DB (GIAS) URN and coordinate (the anchor for `grid_digitise.digitise`), and
whether it was actually landed this session. `pdf_url` is the real source;
PDFs themselves are not committed to this repo (matches this project's
existing convention of not committing large source documents) - re-download
from `pdf_url` to re-run the pipeline.

`manual_spacing_px`, where set, means automatic dual-axis grid-spacing
detection could not be trusted from this file alone (see comments below);
the value used was cross-checked against another Salford source page that
shares the identical underlying base map/extent, and independently
verified safe via containment-margin robustness across the full plausible
spacing range (400-1000px/km all gave a comfortable positive margin) -
never an invented or unverified figure.
"""

BASE_URL = "https://www.salford.gov.uk"

# The 7 already landed in the previous (2026-08-18 "Salford reopened")
# session - not re-attempted here.
ALREADY_LANDED = {
    "christ-church-cofe",
    "st-charles-rc",
    "st-edmunds-rc",
    "st-lukes-rc",
    "st-marks-rc",
    "st-teresas-rc",
    "holy-family-rc",
}

# This session's 17 remaining candidates.
SCHOOLS = {
    "all-hallows": dict(
        urn="131512",
        db_school_name="All Hallows RC High School",
        lon=-2.314724798156515,
        lat=53.49111837601124,
        phase="secondary",
        pdf_url=f"{BASE_URL}/media/387500/all-hallows-rc-boundary-map.pdf",
        landed=False,
        decline_reason=(
            "Grid and star detection both clean (spacing confirmed on both "
            "axes, single unambiguous blue star), but the resulting polygon "
            "misses the school's own real DB coordinate by ~31m - a genuine "
            "near-miss, not a detection bug (col/row spacing agreed to "
            "0.3%). Declined per this project's comfortable-margin rule "
            "rather than forcing a borderline fit.\n"
            "Re-examined 2026-08-18 (affine-refit session, same pass that "
            "fixed Ellesmere Park): this PDF only shows the target school "
            "itself (key literally states 'blue star - All Hallows RC High "
            "School / black line - parish boundary') - no other named "
            "school is plotted on the page, so unlike Ellesmere Park there "
            "is no second/third real DB-coordinate GCP available for an "
            "affine or grid-disambiguation fit here. Checked whether the "
            "grid itself carries any measurable rotation/skew that a pure "
            "north-up similarity fit would miss: sampled the same "
            "confirmed vertical grid line's x-position across 22 evenly "
            "spaced horizontal bands spanning the full page height - "
            "slope was 0.0013 px drift per px of height (~6px of drift "
            "over the whole ~4500px page), i.e. genuinely vertical, not a "
            "rotation problem. Also tried anchoring purely from the grid "
            "(bypassing the star anchor entirely, Barton-Park-style) using "
            "the school's own approximate DB coordinate only to pick which "
            "1000m grid square: this predicts the star's own on-page "
            "position 232m from its DB coordinate, i.e. WORSE than the "
            "31m the original star-forced-exact-to-DB anchor achieves - "
            "confirming the anchor/translation method isn't the weak "
            "point here. Zoomed into the source PDF around the star "
            "(1:1 pixel crop): the school's own drawn star marker sits "
            "essentially ON the printed black boundary line itself (its "
            "lower point touches the line where the boundary bends), not "
            "clearly inside or outside it - a genuine near-boundary siting "
            "in the source cartography itself, not a digitisation "
            "artefact. No refinement of the transform can manufacture a "
            "confident 100m+ margin out of a source document that draws "
            "the school right on its own catchment line. Confirmed still "
            "unsolvable with this project's available techniques; left "
            "declined."
        ),
    ),
    "christ-the-king": dict(
        urn="105950",
        db_school_name="Christ The King RC Primary School",
        lon=-2.389989625074614,
        lat=53.521762700347495,
        phase="primary",
        pdf_url=f"{BASE_URL}/media/381325/christ-the-king-rc-boundary-map.pdf",
        landed=True,
    ),
    "ellesmere-park": dict(
        urn="144200",
        db_school_name="Ellesmere Park High School",
        lon=-2.334240329542372,
        lat=53.49268327844783,
        phase="secondary",
        pdf_url=f"{BASE_URL}/media/0e0mbrbw/ellesmere-park-catchment-area.pdf",
        landed=True,
        landed_note=(
            "Re-attempted 2026-08-18 (affine-refit session): the previous "
            "single-star-anchor near-miss (~104m) was fixed not by a raw "
            "3-point affine on noisy star pixel-picks (tried first: gave a "
            "137-184m cross-check residual, no better) but by using this "
            "map's other 3 gold-star-marked schools - All Hallows RC High "
            "School (own real DB coord, URN 131512), St Patrick's RC High "
            "School (URN 105986) and Salford City Academy (URN 135071), "
            "all plotted on the same page for context and all queried "
            "fresh from the live DB - as ground-control points to "
            "DISAMBIGUATE the absolute georeference of this page's own "
            "confirmed real OS grid (630/632px spacing, 7 corroborating "
            "gap measurements, already well-established), rather than to "
            "anchor a fitted affine directly. Fit x=a*E+c / y=b*N+d "
            "independently per axis from the grid line pixel positions "
            "(5 columns, 4 rows; sub-3px residuals on the grid fit itself, "
            "i.e. essentially exact) after using the 3 GCP schools to pin "
            "down which 1000m grid square each line falls in (each GCP's "
            "predicted pixel position landed 39-124m from its actual "
            "star, consistent with this project's documented GIAS "
            "DB-coordinate siting noise, not a transform error - the grid "
            "fit alone is far tighter than that). This deterministic-grid "
            "approach (no single-marker anchor at all) is the same "
            "upgrade already proven for Oxfordshire's Barton Park Primary. "
            "Boundary extracted via the red-line colour mask; needed a "
            "wider morphological close (41x41, not the default 9x9) than "
            "usual to bridge gaps where large school-name text labels "
            "overlap the printed boundary line - verified safe by "
            "flood-filling from an interior point and confirming it no "
            "longer leaks to the full canvas at this kernel size, and "
            "that the enclosed pixel count is stable across kernel sizes "
            "41-121. Traced ring visually matches the source PDF's red "
            "line. Area 6.34km2. DB coordinate contained, margin 397.9m - "
            "comfortably clears this project's 100m+ bar (previous "
            "attempt missed by 104m). Landed in the new "
            "data/digitized-catchments/salford/salford_secondary_catchments.geojson "
            "(a separate file/source from the primary one, since this "
            "school is secondary phase and area_type must not be tagged "
            "primary for scoring purposes)."
        ),
    ),
    "holy-cross-all-saints": dict(
        urn="105952",
        db_school_name="Holy Cross and All Saints RC Primary School",
        lon=-2.353240843987402,
        lat=53.47745604587117,
        phase="primary",
        pdf_url=f"{BASE_URL}/media/394619/holy-cross-and-all-saints-rc-boundary-map-october-2019.pdf",
        landed=False,
        decline_reason=(
            "This PDF (and st-marys-eccles/st-marks-ce, uploaded under "
            "adjacent media IDs 394618-394620) uses a different, older "
            "basemap style with NO OS grid overlay at all - confirmed by "
            "direct pixel inspection, not just automatic-detection failure. "
            "The school is marked with a small red dot and text leader "
            "line, not a star. Without an independent grid to supply scale "
            "and rotation, this project's core method has no safe way to "
            "digitise this file - declined, not a dead end to retry with "
            "better thresholds."
        ),
    ),
    "st-gilberts": dict(
        urn="105954",
        db_school_name="St Gilbert's RC Primary School",
        lon=-2.370358591986553,
        lat=53.48453205933124,
        phase="primary",
        pdf_url=f"{BASE_URL}/media/381326/st-gilbertsrc-catchment-area.pdf",
        landed=False,
        decline_reason=(
            "A completely different source: a very high-resolution "
            "(9537x13483px) cadastral-style raster scan with a red boundary "
            "line and the school shown as a solid red-shaded building "
            "footprint (no star icon), and no OS grid overlay of any kind. "
            "No independent scale/rotation source available - declined."
        ),
    ),
    "st-josephs-ordsall": dict(
        urn="105965",
        db_school_name="St Joseph's RC Primary School",
        lon=-2.2786608652531344,
        lat=53.47555905997295,
        phase="primary",
        pdf_url=f"{BASE_URL}/media/381126/st-joseph-rc-ordsall-boundary-map.pdf",
        landed=True,
    ),
    "st-joseph-worker-irlam": dict(
        urn="105961",
        db_school_name="St Joseph the Worker RC Primary School",
        lon=-2.417390820184343,
        lat=53.453798013305715,
        phase="primary",
        pdf_url=f"{BASE_URL}/media/396051/st-joseph-the-worker-rc-boundary-map-march-2019v3.pdf",
        landed=True,
    ),
    "st-marks-ce": dict(
        urn="105949",
        db_school_name="St Mark's CofE Primary School",
        lon=-2.3826986848227314,
        lat=53.50438464636215,
        phase="primary",
        pdf_url=f"{BASE_URL}/media/394618/st-marks-ce-boundary-map-april-2019.pdf",
        landed=False,
        decline_reason=(
            "Titled 'Worsley ward map for school admission purposes only' - "
            "a different document type again: the school's position is "
            "given only as a plain text label with no star/dot marker at "
            "all, and (like its sibling uploads holy-cross-all-saints and "
            "st-marys-eccles) there is no OS grid overlay. No safe anchor "
            "or scale source - declined."
        ),
    ),
    "st-marys-eccles": dict(
        urn="105953",
        db_school_name="St Mary's RC Primary School (Eccles)",
        lon=-2.341302540216055,
        lat=53.48245240388145,
        phase="primary",
        pdf_url=f"{BASE_URL}/media/394620/st-marys-rc-eccles-october-2019.pdf",
        landed=False,
        decline_reason="Same no-grid/red-dot-marker style as holy-cross-all-saints - see that entry.",
    ),
    "st-marys-swinton": dict(
        urn="105957",
        db_school_name="St Mary's RC Primary School (Swinton)",
        lon=-2.331852797130668,
        lat=53.511197147317894,
        phase="primary",
        pdf_url=f"{BASE_URL}/media/381322/st-marys-rc-swinton-boundary-map.pdf",
        landed=True,
    ),
    "st-pauls-crompton": dict(
        urn="105945",
        db_school_name="St Paul's CofE Primary School (Crompton Street, Walkden)",
        lon=-2.385815613892371,
        lat=53.52219870701866,
        phase="primary",
        pdf_url=f"{BASE_URL}/media/381147/st-pauls-crompton-street-boundary-map.pdf",
        landed=True,
        landed_note=(
            "A third source type entirely: 'Digital map from Dotted Eyes... "
            "PS Licence No. 100019818. Church Commissioners' - a diocesan "
            "ecclesiastical-parish map product (magenta boundary, a real "
            "raster OS 1km grid baked into the basemap - fainter/greyer "
            "than the council's own cyan-grid template but genuine and "
            "square, spacing 1497px at 400dpi - and a small lettered 'B' "
            "symbol, ~640m from the school, most likely marking the "
            "parish church rather than the school itself) rather than the "
            "council's own OS OpenData basemap. Landed 2026-08-18 by "
            "extracting the boundary as a REAL VECTOR path (get_drawings() "
            "has 11 separate closed magenta rings - one per parish visible "
            "on this wide-area deanery sheet, not just the target parish; "
            "disambiguated by which ring's bounds match the huge loop "
            "dominating the page and by checking which ring, once "
            "georeferenced, plausibly contains the school) using the same "
            "segment-chaining approach as Oxfordshire's vector_boundary.py. "
            "Anchored the grid's absolute position via Nominatim/Overpass's "
            "'Blackleach Reservoir' polygon centroid (color-mask-extracted "
            "from the raster basemap and matched to the OSM way's own "
            "centroid) - implied grid-line eastings/northings landed within "
            "~15m of exact 1000m multiples (E=373000, N=404000 at the "
            "measured grid line pixels), strong confirmation. Independently "
            "cross-checked: under this transform, a building on the map "
            "explicitly labelled 'School' sits exactly on 'Crompton "
            "Street', pixel-matching the predicted position of the school's "
            "own real DB coordinate almost exactly. Traced ring overlays "
            "pixel-perfectly on the source PDF's printed magenta boundary "
            "line. Area 4.01km2, single clean Polygon. DB coordinate "
            "contained, margin 493m - comfortably clears this project's "
            "100m+ bar."
        ),
    ),
    "st-pauls-crosslane": dict(
        urn="147730",
        db_school_name="St Paul's CofE Primary School (Cross Lane)",
        lon=-2.279023351289323,
        lat=53.482578207054644,
        phase="primary",
        pdf_url=f"{BASE_URL}/media/381144/st-pauls-ce-cross-lane-boundary-map.pdf",
        landed=True,
        manual_spacing_px=647,
        manual_spacing_note=(
            "Only ONE vertical grid line survives cleanly on this page (the "
            "rest fall inside the large River Irwell/Salford Loop water "
            "feature or dense urban text); automatic dual-axis corroboration "
            "isn't possible from this file alone. This file and "
            "st-philips-ce are pixel-identical-dimension (4764x3368) renders "
            "of the same underlying basemap/extent (same River Irwell loop "
            "at the same pixel position) with different boundary overlays - "
            "this file's own clean row-gap measurement (640px, a single "
            "sharp peak ~25x stronger than any other candidate, not a "
            "marginal one) was used for both files. Independently verified "
            "safe: containment holds with a comfortable positive margin for "
            "both schools' own DB coordinates across the entire plausible "
            "spacing range (400-1000px/km), not just at the chosen value - "
            "so the result isn't sensitive to getting this single-axis "
            "reading exactly right."
        ),
    ),
    "st-peters-ce": dict(
        urn="105948",
        db_school_name="St Peter's CofE Primary School",
        lon=-2.3425053366698854,
        lat=53.51202098224438,
        phase="primary",
        pdf_url=f"{BASE_URL}/media/381317/st-peters-ce-boundary-map.pdf",
        landed=True,
    ),
    "st-philips-ce": dict(
        urn="105944",
        db_school_name="St Philip's CofE Primary School",
        lon=-2.26312317380596,
        lat=53.48219184641137,
        phase="primary",
        pdf_url=f"{BASE_URL}/media/381153/st-philips-ce-boundary-map.pdf",
        landed=True,
        manual_spacing_px=647,
        manual_spacing_note="See st-pauls-crosslane's manual_spacing_note - same shared basemap/reasoning.",
    ),
    "st-philips-rc": dict(
        urn="105968",
        db_school_name="St Philip's RC Primary School",
        lon=-2.26977802010779,
        lat=53.51689932097769,
        phase="primary",
        pdf_url=f"{BASE_URL}/media/381318/st-philips-rc-boundary-map.pdf",
        landed=True,
    ),
    "cathedral": dict(
        urn="105964",
        db_school_name="The Cathedral School of St Peter and St John RC Primary",
        lon=-2.2601093011486775,
        lat=53.487097158464806,
        phase="primary",
        pdf_url=f"{BASE_URL}/media/381174/the-cathedral-rc-boundary-map.pdf",
        landed=True,
    ),
    "st-thomas-canterbury": dict(
        urn="105970",
        db_school_name="St Thomas of Canterbury RC Primary School",
        lon=-2.251370713564493,
        lat=53.50531745871702,
        phase="primary",
        pdf_url=f"{BASE_URL}/media/381323/st-thomas-of-canterbury-rc-boundary-map.pdf",
        landed=True,
    ),
}
