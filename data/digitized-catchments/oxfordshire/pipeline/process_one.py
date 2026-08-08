"""Per-file processing for Oxfordshire's OS-grid-referenced "Location and
Designated Area" PDF template (see oxon_lib.py for the rendering/grid/
marker/boundary detection primitives this builds on).

IMPORTANT template-detection lesson (found the hard way in a 2026-08-08
session): Oxfordshire's ~207 real per-school PDFs are NOT all the same
template. Two exist:

  - The OS 1:1250-raster grid template this module targets: ~150-165
    embedded raster tiles per page (get_images()), essentially no real
    vector paths (get_drawings() has at most a page-border rectangle),
    and a real cyan 1km grid baked into the raster that the functions
    below can measure for scale.
  - A newer, non-gridded cream/yellow OS-OpenData-style template: far
    fewer images (single digits to ~25) and the boundary/marker ARE
    real vector-drawn PDF paths (get_drawings() contains a saturated-
    blue/red polygon with hundreds of line segments) - see the
    landmark-pair method documented in config/catchment-sources.yml
    for how this template should actually be digitised (it has no grid
    at all, so grid_spacing_px has nothing real to find).

A session tried a "joint autocorrelation fallback" to rescue files where
grid_spacing_px's independent x/y peaks disagreed, on the theory that a
combined column+row search would be more robust. It was NOT: tested
against several non-gridded-template files, it confidently reported a
plausible-looking but entirely fabricated "grid" period, produced from
sparse unrelated cyan pixels (anti-aliasing, water features) rather than
a real grid - verified wrong by rendering the claimed grid over the
actual page image and seeing it line up with nothing. Five schools in an
earlier commit this same session were digitised this way by mistake
(via a lucky-looking but equally coincidental x/y agreement, not the
joint fallback specifically) and had to be pulled back out once this was
understood - see the git history around 2026-08-08 for the correction.
Lesson: NEVER attempt grid-based digitisation on a file without first
confirming via is_grid_template() that it actually has a raster grid.
The joint-fallback function still exists in oxon_lib.py for reference
but must not be wired into process() below without a much stronger,
independently-verified confidence signal than it had.

Given a downloaded PDF, the school's own real DB coordinate (lat/lon) and
the boundary/marker line colour ("blue" for primary schools, "red" for
secondary in the templates seen so far), process() does the following on
a confirmed grid-template file only:

  1. Renders the PDF page to a raster image at a given DPI.
  2. Detects the OS 1km cyan grid line spacing in pixels (the map's scale),
     rejecting the result if the detected x/y spacings disagree by more
     than 3% (a sign the autocorrelation locked onto the wrong periodic
     feature) or no clean autocorrelation peak is found at all.
  3. Finds the boundary outline (large low-fill-ratio connected component)
     and candidate marker icons (small high-fill-ratio components) in the
     given colour, via OpenCV connected-component labelling.
  4. Fills the boundary outline (morphological close + flood-fill) to get
     a pixel-space polygon mask, and picks the marker candidate with the
     largest area as "the" school marker.
  5. Verifies the marker centroid actually falls inside (or right on) the
     traced boundary polygon in pixel space - this is the per-file
     correctness check; if the marker isn't inside its own boundary,
     something detected is wrong and the file is rejected rather than
     guessed at. NOTE this check alone cannot catch a wrong SCALE (only
     a wrong anchor point), which is exactly how the joint-fallback
     false positives above slipped through it - the template guard is
     the check that actually matters for scale correctness.
  6. Anchors the pixel-space polygon to real-world OSGB36 (EPSG:27700)
     eastings/northings using the marker's real lat/lon (converted to
     OSGB36) as the origin and the detected grid spacing as the
     px-per-1000m scale factor, then reprojects to WGS84.
  7. Sanity-checks the result is within Great Britain's bounding box and
     that the implied catchment area is a plausible size.

Returns a dict with ok=True and the polygon (plus diagnostics) on success,
or ok=False and a human-readable reason on failure - callers should log
the reason rather than silently skip, so per-file debugging (the bulk of
the remaining Oxfordshire work) has something concrete to act on.
"""

from __future__ import annotations

import numpy as np
import pymupdf
from pyproj import Transformer
from shapely.geometry import Point, Polygon, mapping
from shapely.ops import transform as shp_transform

from oxon_lib import (
    confirmed_grid_line_fraction,
    fill_boundary,
    find_marker_and_boundary,
    polygon_from_mask,
    render,
)

t_wgs_to_osgb = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
t_osgb_to_wgs = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)

#: Confirmed grid-template files in this batch have 140-165 raster tiles
#: per page; confirmed vector-template files have well under 30. 80 is a
#: comfortable midpoint margin, not a tuned boundary.
GRID_TEMPLATE_MIN_IMAGES = 80


def is_grid_template(pdf_path: str, page_index: int = 0) -> tuple[bool, str]:
    """Returns (is_grid, diagnostic). Distinguishes the raster grid
    template (many embedded image tiles, no real vector boundary path)
    from the newer vector-drawn non-gridded template (few images, a real
    saturated-colour vector path in get_drawings()) - see module
    docstring for why this check is load-bearing, not a nice-to-have."""
    doc = pymupdf.open(pdf_path)
    page = doc[page_index]
    n_images = len(page.get_images())
    drawings = page.get_drawings()
    saturated_vector_paths = [
        d
        for d in drawings
        if d.get("color")
        and len(d["items"]) > 20
        and (
            (d["color"][2] > 0.5 and (d["color"][0] or 0) < 0.3)  # blue-ish
            or (d["color"][0] > 0.5 and (d["color"][2] or 0) < 0.3)  # red-ish
        )
    ]
    if n_images >= GRID_TEMPLATE_MIN_IMAGES and not saturated_vector_paths:
        return True, f"n_images={n_images}, no saturated vector boundary path"
    return (
        False,
        f"n_images={n_images} (<{GRID_TEMPLATE_MIN_IMAGES}) or "
        f"{len(saturated_vector_paths)} saturated vector path(s) found - looks like the "
        "non-gridded vector template, not the grid template",
    )


def grid_spacing_px(arr, min_p=180, max_p=950):
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)
    cyan = (b > 200) & (g > 140) & (g < 230) & (r < 160) & (r > 10)
    colsum = cyan.sum(axis=0).astype(float)
    rowsum = cyan.sum(axis=1).astype(float)

    def period(signal):
        s = signal - signal.mean()
        n = len(s)
        ac = np.correlate(s, s, mode="full")[n - 1 :]
        peaks = []
        for p in range(min_p, min(max_p, n - 1)):
            if ac[p] > ac[p - 1] and ac[p] > ac[p + 1]:
                peaks.append((p, ac[p]))
        if not peaks:
            return None
        peaks.sort(key=lambda t: -t[1])
        tallest = peaks[0][1]
        cands = [p for p, h in peaks if h >= 0.5 * tallest]
        return min(cands)

    return period(colsum), period(rowsum), cyan


def process(pdf_path, lat, lon, color, dpi=300, page_index=0):
    is_grid, diag = is_grid_template(pdf_path, page_index=page_index)
    if not is_grid:
        return {"ok": False, "reason": f"not a grid-template file ({diag})"}

    arr = render(pdf_path, dpi=dpi, page_index=page_index)
    px, py, cyan_mask = grid_spacing_px(arr)
    if px is None or py is None:
        return {"ok": False, "reason": "no grid peak"}
    diff = abs(px - py) / max(px, py)
    if diff > 0.03:
        return {"ok": False, "reason": f"grid x/y mismatch {px} vs {py}"}

    # THE decisive safety check - see confirmed_grid_line_fraction's
    # docstring. Even after is_grid_template() and a clean x/y agreement,
    # a 2026-08-08 session found 13 of 15 previously-"verified" schools
    # were false positives from a third template variant (140+ raster
    # tiles like the real grid template, but genuinely no grid drawn on
    # it) - x/y agreement alone can occur by coincidence on scattered
    # cyan content across a wide search range. This check confirms real,
    # near-continuous grid LINES exist at the claimed spacing, not just
    # a matching pixel-sum coincidence. Threshold 0.7 (not 1.0): real
    # grid files score at/near 1.0 but a line crossing dense map content
    # (buildings, text) can legitimately lose a little coverage.
    line_frac_x, line_frac_y = confirmed_grid_line_fraction(cyan_mask, px, py)
    if line_frac_x < 0.7 or line_frac_y < 0.7:
        return {
            "ok": False,
            "reason": (
                f"no real grid lines confirmed at px={px},py={py} "
                f"(line_frac_x={line_frac_x:.2f}, line_frac_y={line_frac_y:.2f})"
            ),
        }

    boundary, markers, labels, comps = find_marker_and_boundary(arr, color=color)
    if boundary is None:
        return {"ok": False, "reason": "no boundary component found"}
    if not markers:
        return {"ok": False, "reason": "no marker candidates found"}
    marker = max(markers, key=lambda c: c["area"])

    filled = fill_boundary(labels, boundary["label"])
    poly_px = polygon_from_mask(filled)
    if poly_px is None:
        return {"ok": False, "reason": "polygon extraction failed"}

    mx_px, my_px = marker["centroid"]
    marker_pt = Point(mx_px, my_px)
    marker_inside = poly_px.contains(marker_pt) or poly_px.distance(marker_pt) < 5
    if not marker_inside:
        return {
            "ok": False,
            "reason": f"marker not inside pixel-space boundary (dist={poly_px.distance(marker_pt):.1f}px)",
        }

    E_school, N_school = t_wgs_to_osgb.transform(lon, lat)

    def px_to_osgb(x, y):
        E = E_school + (x - mx_px) * 1000.0 / px
        N = N_school - (y - my_px) * 1000.0 / py
        return E, N

    coords_osgb = [px_to_osgb(x, y) for x, y in poly_px.exterior.coords]
    poly_osgb = Polygon(coords_osgb)
    poly_wgs = shp_transform(lambda x, y: t_osgb_to_wgs.transform(x, y), poly_osgb)
    if not poly_wgs.is_valid:
        poly_wgs = poly_wgs.buffer(0)

    minx, miny, maxx, maxy = poly_wgs.bounds
    gb_ok = 49 <= miny <= 61 and 49 <= maxy <= 61 and -11 <= minx <= 2 and -11 <= maxx <= 2
    if not gb_ok:
        return {"ok": False, "reason": f"out of GB bounds {poly_wgs.bounds}"}

    area_km2 = poly_osgb.area / 1e6
    # Oxfordshire's own catchments digitised so far (grid template, all
    # sessions) range roughly 1-160km2 for primary and 15-300km2 for
    # secondary; anything wildly outside that is rejected rather than
    # trusted blind.
    if area_km2 < 0.3 or area_km2 > 600:
        return {"ok": False, "reason": f"implausible area {area_km2:.2f}km2 (grid px={px:.1f})"}

    return {
        "ok": True,
        "poly": poly_wgs,
        "grid_px": px,
        "grid_py": py,
        "marker_px": (mx_px, my_px),
        "boundary_bbox": boundary["bbox"],
        "area_km2": area_km2,
    }
