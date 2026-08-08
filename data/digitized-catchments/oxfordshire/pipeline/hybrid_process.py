"""Digitise Oxfordshire's "hybrid" template: the same real raster OS-grid
basemap as the plain grid template (grid detected the same pixel-
autocorrelation way as oxon_lib/process_one), but with a GENUINE
vector-drawn boundary path and marker square in page.get_drawings()
instead of a boundary baked into the raster - much higher precision than
the pixel-contour method, since the exact vector coordinates are used
directly rather than an approximated raster contour.

Discovered 2026-08-08 investigating the 18 schools catchment-sources.yml
flagged as "source PDF no longer presents as the raster grid template":
these PDFs still have a completely real, visible OS grid (confirmed by
direct visual inspection and confirmed_grid_line_fraction) but
process_one.is_grid_template() rejects them because their boundary is a
real vector path (few n_images, some "saturated vector paths" found)
rather than because they lost their grid. This is a genuinely different
(better) sub-template, not a degraded/fake one - see
config/catchment-sources.yml's Oxfordshire notes for the full
investigation, and vector_boundary.py for the path-extraction/chaining
primitives this builds on.
"""
import numpy as np
import pymupdf
from pyproj import Transformer
from shapely.geometry import Polygon, MultiPolygon, Point
from shapely.ops import transform as shp_transform

from oxon_lib import cyan_mask_broad, reconcile_grid_period, confirmed_grid_line_fraction
from vector_boundary import (
    extract_vector_boundary_and_marker,
    find_all_rings,
    confirmed_grid_line_fraction_peaks,
)

t_wgs_to_osgb = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
t_osgb_to_wgs = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def render(pdf_path, dpi, page_index):
    doc = pymupdf.open(pdf_path)
    page = doc[page_index]
    pix = page.get_pixmap(dpi=dpi)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
    return page, arr


def process_hybrid(pdf_path, lat, lon, color, dpi=300, page_index=0):
    page, arr = render(pdf_path, dpi, page_index)

    mask = cyan_mask_broad(arr)
    colsum = mask.sum(axis=0).astype(float)
    rowsum = mask.sum(axis=1).astype(float)
    px, py = reconcile_grid_period(colsum, rowsum)
    if px is None:
        return {"ok": False, "reason": "no consistent grid period found (broad mask)"}
    frac_x, frac_y = confirmed_grid_line_fraction(mask, px, py)
    if frac_x < 0.5 or frac_y < 0.5:
        # Fixed-integer-stride phase search can drift out of phase on
        # tall/wide A3 pages (see confirmed_grid_line_fraction_peaks'
        # docstring) - fall back to the per-line-peak variant, which
        # validated correctly on every clear-cut known PASS/FAIL
        # Oxfordshire case available (including all known-fake files)
        # before being trusted here, rather than silently lowering the
        # threshold.
        frac_x, frac_y, n_x, n_y = confirmed_grid_line_fraction_peaks(mask, px, py)
        if frac_x < 0.5 or frac_y < 0.5 or n_x < 3 or n_y < 3:
            return {
                "ok": False,
                "reason": f"no real grid lines confirmed (frac_x={frac_x:.2f}, frac_y={frac_y:.2f}, "
                f"n_peaks=({n_x},{n_y}))",
            }

    segs, marker_pt = extract_vector_boundary_and_marker(page, color=color)
    if not segs:
        return {"ok": False, "reason": "no vector boundary segments found"}
    if marker_pt is None:
        return {"ok": False, "reason": "no vector marker found"}
    rings, leftover = find_all_rings(segs)
    if not rings:
        return {
            "ok": False,
            "reason": f"could not chain any closed ring from boundary segments ({len(leftover)} left over)",
        }
    if leftover:
        return {
            "ok": False,
            "reason": f"{len(rings)} ring(s) closed but {len(leftover)} segment(s) left over unchained - refusing to guess",
        }

    ring_polys = []
    for r in rings:
        p = Polygon(r)
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty and p.geom_type == "Polygon" and p.area > 0:
            ring_polys.append(p)
    if not ring_polys:
        return {"ok": False, "reason": "all candidate rings were empty/invalid after repair"}

    # A smaller ring fully inside a bigger one is a real geometric HOLE,
    # not a second disjoint area - found on Burford School's file, whose
    # designated area has a carved-out exclusion around Carterton (its
    # own separately-schooled town), visually confirmed as a ring
    # entirely enclosed within the main boundary, not a satellite area
    # like The Cooper School's genuinely separate second ring (Bicester
    # area + a disjoint Ot Moor-area zone). Resolve containment BEFORE
    # the small-ring size filter below - a real hole can legitimately be
    # small (Carterton's was ~5% of the main ring) and must not be
    # thrown out by the same threshold meant to catch spurious unrelated
    # shapes, since a dropped hole would silently stop being excluded
    # rather than just vanish harmlessly.
    ring_polys.sort(key=lambda p: -p.area)
    used = [False] * len(ring_polys)
    exterior_holes = []  # list of (exterior_poly, [hole_polys])
    for i, p in enumerate(ring_polys):
        if used[i]:
            continue
        holes = []
        for j in range(i + 1, len(ring_polys)):
            if used[j]:
                continue
            if p.contains(ring_polys[j]):
                holes.append(ring_polys[j])
                used[j] = True
        exterior_holes.append((p, holes))
        used[i] = True

    # Now apply the spurious-tiny-ring filter only to TOP-LEVEL exterior
    # candidates (never to an already-resolved hole) - some files carry
    # tiny, clearly-unrelated closed red/blue shapes (an unrelated small
    # map feature entirely outside the main boundary, confirmed visually
    # on The Marlborough CE School's file) picked up by the same colour
    # filter. Keep only exteriors that are at least 3% of the largest
    # exterior's area - a real satellite area (seen: ~37% of the main
    # ring on The Cooper School) clears this easily, while the spurious
    # ones seen so far (~0.06% and ~0.2% of their file's main ring) do
    # not.
    max_ext_area = max(p.area for p, _ in exterior_holes)
    kept_exteriors = [(p, h) for p, h in exterior_holes if p.area >= 0.03 * max_ext_area]
    dropped = len(exterior_holes) - len(kept_exteriors)

    polys = [Polygon(p.exterior.coords, [h.exterior.coords for h in holes]) for p, holes in kept_exteriors]
    poly_pt = polys[0] if len(polys) == 1 else MultiPolygon(polys)

    marker_shp = Point(marker_pt)
    marker_inside = poly_pt.contains(marker_shp) or poly_pt.distance(marker_shp) < 3
    if not marker_inside:
        return {"ok": False, "reason": f"marker not inside vector boundary (dist={poly_pt.distance(marker_shp):.1f}pt)"}

    # Grid spacing detected in pixel space at `dpi`; convert to PDF
    # point space (72pt/inch) so boundary/marker (already in point
    # space) and grid scale share the same units.
    pt_per_1000m_x = px * 72.0 / dpi
    pt_per_1000m_y = py * 72.0 / dpi

    E_school, N_school = t_wgs_to_osgb.transform(lon, lat)
    mx_pt, my_pt = marker_pt

    def pt_to_osgb(x, y):
        E = E_school + (x - mx_pt) * 1000.0 / pt_per_1000m_x
        N = N_school - (y - my_pt) * 1000.0 / pt_per_1000m_y
        return E, N

    poly_osgb = shp_transform(pt_to_osgb, poly_pt)
    if not poly_osgb.is_valid:
        poly_osgb = poly_osgb.buffer(0)
    poly_wgs = shp_transform(lambda x, y: t_osgb_to_wgs.transform(x, y), poly_osgb)
    if not poly_wgs.is_valid:
        poly_wgs = poly_wgs.buffer(0)

    minx, miny, maxx, maxy = poly_wgs.bounds
    gb_ok = 49 <= miny <= 61 and 49 <= maxy <= 61 and -11 <= minx <= 2 and -11 <= maxx <= 2
    if not gb_ok:
        return {"ok": False, "reason": f"out of GB bounds {poly_wgs.bounds}"}

    area_km2 = poly_osgb.area / 1e6
    if area_km2 < 0.3 or area_km2 > 600:
        return {"ok": False, "reason": f"implausible area {area_km2:.2f}km2"}

    school_pt_wgs = Point(lon, lat)
    contains_school = poly_wgs.contains(school_pt_wgs) or poly_wgs.distance(school_pt_wgs) < 0.001
    if not contains_school:
        return {"ok": False, "reason": "school's own real DB coordinate falls outside the digitised boundary"}

    return {
        "ok": True,
        "poly": poly_wgs,
        "grid_px": px,
        "grid_py": py,
        "frac_x": frac_x,
        "frac_y": frac_y,
        "area_km2": area_km2,
        "contains_school_latlon": contains_school,
        "n_rings_kept": len(kept_exteriors),
        "n_rings_dropped": dropped,
        "n_holes": sum(len(h) for _, h in kept_exteriors),
    }


if __name__ == "__main__":
    import sys

    fp, latf, lonf, color = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    r = process_hybrid(fp, latf, lonf, color)
    if r["ok"]:
        print(
            f"OK area={r['area_km2']:.2f}km2 grid=({r['grid_px']:.1f},{r['grid_py']:.1f}) "
            f"frac=({r['frac_x']:.2f},{r['frac_y']:.2f}) rings_kept={r['n_rings_kept']} "
            f"rings_dropped={r['n_rings_dropped']} holes={r['n_holes']} "
            f"contains_school={r['contains_school_latlon']}"
        )
    else:
        print("FAIL", r["reason"])
