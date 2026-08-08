"""Batch-run the grid-template pipeline (process_one.process) over a
directory of downloaded Oxfordshire "Location and Designated Area" PDFs,
against the schools table, appending any successful result to the
committed primary/secondary geojson feature collections.

CRITICAL: always checks each candidate school's URN against both geojson
files before processing it. A prior session's finalize.py skipped this
check and landed 7 near-duplicate catchment polygons (same school
digitised twice) before it was caught - see the 2026-08-08 correction
note in config/catchment-sources.yml. Never bypass build_done_urns()
below when adding to these files by any other means.

Usage:
    python batch_process.py \\
        --codes-tsv <council code TAB name, one per line> \\
        --schools-tsv <urn TAB name TAB phase_name TAB lat TAB lon TAB status> \\
        --pdf-dir <dir of {code}_all.pdf files> \\
        [--dpi 300] [--apply]

Without --apply, only prints a per-file report (ok / reason for failure).
With --apply, successful results are appended to the geojson files and
written back to disk - the caller is still responsible for git add/commit,
pnpm format:write, DB import, and the DB-side dedup safety this implies.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from match_schools import match  # noqa: E402
from process_one import process  # noqa: E402
from shapely.geometry import mapping  # noqa: E402

HERE = Path(__file__).resolve().parent
PRIMARY_PATH = HERE.parent / "oxfordshire_digitized_primary_catchments.geojson"
SECONDARY_PATH = HERE.parent / "oxfordshire_digitized_secondary_catchments.geojson"

# Boundary/marker colour used per phase in this PDF template family -
# blue for primary schools, red for secondary, verified live on every
# school digitised with this pipeline so far.
PHASE_COLOR = {"Primary": "blue", "Secondary": "red"}
PHASE_KEY = {"Primary": "primary", "Secondary": "secondary"}


def build_done_urns() -> set[str]:
    done = set()
    for path in (PRIMARY_PATH, SECONDARY_PATH):
        fc = json.loads(path.read_text())
        for f in fc["features"]:
            urn = f["properties"].get("SCHOOL_URN")
            if urn is not None:
                done.add(str(urn))
    return done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes-tsv", required=True)
    ap.add_argument("--schools-tsv", required=True)
    ap.add_argument("--pdf-dir", required=True)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument(
        "--only-code", action="append", default=None, help="Restrict to specific council code(s)."
    )
    args = ap.parse_args()

    done_urns = build_done_urns()
    rows = match(args.codes_tsv, args.schools_tsv)
    candidates = [
        r
        for r in rows
        if r["matched"]
        and r["phase_name"] in PHASE_COLOR
        and str(r["urn"]) not in done_urns
    ]
    if args.only_code:
        candidates = [r for r in candidates if r["code"] in args.only_code]

    primary_fc = json.loads(PRIMARY_PATH.read_text())
    secondary_fc = json.loads(SECONDARY_PATH.read_text())
    added_this_run: set[str] = set()

    n_ok, n_fail = 0, 0
    fail_reasons: dict[str, int] = {}
    for r in candidates:
        pdf_path = Path(args.pdf_dir) / f"{r['code']}_all.pdf"
        if not pdf_path.exists():
            continue
        urn = str(r["urn"])
        if urn in done_urns or urn in added_this_run:
            print(f"SKIP {r['db_name']} ({urn}): already has a catchment feature")
            continue
        color = PHASE_COLOR[r["phase_name"]]
        result = process(str(pdf_path), r["lat"], r["lon"], color, dpi=args.dpi)
        if not result["ok"]:
            n_fail += 1
            fail_reasons[result["reason"]] = fail_reasons.get(result["reason"], 0) + 1
            print(f"FAIL {r['code']}\t{r['db_name']}\t{result['reason']}")
            continue
        n_ok += 1
        print(
            f"OK   {r['code']}\t{r['db_name']}\tarea={result['area_km2']:.2f}km2 "
            f"grid=({result['grid_px']:.1f},{result['grid_py']:.1f})"
        )
        if args.apply:
            feature = {
                "type": "Feature",
                "properties": {
                    "CATCHMENT_NAME": f"{r['db_name']} catchment",
                    "SCHOOL_URN": r["urn"],
                    "SCHOOL_NAME": r["db_name"],
                },
                "geometry": mapping(result["poly"]),
            }
            if r["phase_name"] == "Primary":
                primary_fc["features"].append(feature)
            else:
                secondary_fc["features"].append(feature)
            added_this_run.add(urn)

    if args.apply and added_this_run:
        PRIMARY_PATH.write_text(json.dumps(primary_fc))
        SECONDARY_PATH.write_text(json.dumps(secondary_fc))

    print()
    print(f"{n_ok} ok, {n_fail} failed, {len(added_this_run)} appended to geojson")
    if fail_reasons:
        print("failure reason breakdown:")
        for reason, count in sorted(fail_reasons.items(), key=lambda kv: -kv[1]):
            print(f"  {count:3d}  {reason}")


if __name__ == "__main__":
    main()
