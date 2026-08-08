"""Shared pipeline for digitizing Oxfordshire's grid-template
'Location and Designated Area' PDFs (OS 1:1250 raster basemap, cyan 1km
grid, blue/red vector-drawn boundary + marker baked into raster tiles -
no real PDF vector paths, confirmed via get_drawings()==[] and
get_images()==60+ tiles, same as the already-documented method in
catchment-sources.yml).
"""
import numpy as np
import cv2
import pymupdf
from shapely.geometry import Polygon, MultiPolygon
from shapely.validation import make_valid


def render(pdf_path, dpi=300, page_index=0):
    doc = pymupdf.open(pdf_path)
    page = doc[page_index]
    pix = page.get_pixmap(dpi=dpi)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
    return arr


def grid_spacing_px(arr):
    """Detect the cyan OS 1km grid line spacing via column/row-sum
    autocorrelation, taking the smallest period among peaks within 50%
    of the tallest peak's height (rejects harmonics) - same fix as the
    documented 2026-08-08 Oxfordshire pipeline update."""
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)
    cyan = (b > 200) & (g > 140) & (g < 230) & (r < 160) & (r > 10)
    colsum = cyan.sum(axis=0).astype(float)
    rowsum = cyan.sum(axis=1).astype(float)

    def period(signal, min_p, max_p):
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
        candidates = [p for p, h in peaks if h >= 0.5 * tallest]
        return min(candidates)

    dpi_scale = arr.shape[1]  # not used directly; min/max period bounds below assume ~300dpi
    min_p, max_p = 100, 700
    px = period(colsum, min_p, max_p)
    py = period(rowsum, min_p, max_p)
    return px, py


def grid_spacing_joint(arr, min_p=180, max_p=950, min_quality=0.08):
    """NOT SAFE TO USE for production digitisation - kept only as a
    documented dead end. Tried as a fallback grid-spacing detector for
    files where the independent per-axis autocorrelation peak search
    (grid_spacing_px) disagrees between x and y, on the theory that a
    genuine square grid should show *some* signal in both axes at the
    same period even when it isn't either axis's own tallest peak.

    Tested live (2026-08-08) against Oxfordshire's non-gridded vector
    template (which has no real grid at all): it confidently returned a
    plausible-looking period from scattered unrelated cyan pixels
    (anti-aliasing, water features) on every file tried, none of which
    lined up with anything real when the claimed grid was drawn back
    over the actual page image. It cannot tell "weak but real grid
    signal" apart from "no grid, coincidental noise" - process_one.py's
    is_grid_template() (a get_images()/get_drawings() check on the PDF
    itself, not a pixel heuristic) is the correct way to decide whether
    a file has a grid at all, and must run before any pixel-based scale
    detection is attempted, joint or otherwise.

    Searches for the period p that maximises the SUM of the normalised
    column and row autocorrelation at p (each divided by that axis's
    zero-lag autocorrelation, i.e. total variance, so the two axes are on
    a comparable scale regardless of image size/contrast), among p that
    are local maxima of that combined curve. Returns (period, quality) or
    (None, None) if no candidate clears min_quality on both axes.
    """
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)
    cyan = (b > 200) & (g > 140) & (g < 230) & (r < 160) & (r > 10)
    colsum = cyan.sum(axis=0).astype(float)
    rowsum = cyan.sum(axis=1).astype(float)

    def autocorr(signal):
        s = signal - signal.mean()
        n = len(s)
        ac = np.correlate(s, s, mode="full")[n - 1 :]
        zero = ac[0] if ac[0] != 0 else 1.0
        return ac / zero

    ac_col = autocorr(colsum)
    ac_row = autocorr(rowsum)
    upper = min(max_p, len(ac_col) - 1, len(ac_row) - 1)
    combined = ac_col[:upper] + ac_row[:upper]

    best_p, best_score = None, -1.0
    for p in range(min_p, upper - 1):
        if combined[p] <= combined[p - 1] or combined[p] <= combined[p + 1]:
            continue
        if ac_col[p] < min_quality or ac_row[p] < min_quality:
            continue
        if combined[p] > best_score:
            best_p, best_score = p, combined[p]
    if best_p is None:
        return None, None
    return best_p, best_score


def _best_phase(signal, p, band=2):
    n = len(signal)
    p_int = int(round(p))
    best_off, best_mass = 0, -1.0
    for off in range(p_int):
        mass = 0.0
        x = off
        while x < n:
            lo, hi = max(0, x - band), min(n, x + band + 1)
            mass += signal[lo:hi].sum()
            x += p_int
        if mass > best_mass:
            best_mass, best_off = mass, off
    return best_off


def confirmed_grid_line_fraction(cyan_mask, px, py, band=2, min_coverage=0.3):
    """The single most important safety check in this pipeline - see the
    long comment in process_one.py's process() for why. A detected
    (px, py) period can pass every other check (x/y agreement, marker-
    inside-boundary, GB bounds, plausible area) while being completely
    fabricated, because none of those checks confirm an actual grid LINE
    exists at the claimed spacing - they only check aggregate pixel
    counts, which scattered unrelated cyan content can satisfy by
    coincidence across a wide search range.

    This checks the real thing: at the best-fitting phase for each axis,
    what fraction of the candidate grid-line positions have cyan pixels
    covering at least `min_coverage` of the full row/column length (i.e.
    an actual near-continuous line spanning most of the page, not a
    handful of scattered points that happen to sum up right). Verified
    live: real grid files score at or near 1.0 on both axes; the "many
    raster tiles but no real grid" false-positive template this check
    was built to catch scores 0.0 on both axes, with no ambiguous middle
    ground observed across Oxfordshire's ~100 confirmed-grid-template
    candidate files. Returns (vertical_fraction, horizontal_fraction).
    """
    h, w = cyan_mask.shape
    colsum = cyan_mask.sum(axis=0).astype(float)
    rowsum = cyan_mask.sum(axis=1).astype(float)

    off_x = _best_phase(colsum, px, band)
    positions_x = list(range(off_x, w, int(round(px))))
    confirmed_x = 0
    for x in positions_x:
        lo, hi = max(0, x - band), min(w, x + band + 1)
        coverage = cyan_mask[:, lo:hi].any(axis=1).sum() / h
        if coverage >= min_coverage:
            confirmed_x += 1
    frac_x = confirmed_x / len(positions_x) if positions_x else 0.0

    off_y = _best_phase(rowsum, py, band)
    positions_y = list(range(off_y, h, int(round(py))))
    confirmed_y = 0
    for y in positions_y:
        lo, hi = max(0, y - band), min(h, y + band + 1)
        coverage = cyan_mask[lo:hi, :].any(axis=0).sum() / w
        if coverage >= min_coverage:
            confirmed_y += 1
    frac_y = confirmed_y / len(positions_y) if positions_y else 0.0

    return frac_x, frac_y


def find_marker_and_boundary(arr, color="blue", min_boundary_pixels=500):
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)
    if color == "blue":
        mask = (b > 180) & (r < 90) & (g < 90)
    else:  # red
        mask = (r > 180) & (g < 90) & (b < 90)
    mask_u8 = (mask * 255).astype(np.uint8)
    # dilate slightly to bridge anti-aliasing gaps in the boundary line
    kernel = np.ones((3, 3), np.uint8)
    mask_dil = cv2.dilate(mask_u8, kernel, iterations=1)
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(mask_dil, connectivity=8)
    comps = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        bbox_area = w * h
        fill_ratio = area / bbox_area if bbox_area else 0
        comps.append(
            {
                "label": i,
                "bbox": (x, y, w, h),
                "area": area,
                "fill_ratio": fill_ratio,
                "centroid": centroids[i],
            }
        )
    # boundary = largest-bbox-area component with LOW fill ratio (thin outline)
    boundary_candidates = [c for c in comps if c["bbox"][2] * c["bbox"][3] > min_boundary_pixels]
    if not boundary_candidates:
        return None, None, labels, comps
    boundary = max(boundary_candidates, key=lambda c: c["bbox"][2] * c["bbox"][3])
    # marker = compact, high-fill-ratio component whose centroid lies
    # inside the boundary's filled interior (checked by caller after
    # filling); here just rank candidates by fill_ratio*compactness,
    # excluding the boundary component itself
    marker_candidates = [
        c
        for c in comps
        if c["label"] != boundary["label"]
        and c["area"] >= 15
        and c["fill_ratio"] > 0.35
        and max(c["bbox"][2], c["bbox"][3]) < 120
    ]
    return boundary, marker_candidates, labels, comps


def fill_boundary(mask_labels, boundary_label):
    filled = (mask_labels == boundary_label).astype(np.uint8) * 255
    # close small gaps then flood-fill from a corner to find exterior,
    # invert to get interior+boundary
    kernel = np.ones((5, 5), np.uint8)
    closed = cv2.morphologyEx(filled, cv2.MORPH_CLOSE, kernel, iterations=2)
    h, w = closed.shape
    flood = closed.copy()
    mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(flood, mask, (0, 0), 255)
    exterior = flood
    interior = cv2.bitwise_not(exterior) | closed
    return interior


def polygon_from_mask(mask_255):
    contours, hierarchy = cv2.findContours(mask_255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    eps = 0.0015 * cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, eps, True)
    pts = approx.reshape(-1, 2)
    if len(pts) < 3:
        return None
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = make_valid(poly)
    return poly
