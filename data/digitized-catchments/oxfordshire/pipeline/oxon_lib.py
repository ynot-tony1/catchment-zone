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
