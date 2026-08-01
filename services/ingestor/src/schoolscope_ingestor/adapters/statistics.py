"""DfE Explore Education Statistics (EES) API adapter.

Queries api.education.gov.uk/statistics/v1 for the publications listed in
config/statistics-sources.yml, resolves each publication's current dataset id
and latest release via the API's own catalogue/search endpoints (never a
hardcoded dataset UUID, since DfE reassigns and supersedes releases over
time), downloads the release's data, and maps rows to SchoolMetric records.

Suppression and provisional flags are read from the source data and carried
through untouched: a suppressed value is stored with suppressed=True and a
null value_numeric (GIAS/DfE suppress small cohorts to protect pupil
identities; this service must never attempt to estimate or back out a
suppressed value). A provisional release's rows are stored with
provisional=True so the web app can label them accordingly rather than
presenting them as final.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from schoolscope_ingestor.models import SchoolMetric

logger = logging.getLogger(__name__)

#: Values the EES API is known to use to flag a suppressed statistic in a
#: results row, checked case-insensitively against the raw cell value.
SUPPRESSED_MARKERS = {"c", "x", "low", "suppressed", ":"}
#: Markers meaning "not applicable", stored as neither a value nor a
#: suppression (there is nothing being withheld, the metric just does not
#: apply, e.g. sixth form places at a school with no sixth form).
NOT_APPLICABLE_MARKERS = {"n/a", "na", "-"}


@dataclass
class PublicationConfig:
    publication_slug: str
    display_name: str
    metric_codes: list[str]
    update_frequency: str
    applies_to_phases: list[str]
    notes: str = ""


@dataclass
class ResolvedRelease:
    publication_slug: str
    dataset_id: str
    release_id: str
    release_label: str
    is_provisional: bool
    published_at: str | None


class StatisticsApiError(RuntimeError):
    """Raised when the EES API returns an unexpected shape or no active release."""


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(httpx.TransportError),
)
def _get_json(client: httpx.Client, url: str, params: dict[str, Any] | None = None) -> Any:
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def resolve_publication_slugs(
    client: httpx.Client, base_url: str, candidate_slugs: list[str]
) -> str:
    """Return whichever candidate slug the API's publication list currently
    marks active, preferring the first candidate found active.

    This exists specifically for the pupil-absence to pupil-attendance
    migration documented in statistics-sources.yml: DfE has been moving this
    series to a new slug, and the ingestor must not assume either one is
    permanently current.
    """
    for slug in candidate_slugs:
        try:
            data = _get_json(client, f"{base_url}/publications/{slug}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                continue
            raise
        if data.get("status", "active") == "active" or data:
            logger.info("resolved active publication slug", extra={"slug": slug})
            return str(slug)
    raise StatisticsApiError(f"none of the candidate slugs are active: {candidate_slugs}")


def resolve_current_release(
    client: httpx.Client, base_url: str, publication_slug: str
) -> ResolvedRelease:
    """Resolve the latest dataset id and release for a publication slug via
    the API's own catalogue, rather than a hardcoded dataset UUID."""
    publication = _get_json(client, f"{base_url}/publications/{publication_slug}")
    releases = publication.get("releases") or publication.get("data", {}).get("releases")
    if not releases:
        raise StatisticsApiError(f"publication {publication_slug!r} has no releases in the API response")

    latest = releases[0]
    for release in releases:
        if release.get("latestRelease") or release.get("isLatest"):
            latest = release
            break

    datasets = latest.get("datasets") or []
    if not datasets:
        raise StatisticsApiError(f"release for {publication_slug!r} has no datasets")
    dataset = datasets[0]

    return ResolvedRelease(
        publication_slug=publication_slug,
        dataset_id=str(dataset.get("id") or dataset.get("datasetId")),
        release_id=str(latest.get("id") or latest.get("releaseId")),
        release_label=str(latest.get("label") or latest.get("releaseName") or "unknown"),
        is_provisional=bool(latest.get("provisional", False)),
        published_at=latest.get("published"),
    )


def _classify_cell(raw_value: str | None) -> tuple[float | None, bool]:
    """Return (value_numeric, suppressed) for a raw statistic cell.

    Handles suppression markers, not-applicable markers, and genuine
    numeric values (including a literal 0, which must not be confused with
    a missing value).
    """
    if raw_value is None:
        return None, False
    cell = raw_value.strip()
    if cell == "":
        return None, False
    lowered = cell.lower()
    if lowered in SUPPRESSED_MARKERS:
        return None, True
    if lowered in NOT_APPLICABLE_MARKERS:
        return None, False
    try:
        return float(cell), False
    except ValueError:
        # Unrecognised non-numeric marker: treat conservatively as suppressed
        # rather than silently dropping or misreading it as a number.
        logger.warning("unrecognised statistic cell value treated as suppressed", extra={"raw_value": raw_value})
        return None, True


def map_rows_to_metrics(
    rows: Iterator[dict[str, Any]],
    metric_codes: list[str],
    academic_year_field: str,
    school_urn_field: str,
    release: ResolvedRelease,
) -> Iterator[SchoolMetric]:
    """Map raw EES data-table rows to SchoolMetric records.

    Each input row is expected to contain a school URN column, an academic
    year (or time period) column, and one column per metric code in
    metric_codes. Rows for URNs that fail basic sanity checks are skipped
    defensively rather than raised, consistent with the GIAS adapter's
    per-row tolerance.
    """
    for row in rows:
        urn = str(row.get(school_urn_field, "")).strip()
        academic_year = str(row.get(academic_year_field, "")).strip()
        if not urn or not academic_year:
            continue
        for metric_code in metric_codes:
            if metric_code not in row:
                continue
            value_numeric, suppressed = _classify_cell(row.get(metric_code))
            yield SchoolMetric(
                school_urn=urn,
                metric_code=metric_code,
                academic_year=academic_year,
                value_numeric=value_numeric,
                suppressed=suppressed,
                provisional=release.is_provisional,
                source_release=release.release_label,
                source_published_at=release.published_at,
            )
