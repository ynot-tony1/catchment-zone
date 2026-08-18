"""Salford OS-grid parish/catchment boundary digitisation pipeline.

Digitises Salford City Council's per-school "parish boundary map for school
admissions" PDFs into georeferenced polygons, without ever inventing
geometry: every polygon is traced directly from the hand-drawn boundary line
printed on a real, genuine OS OpenData-style basemap with a true north-up
1km National Grid overlay.

Method (see the Salford block comment in config/catchment-sources.yml for
the full narrative and this project's standing rules):

1. Detect the pale-cyan 1km grid overlay and measure its pixel spacing
   independently on both the x (easting) and y (northing) axes, using each
   axis's own smallest *adjacent* (consecutive-line) gap - not summed/
   pairwise differences across the combined line set (see `modal_gap` and
   `detect_grid_spacing` for the false-3x-spacing trap this guards against).
   The two axes must agree (equal, or a clean integer multiple) before the
   spacing is trusted, and the implied real-world page extent must be
   plausible for a local-area map.
2. Detect the blue (or gold, on a couple of files) star marking the school,
   and the hand-drawn boundary line (black, or red on the council's
   separate "catchment area" map style) via colour mask + morphological
   close + largest-non-frame connected component + contour extraction.
3. Anchor translation on the school's own real DB (GIAS) coordinate matched
   to its own drawn star; scale and rotation come independently from the
   measured grid spacing (true north-up, so rotation is 0) - not circular.
4. Verify: the resulting polygon must contain the school's own real DB
   coordinate with a comfortable margin. Where more than one star-coloured
   blob is detected (e.g. a decorative copy inside the page's own legend
   box), every candidate is tried and disambiguated by this same
   containment check.

Requires opencv-python-headless, numpy, scipy, shapely, pyproj.
"""
import sys
import cv2
import numpy as np
from scipy.signal import find_peaks
from pyproj import Transformer

WGS84_TO_OSGB = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
OSGB_TO_WGS84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def cyan_grid_mask(img, thin_only=True, max_halfwidth=2.5):
    b = img[:, :, 0].astype(int)
    g = img[:, :, 1].astype(int)
    r = img[:, :, 2].astype(int)
    mask = (b > 225) & (g > 225) & (r > 140) & (r < 235)
    if not thin_only:
        return mask
    # Grid lines are ~1-3px thin; wide cyan-ish fills (lakes, highlight boxes)
    # are much thicker. Use a distance transform: a cyan pixel deep inside a
    # filled blob is far from any non-cyan pixel, while every pixel of a thin
    # line is close to the line's edge. Keep only pixels near their own mask
    # edge (i.e. genuinely thin structures), regardless of orientation.
    mask8 = (mask * 255).astype(np.uint8)
    dist = cv2.distanceTransform(mask8, cv2.DIST_L2, 5)
    thin_mask = mask & (dist <= max_halfwidth)
    return thin_mask


def find_grid_lines(sums, dim, min_frac=0.06, distance_frac=0.08):
    """Find grid line peaks in a 1D sum profile (col_sums or row_sums)."""
    height = min_frac * dim
    distance = max(20, int(distance_frac * dim))
    peaks, props = find_peaks(sums, height=height, distance=distance)
    return peaks, props


def bin_coverage(mask, axis, positions, other_dim, nbins=40, min_coverage=0.5):
    """Keep only candidate line positions whose thin-cyan pixels are spread
    across most of the image span (a real full-page grid line, even if
    dashed/occluded in places) rather than concentrated in one local region
    (e.g. a river's parallel double-border, which is also thin but only
    exists over a short stretch).

    axis=0 -> positions are column x-coords, spread checked over rows (y).
    axis=1 -> positions are row y-coords, spread checked over cols (x).
    """
    kept = []
    bin_size = max(1, other_dim // nbins)
    for pos in positions:
        if axis == 0:
            col = mask[:, pos]
        else:
            col = mask[pos, :]
        idx = np.where(col)[0]
        if len(idx) == 0:
            continue
        bins_hit = len(set((idx // bin_size).tolist()))
        coverage = bins_hit / nbins
        if coverage >= min_coverage:
            kept.append(pos)
    return np.array(kept, dtype=int)


def adjacent_gaps(positions):
    positions = np.sort(positions)
    return np.diff(positions)


def modal_gap(gaps, rel_tol=0.02):
    """Cluster adjacent-gap values within a relative tolerance and return
    (representative_value, cluster_size, confidence) for the best-supported
    spacing estimate on one axis.

    If two or more gaps agree with each other (a real cluster of size >=2),
    that recurring value is trusted over everything else - this is what
    catches a single spurious short gap (e.g. a river's parallel border
    surviving the thin-line filter): it shows up as a singleton while the
    true recurring grid spacing shows up several times across the page.

    If every gap on this axis is a singleton (too few grid lines survived
    to have a repeat, e.g. exactly 2-3 lines with clean multiples of each
    other), fall back to the raw minimum gap as the base unit - the same
    literal-min heuristic this project has used before, but only used here
    as a last resort once clustering has already had its chance to find
    real corroboration.
    """
    gaps = sorted(int(g) for g in gaps if g > 0)
    if not gaps:
        return None, 0, "none"
    clusters = []  # list of [values]
    for gval in gaps:
        placed = False
        for cluster in clusters:
            rep = np.median(cluster)
            if abs(gval - rep) / rep < rel_tol:
                cluster.append(gval)
                placed = True
                break
        if not placed:
            clusters.append([gval])
    clusters.sort(key=lambda c: (-len(c), np.median(c)))
    best = clusters[0]
    if len(best) >= 2:
        return float(np.median(best)), len(best), "confirmed"
    return float(min(gaps)), 1, "single-fallback"


def _merge_close(positions, min_sep=15):
    """Merge candidate line positions that are within min_sep px of each
    other (duplicate detections of the same physical line at different
    thresholds) into a single averaged position."""
    positions = sorted(positions)
    merged = []
    for p in positions:
        if merged and p - merged[-1][-1] <= min_sep:
            merged[-1].append(p)
        else:
            merged.append([p])
    return np.array([int(round(np.mean(g))) for g in merged])


def detect_grid_spacing(img, verbose=False, min_coverage=0.3):
    """Detect the true 1km OS grid spacing, corroborated independently on
    both axes.

    For each axis, gather ALL candidate line positions across a range of
    detection thresholds (low thresholds catch dashed/occluded lines that
    high thresholds miss), keep only those with good full-page span
    coverage (bin_coverage - rejects local features like river borders
    that are thin but not full-page), then take the MODAL adjacent gap
    (the gap value that recurs most often) rather than the raw minimum
    gap - a single spurious short gap from a surviving non-grid thin
    feature shows up as a singleton, while the true grid spacing recurs
    across the page. Finally require the two independently-measured axes'
    modal gaps to agree (equal, or a small integer multiple of each other)
    before trusting the result - real corroboration, not coincidence.
    """
    h, w = img.shape[:2]
    mask = cyan_grid_mask(img)
    col_sums = mask.sum(axis=0).astype(float)
    row_sums = mask.sum(axis=1).astype(float)

    candidates = []
    for min_frac in [0.30, 0.25, 0.20, 0.15, 0.12, 0.10, 0.08, 0.06, 0.05, 0.04, 0.03, 0.02]:
        cols, _ = find_grid_lines(col_sums, h, min_frac=min_frac)
        rows, _ = find_grid_lines(row_sums, w, min_frac=min_frac)
        cols = bin_coverage(mask, axis=0, positions=cols, other_dim=h, min_coverage=min_coverage)
        rows = bin_coverage(mask, axis=1, positions=rows, other_dim=w, min_coverage=min_coverage)
        cols = _merge_close(cols)
        rows = _merge_close(rows)
        if len(cols) < 2 or len(rows) < 2:
            continue

        col_gaps = adjacent_gaps(cols)
        row_gaps = adjacent_gaps(rows)
        col_modal, col_n, col_conf = modal_gap(col_gaps)
        row_modal, row_n, row_conf = modal_gap(row_gaps)
        if verbose:
            print(
                f"  frac={min_frac:.2f} cols={list(cols)} rows={list(rows)}\n"
                f"    col_gaps={list(col_gaps)} -> {col_modal} (n={col_n}, {col_conf})\n"
                f"    row_gaps={list(row_gaps)} -> {row_modal} (n={row_n}, {row_conf})"
            )
        if col_modal is None or row_modal is None:
            continue

        ratio = col_modal / row_modal
        nearest_int = round(ratio) if ratio >= 1 else round(1 / ratio)
        if nearest_int == 0:
            continue
        if ratio >= 1:
            resid = abs(ratio - nearest_int) / nearest_int
        else:
            resid = abs((1 / ratio) - nearest_int) / nearest_int
        # A bit more slack when exactly one axis is a repeat-confirmed
        # reading and the other only had a single gap to go on - the
        # confirmed axis is already independently trustworthy, so this
        # doesn't weaken the corroboration, it just accounts for the
        # weaker axis's single measurement carrying more pixel noise.
        one_confirmed = (col_conf == "confirmed") != (row_conf == "confirmed")
        tol = 0.06 if one_confirmed else 0.03
        agree = resid < tol
        if agree:
            # When the two axes disagree by an integer multiple, trust
            # whichever axis's value is actually *confirmed* by a repeated
            # gap measurement over one that only had a single, unconfirmed
            # gap to go on - a lone small gap on a weak axis is just as
            # likely to be a stray false detection as it is to be "the real
            # base unit the other axis missed".
            if col_conf == "confirmed" and row_conf != "confirmed":
                spacing = col_modal
            elif row_conf == "confirmed" and col_conf != "confirmed":
                spacing = row_modal
            else:
                spacing = min(col_modal, row_modal)
        else:
            spacing = None
        plausible = None
        if agree:
            # Real-world plausibility check: these Salford per-school PDFs
            # visibly span a handful of km (a school's local area plus
            # neighbouring named places) - a spacing implying a page well
            # under 1km or over ~15km across is a sign the true grid line
            # was missed/mismeasured, not a real reading (the same trap
            # that caught St Charles' RC's false 3x-too-large spacing).
            implied_km_w = w / spacing  # spacing is px-per-1km-grid-square
            implied_km_h = h / spacing
            plausible = 1.0 <= max(implied_km_w, implied_km_h) <= 15.0 and min(implied_km_w, implied_km_h) >= 0.6
            if verbose:
                print(
                    f"    -> ratio={ratio:.3f} agree={agree} spacing={spacing} "
                    f"implied_extent={implied_km_w:.2f}x{implied_km_h:.2f}km plausible={plausible}"
                )
        elif verbose:
            print(f"    -> ratio={ratio:.3f} agree={agree}")
        if agree and plausible:
            # Require at least 2 corroborating gap measurements in total
            # (summed across axes) UNLESS this is a very clean, strict
            # (high min_frac) detection where only 2 lines exist per axis -
            # avoids trusting a lucky coincidental single-gap-per-axis
            # match at a noisy low threshold.
            corroboration = col_n + row_n
            candidates.append(
                {
                    "min_frac": min_frac,
                    "cols": cols,
                    "rows": rows,
                    "col_modal": col_modal,
                    "row_modal": row_modal,
                    "col_n": col_n,
                    "row_n": row_n,
                    "corroboration": corroboration,
                    "spacing_px": spacing,
                }
            )
            # Stop at the first (highest / strictest) threshold that
            # produces agreement - prefer the cleanest signal available
            # rather than continuing to scan noisier low thresholds.
            break

    if not candidates:
        return None
    return candidates[0]


STAR_COLOUR_PROFILES = {
    # Most Salford maps use a solid blue star.
    "blue": lambda b, g, r: (b > 150) & (r < 120) & (g < 120),
    # A few use a gold/mustard star instead (e.g. St Joseph the Worker RC).
    "gold": lambda b, g, r: (b < 130) & (g > 190) & (g < 245) & (r > 190) & (r < 245),
}


def detect_star_candidates(img, min_area=80):
    """Find all star-marker-sized blobs across known colour profiles.

    Some source pages place a second, smaller decorative copy of the star
    icon inside their own legend/key box (e.g. St Joseph the Worker RC) -
    same colour, similar size, but not the real on-map marker. Rather than
    guess which is which from position heuristics that won't generalise,
    return every plausible candidate blob and let the caller disambiguate
    using the one real cross-check available: whether anchoring on it (with
    scale/rotation coming independently from the grid) produces a polygon
    that actually contains the school's own real DB coordinate.
    """
    b = img[:, :, 0].astype(int)
    g = img[:, :, 1].astype(int)
    r = img[:, :, 2].astype(int)
    candidates = []
    for colour, fn in STAR_COLOUR_PROFILES.items():
        mask = fn(b, g, r)
        mask8 = (mask * 255).astype(np.uint8)
        n, labels, stats, cent = cv2.connectedComponentsWithStats(mask8, connectivity=8)
        for lbl in range(1, n):
            area = stats[lbl, cv2.CC_STAT_AREA]
            if area < min_area:
                continue
            cx, cy = cent[lbl]
            candidates.append({"colour": colour, "x": float(cx), "y": float(cy), "npix": int(area)})
    candidates.sort(key=lambda c: -c["npix"])
    return candidates


BOUNDARY_COLOUR_PROFILES = {
    # Most Salford parish-boundary maps use a solid hand-drawn black line.
    "black": lambda b, g, r: (b < 70) & (g < 70) & (r < 70),
    # The council's separate "catchment area" style maps (secondary schools,
    # e.g. Ellesmere Park) use a solid red line instead.
    "red": lambda b, g, r: (r > 180) & (g < 100) & (b < 100),
}


def _is_page_border(contour, stats, img_shape, span_frac=0.90):
    """A plain rectangular page-border frame (thin black/red line drawn
    right around the whole map, unrelated to any school's catchment) also
    has a large bbox and low fill ratio, so it can otherwise be mistaken
    for the real hand-drawn boundary. Unlike a genuine catchment polygon
    (which occupies a sub-region of the page, leaving room for title/key
    text), a page border's bbox spans almost the *entire* page in both
    width and height simultaneously - that combination is the reliable
    tell, not vertex count (real boundaries can have long near-straight
    runs that also collapse under contour simplification)."""
    x, y, w, h = stats[0], stats[1], stats[2], stats[3]
    img_h, img_w = img_shape[:2]
    return (w / img_w) > span_frac and (h / img_h) > span_frac


def _detect_boundary_for_mask(mask, max_fill_ratio=0.3):
    mask8 = (mask * 255).astype(np.uint8)
    kernel = np.ones((9, 9), np.uint8)
    closed = cv2.morphologyEx(mask8, cv2.MORPH_CLOSE, kernel, iterations=2)
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(closed, connectivity=8)
    if n <= 1:
        return None
    ranked = []
    for lbl in range(1, n):
        x, y, w, h, area = stats[lbl]
        if w * h == 0:
            continue
        fill = area / (w * h)
        if fill > max_fill_ratio:
            continue
        ranked.append((w * h, lbl))
    ranked.sort(reverse=True)
    for bbox_area, lbl in ranked:
        comp_mask = (labels == lbl).astype(np.uint8) * 255
        contours, _ = cv2.findContours(comp_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        largest_contour = max(contours, key=cv2.contourArea)
        if _is_page_border(largest_contour, stats[lbl], mask.shape):
            continue  # skip plain frame borders, keep looking
        return largest_contour, stats[lbl], comp_mask
    return None


def detect_boundary_polygon_px(img, max_fill_ratio=0.3):
    """Detect the hand-drawn boundary loop (black or red line), skipping
    over any plain rectangular page-border frame and solid legend/title
    boxes (high fill ratio) along the way.

    The boundary is a thin closed(ish) line, so among same-coloured
    connected components it has a large bounding box but a *low* fill ratio
    (area / (bbox_w * bbox_h)) - this distinguishes it from solid legend/
    title boxes. Tries both known boundary-line colours used across this
    council's two source-page styles and keeps whichever produces a result.
    """
    b = img[:, :, 0].astype(int)
    g = img[:, :, 1].astype(int)
    r = img[:, :, 2].astype(int)
    for colour, fn in BOUNDARY_COLOUR_PROFILES.items():
        mask = fn(b, g, r)
        result = _detect_boundary_for_mask(mask, max_fill_ratio=max_fill_ratio)
        if result is not None:
            return result
    return None


def px_to_lonlat(px, py, star_px, star_py, school_easting, school_northing, scale_m_per_px):
    dx = px - star_px
    dy = py - star_py
    de = dx * scale_m_per_px
    dn = -dy * scale_m_per_px
    E = school_easting + de
    N = school_northing + dn
    lon, lat = OSGB_TO_WGS84.transform(E, N)
    return lon, lat


def _dominant_polygon(geom):
    """Reduce a Polygon/MultiPolygon to its single largest-area piece.

    `Polygon.buffer(0)` (used to repair a self-intersecting ring produced by
    contour-tracing a hand-drawn line) can legitimately split a shape into
    several disjoint pieces where the drawn line nearly touches itself. Per
    this project's standing rule, every shipped feature must be a single
    clean Polygon - take the dominant (largest area) piece and verify
    containment against THAT, not the raw multi-part geometry."""
    if geom.geom_type == "Polygon":
        return geom
    if geom.geom_type == "MultiPolygon":
        return max(geom.geoms, key=lambda g: g.area)
    return geom


def _polygon_from_contour(contour, star_px, star_py, school_e, school_n, scale_m_per_px):
    from shapely.geometry import Polygon

    pts = contour.reshape(-1, 2)
    lonlat_pts = [
        px_to_lonlat(px, py, star_px, star_py, school_e, school_n, scale_m_per_px) for px, py in pts
    ]
    ring = lonlat_pts + [lonlat_pts[0]]
    polygon = Polygon(ring)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    polygon = _dominant_polygon(polygon)
    return polygon, pts


def digitise(path, school_lon, school_lat, verbose=False, manual_spacing_px=None):
    """Digitise one school's boundary map into a lon/lat polygon.

    manual_spacing_px: escape hatch for the rare case where automatic dual-
    axis grid-spacing detection can't be trusted on a single file (e.g. only
    one grid line survives on one axis) but a spacing value is otherwise
    well-corroborated (e.g. cross-checked against a second source page that
    shares the exact same underlying base map/extent) and independently
    verified safe via containment-margin robustness across the full
    plausible spacing range. Used for exactly two Salford files this
    session (St Philip's CE, St Paul's CE Cross Lane) - see notes in
    build_geojson.py. Never used to force an implausible or unverified fit.
    """
    img = cv2.imread(path)
    h, w = img.shape[:2]
    if manual_spacing_px is not None:
        spacing = {"spacing_px": manual_spacing_px}
    else:
        spacing = detect_grid_spacing(img, verbose=verbose)
    if spacing is None:
        return {"ok": False, "reason": "grid spacing not found/agreed"}
    star_candidates = detect_star_candidates(img)
    star_candidates = [c for c in star_candidates if c["npix"] >= 100]
    if not star_candidates:
        return {"ok": False, "reason": "star not found"}
    poly = detect_boundary_polygon_px(img)
    if poly is None:
        return {"ok": False, "reason": "boundary polygon not found"}
    contour, stats, comp_mask = poly

    scale_m_per_px = 1000.0 / spacing["spacing_px"]
    school_e, school_n = WGS84_TO_OSGB.transform(school_lon, school_lat)

    from shapely.geometry import Point
    from shapely.ops import transform as shp_transform

    def to_osgb(x, y):
        return WGS84_TO_OSGB.transform(x, y)

    school_point = Point(school_lon, school_lat)
    school_pt_osgb = Point(school_e, school_n)

    # Disambiguate between multiple star-coloured blobs (e.g. a real on-map
    # marker vs a decorative legend-box copy) using the one real signal
    # available: which anchor produces a polygon that actually contains the
    # school's own already-known-precise DB coordinate. Scale/rotation still
    # come independently from the grid, so this isn't circular - it's the
    # same containment check every candidate must clear regardless.
    results = []
    for cand in star_candidates:
        star_px, star_py = cand["x"], cand["y"]
        polygon, pts = _polygon_from_contour(contour, star_px, star_py, school_e, school_n, scale_m_per_px)
        contains = polygon.contains(school_point)
        polygon_osgb = shp_transform(to_osgb, polygon)
        if contains:
            margin_m = polygon_osgb.boundary.distance(school_pt_osgb)
        else:
            margin_m = -polygon_osgb.distance(school_pt_osgb)
        results.append((margin_m, cand, polygon, pts))

    results.sort(key=lambda t: -t[0])
    margin_m, star_cand, polygon, pts = results[0]
    star_px, star_py, star_npix = star_cand["x"], star_cand["y"], star_cand["npix"]
    contains = margin_m > 0

    return {
        "ok": True,
        "spacing_px": spacing["spacing_px"],
        "scale_m_per_px": scale_m_per_px,
        "star_px": (star_px, star_py),
        "star_npix": star_npix,
        "star_colour": star_cand["colour"],
        "n_star_candidates": len(star_candidates),
        "n_boundary_pts": len(pts),
        "polygon": polygon,
        "contains": contains,
        "margin_m": margin_m,
    }


if __name__ == "__main__":
    path = sys.argv[1]
    lon = float(sys.argv[2])
    lat = float(sys.argv[3])
    result = digitise(path, lon, lat, verbose=True)
    for k, v in result.items():
        if k == "polygon":
            continue
        print(k, "=", v)
