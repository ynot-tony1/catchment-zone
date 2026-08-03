"""Computes a performance percentile for each catchment area.

Not a data source adapter like the others in this package: this reads
data this service has already imported (schools, school_metrics,
catchment_areas) and derives a comparative score, rather than fetching
anything external. Run as a separate refresh-catchment-scores step (not
folded into import-catchments), since it depends on performance metrics
that may be imported after catchments are, and needs to re-run whenever
either side's data changes.

For each catchment area, the served school is found by a real point-in-
polygon test (every school with real coordinates whose point falls
inside the area's polygon, using the area's own indexed
minimum/maximum latitude/longitude columns as a cheap bounding-box
prefilter before the precise shapely test - the same two-phase pattern
apps/web/lib/geo.ts already uses for the admissions checker). The
served school's most recent value for whichever metric applies to the
area's phase and nation is converted to a percentile rank (0-1, higher
is better) among every school with that same metric, so metrics on
different scales (a GCSE Attainment 8 score vs a Wales Capped 9 points
score vs a percentage) become comparable on one scale. An area with no
matching school, or a school with no matching metric (e.g. every
Scottish catchment area right now, since Scotland has no performance
metrics at all), is left with a null percentile - this service never
invents a score.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import psycopg
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from catchment_zone_ingestor import db

logger = logging.getLogger(__name__)

#: Ordered by preference; the first metric_code with real (non-null,
#: non-suppressed) data for a given school wins. One metric per phase/
#: nation combination is used (not an average across several), so the
#: score always means one specific, named thing rather than a blended
#: figure - the UI shows which metric was used via performance_metric_code.
_METRIC_CANDIDATES_BY_NATION_AND_PHASE: dict[tuple[str, str], list[str]] = {
    ("ENGLAND", "primary"): ["ks2_rwm_expected_standard_percent"],
    ("ENGLAND", "secondary"): ["attainment8_average", "a_level_aps_per_entry"],
    ("WALES", "secondary"): ["wales_ks4_capped9_points_score"],
    ("SCOTLAND", "secondary"): ["scotland_leaver_tariff_middle60"],
}


def all_configured_metric_codes() -> set[str]:
    """Every metric_code any nation/phase combination might use, so a
    caller can precompute percentiles for exactly the metrics that
    matter without needing to know the nation/phase table's shape."""
    return {code for codes in _METRIC_CANDIDATES_BY_NATION_AND_PHASE.values() for code in codes}


@dataclass
class SchoolPoint:
    urn: str
    latitude: float
    longitude: float


@dataclass
class CatchmentAreaRow:
    id: str
    area_type: str
    nation: str
    geometry_geojson: str
    minimum_latitude: float
    maximum_latitude: float
    minimum_longitude: float
    maximum_longitude: float


@dataclass
class CatchmentScoreResult:
    id: str
    performance_percentile: float | None
    performance_metric_code: str | None


def _phase_from_area_type(area_type: str) -> str | None:
    """area_type (e.g. "primary_catchment_nd", "secondary_catchment",
    "all_through_catchment") always starts with the phase word this
    service's metric candidates are keyed by. "all_through" areas (e.g.
    Orkney) are deliberately not scored: they mix primary-only and
    combined primary/secondary schools per feature (see
    config/catchment-sources.yml's Orkney entry), so neither a "primary"
    nor a "secondary" metric would honestly describe every school it
    might contain."""
    if area_type.startswith("primary"):
        return "primary"
    if area_type.startswith("secondary"):
        return "secondary"
    return None


def compute_percentiles(values_by_urn: dict[str, float]) -> dict[str, float]:
    """Mid-rank percentile (0-1, higher is better) for each URN's value
    within this single metric's population. Ties share the same
    percentile (the average rank across the tied group), so identical
    scores are never arbitrarily ordered against each other.
    """
    if not values_by_urn:
        return {}
    sorted_values = sorted(values_by_urn.values())
    n = len(sorted_values)

    def _percentile_for(value: float) -> float:
        less_than = 0
        equal_to = 0
        for v in sorted_values:
            if v < value:
                less_than += 1
            elif v == value:
                equal_to += 1
        return (less_than + equal_to / 2) / n

    return {urn: _percentile_for(value) for urn, value in values_by_urn.items()}


def load_latest_metric_values(conn: db.ConnectionLike, metric_code: str) -> dict[str, float]:
    """Each school's most recent (highest academic_year), non-suppressed,
    non-null value for one metric_code."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (school_urn) school_urn, value_numeric
            FROM school_metrics
            WHERE metric_code = %(metric_code)s
              AND value_numeric IS NOT NULL
              AND suppressed = false
            ORDER BY school_urn, academic_year DESC
            """,
            {"metric_code": metric_code},
        )
        return {row["school_urn"]: row["value_numeric"] for row in cur.fetchall()}


def load_schools_with_coordinates(conn: db.ConnectionLike) -> list[SchoolPoint]:
    with conn.cursor() as cur:
        cur.execute("SELECT urn, latitude, longitude FROM schools WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
        return [SchoolPoint(urn=row["urn"], latitude=row["latitude"], longitude=row["longitude"]) for row in cur.fetchall()]


def load_catchment_areas(conn: db.ConnectionLike) -> list[CatchmentAreaRow]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ca.id, ca.area_type, ca.geometry_geojson,
                   ca.minimum_latitude, ca.maximum_latitude,
                   ca.minimum_longitude, ca.maximum_longitude,
                   la.nation
            FROM catchment_areas ca
            JOIN catchment_sources cs ON cs.id = ca.source_id
            JOIN local_authorities la ON la.code = cs.local_authority_code
            """
        )
        return [
            CatchmentAreaRow(
                id=row["id"],
                area_type=row["area_type"],
                nation=row["nation"],
                geometry_geojson=row["geometry_geojson"],
                minimum_latitude=row["minimum_latitude"],
                maximum_latitude=row["maximum_latitude"],
                minimum_longitude=row["minimum_longitude"],
                maximum_longitude=row["maximum_longitude"],
            )
            for row in cur.fetchall()
        ]


def _schools_in_bbox(schools: list[SchoolPoint], area: CatchmentAreaRow) -> list[SchoolPoint]:
    return [
        s
        for s in schools
        if area.minimum_latitude <= s.latitude <= area.maximum_latitude
        and area.minimum_longitude <= s.longitude <= area.maximum_longitude
    ]


def _parse_geometry(geometry_geojson: str) -> BaseGeometry | None:
    try:
        return shape(json.loads(geometry_geojson))
    except (ValueError, TypeError, KeyError):
        return None


def compute_catchment_scores(
    areas: list[CatchmentAreaRow],
    schools: list[SchoolPoint],
    percentiles_by_metric: dict[str, dict[str, float]],
) -> list[CatchmentScoreResult]:
    """Pure function (no I/O) so the scoring logic itself is directly
    testable without a database: given every catchment area, every
    school's coordinates, and every metric's precomputed percentile
    ranks, returns one score per area."""
    results: list[CatchmentScoreResult] = []
    for area in areas:
        phase = _phase_from_area_type(area.area_type)
        if phase is None:
            results.append(CatchmentScoreResult(area.id, None, None))
            continue

        metric_candidates = _METRIC_CANDIDATES_BY_NATION_AND_PHASE.get((area.nation, phase), [])
        if not metric_candidates:
            results.append(CatchmentScoreResult(area.id, None, None))
            continue

        candidate_schools = _schools_in_bbox(schools, area)
        if not candidate_schools:
            results.append(CatchmentScoreResult(area.id, None, None))
            continue

        geometry = _parse_geometry(area.geometry_geojson)
        if geometry is None:
            results.append(CatchmentScoreResult(area.id, None, None))
            continue

        served_urns = [s.urn for s in candidate_schools if geometry.covers(Point(s.longitude, s.latitude))]
        if not served_urns:
            results.append(CatchmentScoreResult(area.id, None, None))
            continue

        # First metric_code candidate with at least one served school's
        # percentile available wins; the school-level metric-availability
        # gap (e.g. not every school has every metric every year) means a
        # school-by-school fallback would be needed for a true
        # multi-metric blend, which is not attempted here - one metric,
        # honestly labelled, beats an opaque blend.
        for metric_code in metric_candidates:
            metric_percentiles = percentiles_by_metric.get(metric_code, {})
            matched = [metric_percentiles[urn] for urn in served_urns if urn in metric_percentiles]
            if matched:
                results.append(
                    CatchmentScoreResult(area.id, sum(matched) / len(matched), metric_code)
                )
                break
        else:
            results.append(CatchmentScoreResult(area.id, None, None))

    return results


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(psycopg.errors.SerializationFailure),
)
def _write_batch_with_retry(conn: db.ConnectionLike, batch: list[dict[str, object]]) -> None:
    """Writes one batch inside its own short transaction, retrying just
    that batch from scratch on a CockroachDB SERIALIZABLE retry error
    (SQLSTATE 40001) - the same class of error, and the same per-batch-
    transaction fix, as cli.py's _upsert_batch_with_retry."""
    with db.transaction(conn), conn.cursor() as cur:
        cur.executemany(
            """
            UPDATE catchment_areas
            SET performance_percentile = %(performance_percentile)s,
                performance_metric_code = %(performance_metric_code)s,
                updated_at = now()
            WHERE id = %(id)s
            """,
            batch,
        )


def write_catchment_scores(conn: db.ConnectionLike, scores: list[CatchmentScoreResult], batch_size: int) -> int:
    rows = [
        {"id": s.id, "performance_percentile": s.performance_percentile, "performance_metric_code": s.performance_metric_code}
        for s in scores
    ]
    total = 0
    for batch in db.batched(rows, batch_size=batch_size):
        _write_batch_with_retry(conn, batch)
        total += len(batch)
    return total
