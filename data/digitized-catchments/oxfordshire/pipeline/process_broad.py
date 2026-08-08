"""Grid-template processing using the BROADER cyan_mask_broad() +
reconcile_grid_period() combo from oxon_lib.py, for candidate schools
that fail process_one.process()'s narrower cyan detector. This mirrors
the already-documented 2026-08-08 re-verification finding (see
oxon_lib.py's cyan_mask_broad docstring) that several genuine grid files
render their OS 1km grid line in a paler cyan on a rural/topographic
basemap sub-variant that the narrow RGB mask misses, and that a real
period can be a harmonic-confused mismatch under independent per-axis
autocorrelation but resolve cleanly under reconcile_grid_period's shared-
period search.

Not wired into batch_process.py's default path; invoked standalone here
against files process_one.process() rejected, with the same
confirmed_grid_line_fraction() safety gate before anything is trusted.
"""
from __future__ import annotations

from pyproj import Transformer
from shapely.geometry import Point, Polygon
from shapely.ops import transform as shp_transform

from oxon_lib import (
    confirmed_grid_line_fraction,
    cyan_mask_broad,
    fill_boundary,
    find_marker_and_boundary,
    polygon_from_mask,
    reconcile_grid_period,
    render,
)

t_wgs_to_osgb = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
t_osgb_to_wgs = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def process_broad(pdf_path, lat, lon, color, dpi=300, page_index=0):
    arr = render(pdf_path, dpi=dpi, page_index=page_index)
    cyan_mask = cyan_mask_broad(arr)
    colsum = cyan_mask.sum(axis=0).astype(float)
    rowsum = cyan_mask.sum(axis=1).astype(float)
    px, py = reconcile_grid_period(colsum, rowsum)
    if px is None or py is None:
        return {"ok": False, "reason": "no reconciled grid period"}

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
