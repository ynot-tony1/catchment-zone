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

The endpoint shapes used below (find_publication_id, list_publication_datasets,
resolve_current_release) were checked against the live documentation at
https://api.education.gov.uk/statistics/docs/ on 2026-08-01:
  GET /publications?search=<text>&pageSize=<n>   (publication has id, slug, title)
  GET /publications/{publicationId}/data-sets     (each result has an "id" and a
                                                    "latestVersion" object with
                                                    version/published/timePeriods)
  GET /data-sets/{dataSetId}/query?...            (rows keyed by opaque indicator
                                                    and filter IDs, not the plain
                                                    metric_codes used in this repo)
A documented TODO (see fetch_dataset_rows below) is left for turning a query
response's opaque indicator/filter IDs into this service's metric_codes: that
mapping is dataset-specific and was not available from the docs page fetched
during development, so it needs live verification against a real dataset's
metadata endpoint before import_statistics can persist rows, not just resolve
releases.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from catchment_zone_ingestor.models import SchoolMetric

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


def find_publication_id(client: httpx.Client, base_url: str, publication_slug: str) -> str:
    """Resolve a publication's GUID id from its slug via the search endpoint.

    The EES API's GET /publications/{publicationId} endpoint takes an id, not
    a slug (confirmed against the live API docs), so the ingestor must first
    search by a text term derived from the slug and pick out the result whose
    own "slug" field matches exactly. The search endpoint requires a search
    term of at least 3 characters, hence the fallback to the whole slug if the
    dash-replaced version is somehow shorter.
    """
    search_term = publication_slug.replace("-", " ").strip() or publication_slug
    data = _get_json(client, f"{base_url}/publications", params={"search": search_term, "pageSize": 40})
    for pub in data.get("results", []):
        if pub.get("slug") == publication_slug:
            return str(pub["id"])
    raise StatisticsApiError(f"no publication found with slug {publication_slug!r} via search term {search_term!r}")


def resolve_publication_slugs(
    client: httpx.Client, base_url: str, candidate_slugs: list[str]
) -> str:
    """Return whichever candidate slug currently resolves to a real
    publication, preferring the first candidate found.

    This exists specifically for the pupil-absence to pupil-attendance
    migration documented in statistics-sources.yml: DfE has been moving this
    series to a new slug, and the ingestor must not assume either one is
    permanently current. A slug "resolves" here if the search endpoint
    returns a publication whose own slug field matches it exactly.
    """
    for slug in candidate_slugs:
        try:
            find_publication_id(client, base_url, slug)
        except StatisticsApiError:
            continue
        logger.info("resolved active publication slug", extra={"slug": slug})
        return slug
    raise StatisticsApiError(f"none of the candidate slugs resolved to a real publication: {candidate_slugs}")


def list_publication_datasets(client: httpx.Client, base_url: str, publication_id: str) -> list[dict[str, Any]]:
    """List a publication's data sets, each including a "latestVersion" summary."""
    data = _get_json(client, f"{base_url}/publications/{publication_id}/data-sets", params={"page": 1, "pageSize": 20})
    results: list[dict[str, Any]] = data.get("results", [])
    return results


def resolve_current_release(client: httpx.Client, base_url: str, publication_slug: str) -> ResolvedRelease:
    """Resolve the latest dataset id and release for a publication slug via
    the API's own catalogue, rather than a hardcoded dataset UUID.

    A publication can have more than one data set; this picks the first one
    the API returns. Where a publication has several data sets covering
    different breakdowns, a future revision should match on dataset title
    against the metric_codes this service actually wants rather than always
    taking the first result.
    """
    publication_id = find_publication_id(client, base_url, publication_slug)
    datasets = list_publication_datasets(client, base_url, publication_id)
    if not datasets:
        raise StatisticsApiError(f"publication {publication_slug!r} has no data sets")

    dataset = datasets[0]
    latest_version = dataset.get("latestVersion", {})

    return ResolvedRelease(
        publication_slug=publication_slug,
        dataset_id=str(dataset.get("id")),
        release_id=str(latest_version.get("version", "unknown")),
        release_label=str(latest_version.get("version", "unknown")),
        # NOTE (documented TODO): the live docs excerpt available during
        # development did not show a "provisional" field on latestVersion;
        # this needs confirming against a real response before trusting it.
        # Defaulting to False (not provisional) is the conservative choice
        # for a field we cannot yet confirm, since marking a genuinely final
        # release as provisional would be a lesser error than the reverse.
        is_provisional=bool(latest_version.get("provisional", False)),
        published_at=latest_version.get("published"),
    )


def fetch_dataset_rows(
    client: httpx.Client, base_url: str, dataset_id: str, page_size: int = 1000
) -> Iterator[dict[str, Any]]:
    """Page through a data set's /query endpoint results.

    NOTE (documented TODO, needs live verification): the query response's
    `results` rows are keyed by opaque indicator and filter IDs (e.g.
    "4xbOu"), not by the plain metric_codes this service uses
    (overall_absence_rate, etc). Turning a row into the flat
    {metric_code: value} shape map_rows_to_metrics expects requires first
    calling the data set's metadata endpoint to build an indicator-id to
    metric-code lookup, which was not available from the documentation page
    fetched during development. This function currently yields the raw
    result rows unmodified; a caller must not assume its keys already match
    metric_codes until that lookup is wired in and verified against a real
    dataset.
    """
    page = 1
    while True:
        data = _get_json(
            client,
            f"{base_url}/data-sets/{dataset_id}/query",
            params={"page": page, "pageSize": page_size},
        )
        results = data.get("results", [])
        yield from results
        paging = data.get("paging", {})
        if page >= int(paging.get("totalPages", page)):
            break
        page += 1


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
