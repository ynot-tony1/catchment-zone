"""Extract a real vector-drawn boundary polygon from Oxfordshire's
"hybrid" PDF template: the same real raster OS-grid basemap as the
original grid template (see oxon_lib.py / process_one.py), but with the
boundary/marker drawn as GENUINE vector paths in page.get_drawings()
(several hundred line/curve segments split across multiple path objects
that chain end-to-end into one closed loop, plus a small filled marker
square) instead of baked into the raster.

Discovered 2026-08-08 investigating the 18 schools catchment-sources.yml
flagged as "source PDF no longer presents as the raster grid template" -
direct inspection of get_drawings() (rather than trusting
process_one.is_grid_template()'s n_images/saturated-vector-path
heuristic, which was built only to distinguish the OTHER two known
templates) showed these files still have a completely real, visible OS
grid; is_grid_template() rejects them purely because of the low image
count and the presence of vector paths it otherwise treats as evidence
of the non-gridded vector template. This sub-template is actually HIGHER
precision than the pixel-contour method used for the plain raster
template (exact vector coordinates, not a rasterised approximation), not
lower. See hybrid_process.py for how these primitives combine into a
full digitisation, and catchment-sources.yml's Oxfordshire notes for the
full worked investigation (including two genuine geometric subtleties
found this way: a school with a disjoint two-ring designated area, and a
school with a real interior hole excluding a separately-schooled town).
"""
import numpy as np


def item_endpoints(item):
    """A get_drawings() 'items' entry is either a line ('l', p1, p2), a
    bezier curve ('c', p0, p1, p2, p3), or a rect ('re', ...). Returns
    (start_point, end_point) for line/curve items, (None, None) for
    anything else (rects only appear as the page-border/background
    items in these files, never as part of the boundary path)."""
    kind = item[0]
    if kind == "l":
        return item[1], item[2]
    if kind == "c":
        return item[1], item[4]
    return None, None


def _cubic_bezier_points(p0, p1, p2, p3, n=12):
    """Sample n intermediate points (excluding the start, including the
    end) along a cubic bezier curve. Discovered necessary 2026-08-09
    digitising Thomas Reade Primary School: item_endpoints() collapsing
    a 'c' item to just its start/end point turns any curved stretch of
    the boundary into a straight chord - invisible on most files (curves
    are usually gentle) but produced a visible, wrong straight-line cut
    across a real notch in Thomas Reade's boundary near Eney Road,
    caught only by this project's standing practice of visually
    overlaying every traced ring on the source page before trusting it."""
    pts = []
    for i in range(1, n + 1):
        t = i / n
        mt = 1 - t
        x = mt**3 * p0.x + 3 * mt**2 * t * p1.x + 3 * mt * t**2 * p2.x + t**3 * p3.x
        y = mt**3 * p0.y + 3 * mt**2 * t * p1.y + 3 * mt * t**2 * p2.y + t**3 * p3.y
        pts.append((x, y))
    return pts


def segment_polyline(d):
    """Flatten one get_drawings() path dict into an ordered list of
    (x, y) points, relying on each item's end point equalling the next
    item's start point within the same path (verified true in every
    file checked so far). Bezier curve ('c') items are sampled at 12
    intermediate points rather than collapsed to a straight chord
    between their start/end - see _cubic_bezier_points()."""
    pts = []
    for item in d["items"]:
        kind = item[0]
        if kind == "l":
            s, e = item[1], item[2]
            if not pts:
                pts.append((s.x, s.y))
            pts.append((e.x, e.y))
        elif kind == "c":
            p0, p1, p2, p3 = item[1], item[2], item[3], item[4]
            if not pts:
                pts.append((p0.x, p0.y))
            pts.extend(_cubic_bezier_points(p0, p1, p2, p3))
    return pts


def is_boundary_color(color, target):
    """Discovered 2026-08-09 (St John's Primary School, The Oxford
    Academy): a third marker/boundary colour exists in this template
    family - plain BLACK stroke/fill, rather than the blue/red used
    elsewhere. Distinguishing it from the base-map's own black text/
    road-outline strokes isn't an issue here because those are baked
    into the raster basemap image (get_text() confirms no real text
    layer beyond the page title), so any real get_drawings() vector
    path in this colour range - other than the single page-border
    rect, already excluded by extract_vector_boundary_and_marker's own
    item-count/fill filtering - is the boundary/marker overlay."""
    if color is None:
        return False
    r, g, b = color
    if target == "blue":
        return b > 0.5 and r < 0.3
    if target == "black":
        return r < 0.3 and g < 0.3 and b < 0.3
    return r > 0.5 and b < 0.3


def extract_vector_boundary_and_marker(page, color="blue", min_items=5):
    """Returns (boundary_segments, marker_point). boundary_segments is a
    list of polylines (one per get_drawings() path in the target
    colour, stroke-only - no fill) that need chaining (see
    find_all_rings) into one or more closed rings; marker_point is the
    (x, y) centroid of the small filled same-colour square that marks
    the school's own location on the map (used later as the real-world
    anchor point). Both are in raw PDF point space (page.get_drawings()
    coordinates, top-left origin, y increasing downward - confirmed to
    match pymupdf's pixmap rendering convention by rendering a test
    marker position back over the page image and seeing it land exactly
    on the printed school-location icon)."""
    drawings = page.get_drawings()
    boundary_segs = []
    marker = None
    for d in drawings:
        c = d.get("color")
        n = len(d["items"])
        if is_boundary_color(c, color) and n >= min_items and d.get("fill") is None:
            boundary_segs.append(segment_polyline(d))
        elif d.get("fill") is not None and is_boundary_color(d.get("fill"), color) and n < 50:
            x0, y0, x1, y1 = d["rect"]
            marker = ((x0 + x1) / 2, (y0 + y1) / 2)
    return boundary_segs, marker


def find_all_rings(segs, tol=0.5, close_tol=10.0):
    """Chain polylines end-to-end into as many closed rings as the
    segment set actually forms. Oxfordshire designated areas are
    sometimes genuinely disjoint (The Cooper School: a main Bicester-area
    zone plus a separate Ot Moor-area zone, both confirmed by tracing the
    extracted rings back over the source page image) or have a real
    interior hole (Burford School: Carterton, its own separately-schooled
    town, excluded from the middle of Burford's area) - so a single
    school can legitimately produce more than one ring, and the caller
    (hybrid_process.py) is responsible for deciding hole vs disjoint
    exterior via containment, not this function.

    `tol` governs matching one segment's endpoint to another segment's
    endpoint (real shared vertices, seen matching to <0.001pt in
    practice). `close_tol` is a looser allowance (default 10pt, i.e.
    ~3.5m at a typical ~280pt/km grid scale - small relative to any
    >1km2 catchment) purely for the final "does the whole chained ring
    return to its own start" check, since a few files have been observed
    to leave a tiny real rendering gap at the closing vertex (the PDF
    export not perfectly re-joining start/end of a hand-drawn boundary)
    rather than a spurious non-loop.

    Extends the growing chain from BOTH ends (not just the tail) before
    giving up - picking any segment other than the loop's "first" one as
    the arbitrary starting point otherwise wrongly looks like an
    open/unclosed chain even when every segment genuinely connects,
    found live on Burford School's file.

    Returns (rings, leftover_open_polylines) - a non-empty leftover means
    refuse to guess rather than land a partial/wrong boundary."""
    remaining = [list(s) for s in segs]
    rings = []
    while remaining:
        chain = remaining.pop(0)
        while True:
            tail = chain[-1]
            if abs(chain[0][0] - tail[0]) < tol and abs(chain[0][1] - tail[1]) < tol and len(chain) > 3:
                break
            found = False
            for i, seg in enumerate(remaining):
                if abs(seg[0][0] - tail[0]) < tol and abs(seg[0][1] - tail[1]) < tol:
                    chain.extend(seg[1:])
                    remaining.pop(i)
                    found = True
                    break
                if abs(seg[-1][0] - tail[0]) < tol and abs(seg[-1][1] - tail[1]) < tol:
                    chain.extend(list(reversed(seg))[1:])
                    remaining.pop(i)
                    found = True
                    break
            if found:
                continue
            head = chain[0]
            for i, seg in enumerate(remaining):
                if abs(seg[-1][0] - head[0]) < tol and abs(seg[-1][1] - head[1]) < tol:
                    chain = seg[:-1] + chain
                    remaining.pop(i)
                    found = True
                    break
                if abs(seg[0][0] - head[0]) < tol and abs(seg[0][1] - head[1]) < tol:
                    chain = list(reversed(seg))[:-1] + chain
                    remaining.pop(i)
                    found = True
                    break
            if not found:
                break
        tail = chain[-1]
        gap = ((chain[0][0] - tail[0]) ** 2 + (chain[0][1] - tail[1]) ** 2) ** 0.5
        closed = gap < close_tol and len(chain) > 3
        if closed:
            rings.append(chain)
        else:
            return rings, [chain] + remaining
    return rings, []


def confirmed_grid_line_fraction_peaks(cyan_mask, px, py, prominence=0.35, min_coverage=0.3, band=2):
    """A more robust alternative to oxon_lib.confirmed_grid_line_fraction
    for large (tall/wide, e.g. A3 portrait) pages: rather than stepping a
    FIXED pixel stride derived by rounding the autocorrelation period to
    an integer (which drifts out of phase by several pixels over a
    ~15-square page when the true period has a fractional-pixel
    component - confirmed on Wheatley Park School's file, true period
    ~207.6px vs the rounded 208px, ~6px of accumulated drift by the far
    edge, enough to make a genuinely fully-gridded page score a low
    coverage fraction on whichever half the single global phase guess
    doesn't happen to fit), this directly finds each axis's own local
    mass peaks (independent per-line, no drift possible) and checks each
    one's real full-span coverage individually. A real grid scores high
    on both "were periodic peaks found roughly `spacing` apart at all"
    and "does each one have a real, near-continuous line"; a fake file
    (no periodic structure at all) has neither.

    Validated 2026-08-08 against every clear-cut known real/fake
    Oxfordshire file available locally at the time (13 cases spanning
    both directions, including known-fake Edith Moorhouse and Hardwick
    Primary): scored exactly the same PASS/FAIL as the existing narrow
    and broadened cyan-mask checks on every one, while additionally
    fixing Wheatley Park's drift false-negative - use as a fallback when
    oxon_lib.confirmed_grid_line_fraction scores low, not as a wholesale
    replacement (see hybrid_process.py for how it's actually invoked).

    Returns (frac_x, frac_y, n_peaks_x, n_peaks_y)."""
    h, w = cyan_mask.shape
    colsum = cyan_mask.sum(axis=0).astype(float)
    rowsum = cyan_mask.sum(axis=1).astype(float)

    def find_peaks(signal, spacing):
        thresh = prominence * signal.max() if signal.max() > 0 else 0
        n = len(signal)
        peaks = []
        half = max(3, int(spacing * 0.3))
        i = 0
        while i < n:
            lo, hi = max(0, i - half), min(n, i + half + 1)
            if signal[i] == signal[lo:hi].max() and signal[i] >= thresh:
                peaks.append(i)
                i += half
            else:
                i += 1
        return peaks

    def axis_frac(signal, mask_axis, spacing, full_len):
        peaks = find_peaks(signal, spacing)
        if not peaks:
            return 0.0, 0
        confirmed = 0
        for p in peaks:
            lo, hi = max(0, p - band), min(len(signal), p + band + 1)
            if mask_axis(lo, hi) / full_len >= min_coverage:
                confirmed += 1
        return confirmed / len(peaks), len(peaks)

    frac_x, n_x = axis_frac(colsum, lambda lo, hi: cyan_mask[:, lo:hi].any(axis=1).sum(), px, h)
    frac_y, n_y = axis_frac(rowsum, lambda lo, hi: cyan_mask[lo:hi, :].any(axis=0).sum(), py, w)
    return frac_x, frac_y, n_x, n_y


if __name__ == "__main__":
    import sys

    import pymupdf
    from shapely.geometry import Polygon

    fp = sys.argv[1]
    color = sys.argv[2] if len(sys.argv) > 2 else "blue"
    page_index = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    doc = pymupdf.open(fp)
    page = doc[page_index]
    segs, marker = extract_vector_boundary_and_marker(page, color)
    print(f"{len(segs)} boundary segments, marker={marker}")
    rings, leftover = find_all_rings(segs)
    print(f"{len(rings)} closed ring(s), {len(leftover)} leftover unchained segment(s)")
    for r in rings:
        poly = Polygon(r)
        print(f"  ring: {len(r)} pts, area(pt2)={poly.area:.1f}, valid={poly.is_valid}")
