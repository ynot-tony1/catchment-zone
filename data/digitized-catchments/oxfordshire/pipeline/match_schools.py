"""Match Oxfordshire County Council's own school-directory codes (used in
its "Location and Designated Area" PDF URLs,
oxfordshire.gov.uk/sites/default/files/2022-12/{code}_all.pdf) to real
schools in our `schools` DB table, by normalised name.

Inputs (both produced by a prior session and expected as plain TSVs, not
regenerated here - see the block comment in config/catchment-sources.yml
for how to regenerate the code list by paginating
oxfordshire.gov.uk/schools/list?page=0..15 if it's ever lost):

  codes_tsv:  council code <TAB> HTML-escaped school name, one per line,
              for all ~307 Oxfordshire school codes.
  schools_tsv: urn <TAB> school_name <TAB> phase_name <TAB> latitude <TAB>
              longitude <TAB> status, one per line, for local_authority_code
              '931' (produced via a `psql -t -A -F$'\\t'` query against the
              schools table - see PROJECT_STATUS.md / this directory's
              batch_process.py for the exact query).

Output: a list of dicts with code, urn, name, phase_name, lat, lon,
matched (bool). Ambiguous/unmatched names are reported, not guessed at -
this script never invents a mapping.
"""

from __future__ import annotations

import csv
import html
import re


def normalise(name: str) -> str:
    name = html.unescape(name)
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", " ", name)
    return name.strip()


def load_codes(codes_tsv: str) -> list[tuple[str, str]]:
    rows = []
    with open(codes_tsv, newline="") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            code, name = line.split("\t", 1)
            rows.append((code.strip(), html.unescape(name.strip())))
    return rows


def load_schools(schools_tsv: str) -> list[dict]:
    rows = []
    with open(schools_tsv, newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        for r in reader:
            if len(r) < 6:
                continue
            urn, name, phase, lat, lon, status = r[:6]
            rows.append(
                {
                    "urn": urn,
                    "name": name,
                    "phase_name": phase,
                    "lat": float(lat) if lat else None,
                    "lon": float(lon) if lon else None,
                    "status": status,
                }
            )
    return rows


def match(codes_tsv: str, schools_tsv: str) -> list[dict]:
    codes = load_codes(codes_tsv)
    schools = load_schools(schools_tsv)
    by_norm: dict[str, list[dict]] = {}
    for s in schools:
        by_norm.setdefault(normalise(s["name"]), []).append(s)

    results = []
    for code, name in codes:
        key = normalise(name)
        candidates = by_norm.get(key, [])
        # prefer OPEN schools if there's ambiguity between an open and a
        # closed school sharing a normalised name
        open_candidates = [c for c in candidates if c["status"] == "OPEN"]
        chosen = open_candidates[0] if open_candidates else (candidates[0] if candidates else None)
        results.append(
            {
                "code": code,
                "council_name": name,
                "matched": chosen is not None,
                "ambiguous": len(candidates) > 1,
                "urn": chosen["urn"] if chosen else None,
                "db_name": chosen["name"] if chosen else None,
                "phase_name": chosen["phase_name"] if chosen else None,
                "lat": chosen["lat"] if chosen else None,
                "lon": chosen["lon"] if chosen else None,
            }
        )
    return results


if __name__ == "__main__":
    import sys

    codes_tsv, schools_tsv = sys.argv[1], sys.argv[2]
    rows = match(codes_tsv, schools_tsv)
    matched = [r for r in rows if r["matched"]]
    unmatched = [r for r in rows if not r["matched"]]
    print(f"{len(matched)}/{len(rows)} matched, {len(unmatched)} unmatched", file=sys.stderr)
    for r in unmatched:
        print(f"UNMATCHED\t{r['code']}\t{r['council_name']}", file=sys.stderr)
    w = csv.writer(sys.stdout, delimiter="\t")
    w.writerow(["code", "urn", "db_name", "phase_name", "lat", "lon"])
    for r in matched:
        w.writerow([r["code"], r["urn"], r["db_name"], r["phase_name"], r["lat"], r["lon"]])
