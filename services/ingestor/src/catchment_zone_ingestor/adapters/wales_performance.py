"""Wales school performance adapter: mylocalschool.gov.wales.

Wales has no bulk downloadable school-level performance dataset. Checked
live (2026-08-03) every dataset title under StatsWales's "Schools" and
"Pupils" topics (via https://stats.gov.wales, api.stats.gov.wales/v1): the
GCSE/key stage 4 datasets there all break down by local authority,
national total, or pupil characteristic (sex, FSM, ethnic background,
ALN) - never by individual school. Real school-level headline exam
results are published only through mylocalschool.gov.wales's per-school
pages, which have no bulk API or CSV export - the site's own "Data
Sources" page (mylocalschool.gov.wales/About/DataSources) confirms this
is real, current Key Stage 4 examination data collated from awarding
organisations, not a scraped/estimated figure. wales.py (the school
register adapter) already references this same site as one of
DataMapWales's own input sources, so this is not a new, unvetted source
for this project.

Each school's Summary section is server-rendered as a fixed sequence of
sibling <div class="statistic-block"> elements (value/name/year), present
in the initial HTML with no JavaScript execution required (verified live:
plain httpx GET returns the real figures) - this is the site's own public
per-school page, not its interactive search/filter UI. A metric block is
simply omitted from the page when not applicable to a school (verified
live: special schools omit all five key-stage-4 blocks entirely; no fake
N/A or zero placeholder ever appears), so a metric absent from a school's
page is treated as not applicable, matching this service's don't-guess
policy without any extra handling.

Fetches one page per school (Welsh secondary schools only, since the
"Middle"/"Special" phases were verified live to genuinely omit these
blocks and primary schools have no equivalent headline score published
here at all post-Curriculum for Wales reform) - a small, deliberate delay
between requests avoids hammering a public-facing government website that
was never designed for bulk access.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from catchment_zone_ingestor.models import SchoolMetric

logger = logging.getLogger(__name__)

WALES_SCHOOL_PAGE_URL = "https://mylocalschool.gov.wales/School/{urn}"

#: Politeness delay between per-school page fetches (seconds).
REQUEST_DELAY_SECONDS = 0.3

_STATISTIC_BLOCK_PATTERN = re.compile(
    r'<div class="statistic-value">\s*([^<]*?)\s*</div>\s*'
    r'<div class="statistic-name">\s*([^<]*?)\s*</div>\s*'
    r'<div class="statistic-year">\s*([^<]*?)\s*</div>',
    re.DOTALL,
)

#: Maps mylocalschool.gov.wales's exact statistic-name text to this
#: service's metric_code. Verified live against multiple real secondary
#: schools (2026-08-03); label text must match exactly, not fuzzily.
METRIC_NAME_TO_CODE = {
    "Capped 9 points score (interim measures version)": "wales_ks4_capped9_points_score",
    "Literacy points score": "wales_ks4_literacy_points_score",
    "Numeracy points score": "wales_ks4_numeracy_points_score",
    "Science points score": "wales_ks4_science_points_score",
    "Welsh Baccalaureate Skills Challenge Certificate points score": "wales_ks4_welsh_bacc_points_score",
}


@dataclass
class WalesPerformanceFetchResult:
    metrics: list[SchoolMetric] = field(default_factory=list)
    schools_fetched: int = 0
    schools_failed: int = 0
    failure_samples: list[str] = field(default_factory=list)


def _parse_value(raw: str) -> float | None:
    cleaned = raw.strip().lstrip("£").rstrip("%")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _academic_year_from_calendar_year(raw: str) -> str | None:
    """mylocalschool.gov.wales labels each result with the single calendar
    year exams were sat/published (e.g. "2025"), not this service's
    "YYYY-YYYY" academic year convention. Results published in year N
    correspond to the academic year ending in the summer of year N."""
    year = raw.strip()
    if not (year.isdigit() and len(year) == 4):
        return None
    end_year = int(year)
    return f"{end_year - 1}-{end_year}"


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(httpx.TransportError),
)
def fetch_school_performance(client: httpx.Client, urn: str) -> list[SchoolMetric]:
    """Fetch and parse one school's key stage 4 performance summary.

    Returns an empty list (not an error) for a school with no performance
    blocks at all - the real, expected shape for special/non-key-stage-4
    schools - and only creates a SchoolMetric for metric names actually
    present on the page.
    """
    response = client.get(WALES_SCHOOL_PAGE_URL.format(urn=urn), params={"lang": "en"})
    response.raise_for_status()
    metrics: list[SchoolMetric] = []
    for raw_value, raw_name, raw_year in _STATISTIC_BLOCK_PATTERN.findall(response.text):
        metric_code = METRIC_NAME_TO_CODE.get(raw_name.strip())
        if metric_code is None:
            continue
        academic_year = _academic_year_from_calendar_year(raw_year)
        if academic_year is None:
            continue
        metrics.append(
            SchoolMetric(
                school_urn=urn,
                metric_code=metric_code,
                academic_year=academic_year,
                value_numeric=_parse_value(raw_value),
                source_release="mylocalschool.gov.wales",
            )
        )
    return metrics


def fetch_all_schools_performance(client: httpx.Client, urns: list[str]) -> WalesPerformanceFetchResult:
    """Fetches performance data for each URN in turn, tolerating a single
    school's fetch failure without losing the rest (consistent with every
    other adapter's per-row tolerance in this service)."""
    result = WalesPerformanceFetchResult()
    for i, urn in enumerate(urns):
        try:
            result.metrics.extend(fetch_school_performance(client, urn))
            result.schools_fetched += 1
        except Exception as exc:
            result.schools_failed += 1
            if len(result.failure_samples) < 20:
                result.failure_samples.append(f"urn={urn}: {exc}")
            logger.warning("could not fetch Wales school performance page", extra={"urn": urn, "error": str(exc)})
        if i < len(urns) - 1:
            time.sleep(REQUEST_DELAY_SECONDS)
    return result
