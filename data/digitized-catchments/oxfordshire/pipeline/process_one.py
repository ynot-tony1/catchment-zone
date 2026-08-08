"""Per-file processing for Oxfordshire's OS-grid-referenced "Location and
Designated Area" PDF template (see oxon_lib.py for the rendering/grid/
marker/boundary detection primitives this builds on).

Given a downloaded PDF, the school's own real DB coordinate (lat/lon) and
the boundary/marker line colour ("blue" for primary schools, "red" for
secondary in the templates seen so far), this:

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
     guessed at.
  6. Anchors the pixel-space polygon to real-world OSGB36 (EPSG:27700)
     eastings/northings using the marker's real lat/lon (converted to
     OSGB36) as the origin and the detected grid spacing as the
     px-per-1000m scale factor, then reprojects to WGS84.
  7. Sanity-checks the result is within Great Britain's bounding box.

Returns a dict with ok=True and the polygon (plus diagnostics) on success,
or ok=False and a human-readable reason on failure - callers should log
the reason rather than silently skip, so per-file debugging (the bulk of
the remaining Oxfordshire work) has something concrete to act on.
"""

from __future__ import annotations

import numpy as np
from pyproj import Transformer
from shapely.geometry import Point, Polygon, mapping
from shapely.ops import transform as shp_transform

from oxon_lib import fill_boundary, find_marker_and_boundary, polygon_from_mask, render

t_wgs_to_osgb = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
t_osgb_to_wgs = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


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
    arr = render(pdf_path, dpi=dpi, page_index=page_index)
    px, py, cyan_mask = grid_spacing_px(arr)
    if px is None or py is None:
        return {"ok": False, "reason": "no grid peak"}
    diff = abs(px - py) / max(px, py)
    if diff > 0.03:
        return {"ok": False, "reason": f"grid x/y mismatch {px} vs {py}"}

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

    return {
        "ok": True,
        "poly": poly_wgs,
        "grid_px": px,
        "grid_py": py,
        "marker_px": (mx_px, my_px),
        "boundary_bbox": boundary["bbox"],
        "area_km2": poly_osgb.area / 1e6,
    }
