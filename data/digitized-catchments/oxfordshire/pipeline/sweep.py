import sys, json, os
sys.path.insert(0, ".")
from match_schools import match
from process_one import is_grid_template
from oxon_lib import (
    render, cyan_mask_broad, reconcile_grid_period, confirmed_grid_line_fraction,
    find_marker_and_boundary, fill_boundary, polygon_from_mask,
)
import numpy as np
from pyproj import Transformer
from shapely.geometry import Point, Polygon
from shapely.ops import transform as shp_transform

t_wgs_to_osgb = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
t_osgb_to_wgs = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)

def narrow_mask(arr):
    r = arr[:, :, 0].astype(int); g = arr[:, :, 1].astype(int); b = arr[:, :, 2].astype(int)
    return (b > 200) & (g > 140) & (g < 230) & (r < 160) & (r > 10)

def try_process(pdf_path, lat, lon, color, dpi, mask_fn):
    arr = render(pdf_path, dpi=dpi)
    mask = mask_fn(arr)
    colsum = mask.sum(axis=0).astype(float)
    rowsum = mask.sum(axis=1).astype(float)
    px, py = reconcile_grid_period(colsum, rowsum, min_p=100, max_p=1000, tol=0.03)
    if px is None:
        return {"ok": False, "reason": "no period"}
    fx, fy = confirmed_grid_line_fraction(mask, px, py)
    if fx < 0.7 or fy < 0.7:
        return {"ok": False, "reason": f"low line frac {fx:.2f}/{fy:.2f}"}
    boundary, markers, labels, comps = find_marker_and_boundary(arr, color=color)
    if boundary is None or not markers:
        return {"ok": False, "reason": "no boundary/marker"}
    marker = max(markers, key=lambda c: c["area"])
    filled = fill_boundary(labels, boundary["label"])
    poly_px = polygon_from_mask(filled)
    if poly_px is None:
        return {"ok": False, "reason": "poly extraction failed"}
    mx_px, my_px = marker["centroid"]
    marker_pt = Point(mx_px, my_px)
    if not (poly_px.contains(marker_pt) or poly_px.distance(marker_pt) < 5):
        return {"ok": False, "reason": "marker not inside boundary"}
    E_school, N_school = t_wgs_to_osgb.transform(lon, lat)
    def px_to_osgb(x, y):
        return E_school + (x - mx_px) * 1000.0 / px, N_school - (y - my_px) * 1000.0 / py
    coords_osgb = [px_to_osgb(x, y) for x, y in poly_px.exterior.coords]
    poly_osgb = Polygon(coords_osgb)
    poly_wgs = shp_transform(lambda x, y: t_osgb_to_wgs.transform(x, y), poly_osgb)
    if not poly_wgs.is_valid:
        poly_wgs = poly_wgs.buffer(0)
    minx, miny, maxx, maxy = poly_wgs.bounds
    if not (49 <= miny <= 61 and 49 <= maxy <= 61 and -11 <= minx <= 2 and -11 <= maxx <= 2):
        return {"ok": False, "reason": "out of GB bounds"}
    area_km2 = poly_osgb.area / 1e6
    if area_km2 < 0.3 or area_km2 > 600:
        return {"ok": False, "reason": f"implausible area {area_km2:.2f}"}
    return {"ok": True, "poly": poly_wgs, "area_km2": area_km2, "grid_px": px, "grid_py": py, "dpi": dpi}


def main():
    scratch = sys.argv[1]
    rows = match(f"{scratch}/oxon_codes.tsv", f"{scratch}/oxon_schools.tsv")
    PHASE_COLOR = {"Primary": "blue", "Secondary": "red"}
    done_urns = set()
    for f in ["../oxfordshire_digitized_primary_catchments.geojson", "../oxfordshire_digitized_secondary_catchments.geojson"]:
        fc = json.load(open(f))
        for feat in fc["features"]:
            done_urns.add(str(feat["properties"].get("SCHOOL_URN")))

    candidates = [r for r in rows if r["matched"] and r["phase_name"] in PHASE_COLOR and str(r["urn"]) not in done_urns]
    dpis = [300, 280, 260, 240, 220, 200, 180, 160]
    masks = [("narrow", narrow_mask), ("broad", cyan_mask_broad)]

    found = {}
    for r in candidates:
        pdf_path = f"{scratch}/pdfs/{r['code']}_all.pdf"
        if not os.path.exists(pdf_path):
            continue
        is_grid, diag = is_grid_template(pdf_path)
        if not is_grid:
            continue
        urn = str(r["urn"])
        if urn in found:
            continue
        for dpi in dpis:
            for mname, mfn in masks:
                try:
                    result = try_process(pdf_path, r["lat"], r["lon"], PHASE_COLOR[r["phase_name"]], dpi, mfn)
                except Exception as e:
                    continue
                if result["ok"]:
                    print(f"OK\t{r['code']}\t{r['db_name']}\tdpi={dpi}\tmask={mname}\tarea={result['area_km2']:.2f}km2")
                    found[urn] = (r, result, mname, dpi)
                    break
            if urn in found:
                break
        else:
            pass
    print(f"\n{len(found)} found")
    import pickle
    with open(f"{scratch}/sweep_found.pkl", "wb") as f:
        pickle.dump(found, f)

if __name__ == "__main__":
    main()
