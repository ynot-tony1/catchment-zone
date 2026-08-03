"""Scotland school performance adapter: two statistics.gov.scot datasets,
"Schools - Attainment for All" (http://statistics.gov.scot/data/attainment-for-all)
and "Schools - Attainment by Deprivation" (http://statistics.gov.scot/data/attainment-by-deprivation-quintile).

Previously this service concluded Scotland had zero public per-school
performance data (SQA National Qualifications results, Achievement of CfE
levels, and statistics.gov.scot's SPARQL endpoint all publish only at
local-authority/national level; the one real per-school tool, Insight,
requires school/council login and was correctly never scraped). That
conclusion was wrong for these two datasets, missed in the earlier pass:
both have a genuine `refEstablishment` dimension, verified live
(2026-08-03) - one row per secondary school, per academic year. Attainment
for All gives the average total SQA tariff score of that year's S4-S6
leavers split into three attainment bands (lowest 20%, middle 60%,
highest 20% of attainers). Attainment by Deprivation gives the same
average total tariff score, structurally identical, but split into five
SIMD (Scottish Index of Multiple Deprivation) quintiles of the pupil's
home postcode instead (1 = most deprived, 5 = least deprived) - a
within-school attainment-gap view, not a duplicate of the first dataset.
Junior High schools (which do not run to S6) and schools with a cohort
too small to report are present in both tables but with a suppression
marker in place of every value - stored as suppressed=True,
value_numeric=None, never dropped or invented.

Both datasets' `refEstablishment` numeric id (e.g. 5244439) is the same
underlying SEED code the Scotland schools adapter (scotland.py) already
uses as School.urn, just without the "S" suffix schools.urn carries -
verified live against a real row already in this database (Aberdeen
Grammar School, establishment id 5244439, schools.urn "5244439S").
Two aggregate rows per year (`establishment-group/900` "Grant Aided",
`establishment-group/1` "National") are not real schools and are
filtered out by URI shape, not by a hardcoded id list, so a future third
aggregate group does not silently leak through as a fake school.

One CSV GET per (dataset, academic year) pair covers every school in
Scotland at once (no per-school querying, unlike the Wales adapter) -
verified live that data exists for academic years 2015-16 through
2024-25 in both datasets (2013-14 and 2025-26 both return headers only,
confirming the real range) - and licensed Open Government Licence v3.0,
stated explicitly on each dataset's own statistics.gov.scot page.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from catchment_zone_ingestor.models import SchoolMetric

logger = logging.getLogger(__name__)

_SLICE_BASE_URL = "https://statistics.gov.scot/slice/observations.csv"
_MEASURE_TYPE_URI = "http://statistics.gov.scot/def/measure-properties/average-total-tariff-score"
_COMPARATOR_URI = "http://statistics.gov.scot/def/concept/comparator/real-establishment"
_REF_PERIOD_TEMPLATE = "http://reference.data.gov.uk/id/gregorian-interval/{year}-08-01T00:00:00/P1Y"

#: Verified live (2026-08-03): the earliest and latest academic years with
#: real per-school data in both datasets. The calendar year here is the
#: START of the academic year (e.g. 2024 -> "2024-2025").
EARLIEST_ACADEMIC_YEAR_START = 2015
LATEST_ACADEMIC_YEAR_START = 2024

METRIC_CODE_LOWEST_20 = "scotland_leaver_tariff_lowest20"
METRIC_CODE_MIDDLE_60 = "scotland_leaver_tariff_middle60"
METRIC_CODE_HIGHEST_20 = "scotland_leaver_tariff_highest20"

METRIC_CODE_SIMD_Q1_MOST_DEPRIVED = "scotland_leaver_tariff_simd_q1"
METRIC_CODE_SIMD_Q2 = "scotland_leaver_tariff_simd_q2"
METRIC_CODE_SIMD_Q3 = "scotland_leaver_tariff_simd_q3"
METRIC_CODE_SIMD_Q4 = "scotland_leaver_tariff_simd_q4"
METRIC_CODE_SIMD_Q5_LEAST_DEPRIVED = "scotland_leaver_tariff_simd_q5"

#: "#" marks a school with too few leavers to report the whole table row;
#: "*" marks one band suppressed on its own (verified live, e.g.
#: Ardnamurchan High School: lowest-20 and highest-20 are "*" while
#: middle-60 has a real value most years) - a small-rural-school cohort
#: too thin to safely split for that specific band, not a different kind
#: of gap. "NA" marks a school-year with no reportable leaver cohort at
#: all that year (verified live across several small/remote schools,
#: e.g. Tiree High School, Kinlochbervie High School - every band reads
#: "NA" together, unlike "#"/"*" which can apply to individual bands).
#: All three are real, named markers in these datasets, not unrecognised
#: data.
_SUPPRESSED_MARKERS = {"#", "*", "NA"}

#: The real per-school row's id looks like
#: ".../id/education/establishment/5244439"; the two national/sector
#: aggregate rows look like ".../id/education/establishment-group/900" -
#: distinguished by this literal substring, not a hardcoded id allowlist.
_ESTABLISHMENT_GROUP_MARKER = "establishment-group/"
_ESTABLISHMENT_ID_PREFIX = "http://statistics.gov.scot/id/education/establishment/"


@dataclass(frozen=True)
class _DatasetSpec:
    dataset_uri: str
    #: CSV column order (after the refEstablishment/name columns),
    #: verified live against each dataset's own header row.
    band_metric_codes: list[str]
    source_release: str


_ATTAINMENT_FOR_ALL = _DatasetSpec(
    dataset_uri="http://statistics.gov.scot/data/attainment-for-all",
    band_metric_codes=[METRIC_CODE_LOWEST_20, METRIC_CODE_MIDDLE_60, METRIC_CODE_HIGHEST_20],
    source_release="statistics.gov.scot/data/attainment-for-all",
)

_ATTAINMENT_BY_DEPRIVATION = _DatasetSpec(
    dataset_uri="http://statistics.gov.scot/data/attainment-by-deprivation-quintile",
    band_metric_codes=[
        METRIC_CODE_SIMD_Q1_MOST_DEPRIVED,
        METRIC_CODE_SIMD_Q2,
        METRIC_CODE_SIMD_Q3,
        METRIC_CODE_SIMD_Q4,
        METRIC_CODE_SIMD_Q5_LEAST_DEPRIVED,
    ],
    source_release="statistics.gov.scot/data/attainment-by-deprivation-quintile",
)

_DATASET_SPECS = [_ATTAINMENT_FOR_ALL, _ATTAINMENT_BY_DEPRIVATION]

#: Every metric_code either dataset can produce, for callers (e.g. cli.py's
#: refresh-metrics validation) that need the full set without knowing this
#: module's internal dataset split.
ALL_METRIC_CODES = [code for spec in _DATASET_SPECS for code in spec.band_metric_codes]


@dataclass
class ScotlandPerformanceFetchResult:
    metrics: list[SchoolMetric] = field(default_factory=list)
    years_fetched: int = 0
    rows_skipped_no_school: int = 0
    skipped_urn_samples: list[str] = field(default_factory=list)


def academic_year_label(year_start: int) -> str:
    return f"{year_start}-{year_start + 1}"


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    retry=retry_if_exception_type(httpx.TransportError),
)
def fetch_attainment_csv(client: httpx.Client, dataset_uri: str, year_start: int) -> str:
    """Fetch one dataset's one academic year's full-Scotland CSV in a
    single request."""
    response = client.get(
        _SLICE_BASE_URL,
        params={
            "dataset": dataset_uri,
            "http://purl.org/linked-data/cube#measureType": _MEASURE_TYPE_URI,
            "http://purl.org/linked-data/sdmx/2009/dimension#refPeriod": _REF_PERIOD_TEMPLATE.format(year=year_start),
            "http://statistics.gov.scot/def/dimension/comparator": _COMPARATOR_URI,
        },
    )
    response.raise_for_status()
    return response.text


def _parse_band_value(raw: str) -> tuple[float | None, bool]:
    """Returns (value_numeric, suppressed)."""
    stripped = raw.strip()
    if stripped in _SUPPRESSED_MARKERS or not stripped:
        return None, True
    try:
        return float(stripped), False
    except ValueError:
        logger.warning("unrecognised Scotland attainment cell value treated as suppressed", extra={"raw_value": raw})
        return None, True


def parse_attainment_csv(
    csv_text: str, year_start: int, known_urns: set[str], spec: _DatasetSpec = _ATTAINMENT_FOR_ALL
) -> tuple[list[SchoolMetric], list[str]]:
    """Parses one dataset's one year's CSV into SchoolMetric rows,
    filtering to schools that actually exist in this database
    (school_metrics.school_urn has a real foreign key to schools.urn - an
    establishment id present in this dataset but not in our schools
    table, e.g. a school that closed before the current GIAS-equivalent
    extract, is skipped rather than inserted).

    Returns (metrics, skipped_urn_samples).
    """
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    header_index = next(
        (i for i, row in enumerate(rows) if row and row[0] == "http://statistics.gov.scot/def/education/refEstablishment"),
        None,
    )
    if header_index is None:
        raise ValueError("could not find refEstablishment header row in Scotland attainment CSV")

    academic_year = academic_year_label(year_start)
    metrics: list[SchoolMetric] = []
    skipped_samples: list[str] = []

    for row in rows[header_index + 1 :]:
        if len(row) < 1 + 1 + len(spec.band_metric_codes):
            continue
        establishment_uri, _name, *band_values = row
        if _ESTABLISHMENT_GROUP_MARKER in establishment_uri:
            continue
        if not establishment_uri.startswith(_ESTABLISHMENT_ID_PREFIX):
            continue
        seed_code = establishment_uri[len(_ESTABLISHMENT_ID_PREFIX) :].strip()
        if not seed_code:
            continue
        urn = f"{seed_code}S"
        if urn not in known_urns:
            if len(skipped_samples) < 20:
                skipped_samples.append(urn)
            continue

        for metric_code, raw_value in zip(spec.band_metric_codes, band_values, strict=False):
            value_numeric, suppressed = _parse_band_value(raw_value)
            metrics.append(
                SchoolMetric(
                    school_urn=urn,
                    metric_code=metric_code,
                    academic_year=academic_year,
                    value_numeric=value_numeric,
                    suppressed=suppressed,
                    source_release=spec.source_release,
                )
            )

    return metrics, skipped_samples


def fetch_all_years_performance(
    client: httpx.Client,
    known_urns: set[str],
    year_starts: list[int] | None = None,
) -> ScotlandPerformanceFetchResult:
    """Fetches and parses every (dataset, academic year) pair (years
    default to the full verified-live range, datasets always both), a
    single school's fetch failure for one dataset/year never losing any
    other dataset/year (consistent with every other adapter's per-unit
    tolerance in this service)."""
    if year_starts is None:
        year_starts = list(range(EARLIEST_ACADEMIC_YEAR_START, LATEST_ACADEMIC_YEAR_START + 1))

    result = ScotlandPerformanceFetchResult()
    for spec in _DATASET_SPECS:
        for year_start in year_starts:
            try:
                csv_text = fetch_attainment_csv(client, spec.dataset_uri, year_start)
                metrics, skipped_samples = parse_attainment_csv(csv_text, year_start, known_urns, spec)
                result.metrics.extend(metrics)
                result.rows_skipped_no_school += len(skipped_samples)
                for sample in skipped_samples:
                    if len(result.skipped_urn_samples) < 20:
                        result.skipped_urn_samples.append(sample)
                result.years_fetched += 1
            except Exception as exc:
                logger.warning(
                    "could not fetch/parse Scotland attainment CSV for one dataset/academic year",
                    extra={"dataset": spec.dataset_uri, "academic_year": academic_year_label(year_start), "error": str(exc)},
                )
    return result
