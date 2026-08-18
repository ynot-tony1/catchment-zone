#!/usr/bin/env python3
"""Build/refresh salford_primary_catchments.geojson from the per-school PDFs.

Usage:
    python3 build_geojson.py --png-dir /path/to/rendered/pngs \
        --existing ../salford_primary_catchments.geojson \
        --output ../salford_primary_catchments.geojson

`--png-dir` must contain one PNG per landed school key in schools.py
(e.g. christ-the-king.png), rendered from the source PDF at high
resolution (this session used PyMuPDF: `page.get_pixmap(matrix=fitz.Matrix(4, 4))`,
i.e. ~288dpi - the pipeline's colour thresholds and thin-line distance-
transform were tuned against that resolution). PDFs themselves are not
committed to this repo; re-download each from `SCHOOLS[key]["pdf_url"]`.

This script only ADDS the schools marked `landed=True` in schools.py that
are not already present (matched by URN) in the existing GeoJSON - it does
not touch the 7 schools landed in the previous session, and re-running it
is safe/idempotent.

Output is written compact (`json.dumps(..., separators=(",", ":"))`) to
match this project's committed-minified GeoJSON convention.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from grid_digitise import digitise  # noqa: E402
from schools import SCHOOLS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png-dir", required=True)
    ap.add_argument("--existing", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--min-margin-m", type=float, default=100.0)
    args = ap.parse_args()

    with open(args.existing) as f:
        existing = json.load(f)
    existing_urns = {feat["properties"]["urn"] for feat in existing["features"]}

    new_features = []
    for key, info in SCHOOLS.items():
        if not info.get("landed"):
            continue
        if info["urn"] in existing_urns:
            print(f"skip {key}: URN {info['urn']} already present", file=sys.stderr)
            continue
        png_path = os.path.join(args.png_dir, f"{key}.png")
        if not os.path.exists(png_path):
            print(f"ERROR: missing rendered PNG for {key}: {png_path}", file=sys.stderr)
            sys.exit(1)
        result = digitise(
            png_path,
            info["lon"],
            info["lat"],
            manual_spacing_px=info.get("manual_spacing_px"),
        )
        if not result["ok"]:
            print(f"ERROR: {key} failed to digitise: {result['reason']}", file=sys.stderr)
            sys.exit(1)
        if not result["contains"] or result["margin_m"] < args.min_margin_m:
            print(
                f"ERROR: {key} margin {result['margin_m']:.1f}m below "
                f"{args.min_margin_m}m bar - refusing to include",
                file=sys.stderr,
            )
            sys.exit(1)
        polygon = result["polygon"]
        coords = [list(polygon.exterior.coords)]
        feature = {
            "type": "Feature",
            "properties": {"urn": info["urn"], "db_school_name": info["db_school_name"]},
            "geometry": {"type": "Polygon", "coordinates": coords},
        }
        new_features.append(feature)
        print(
            f"OK  {key:25s} urn={info['urn']:8s} margin={result['margin_m']:8.1f}m "
            f"spacing={result['spacing_px']:.1f}px star={result['star_colour']}",
            file=sys.stderr,
        )

    merged = {
        "type": "FeatureCollection",
        "features": existing["features"] + new_features,
    }
    with open(args.output, "w") as f:
        json.dump(merged, f, separators=(",", ":"))
    print(f"Wrote {len(merged['features'])} total features ({len(new_features)} new) to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
