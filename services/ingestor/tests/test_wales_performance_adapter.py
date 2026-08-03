"""Tests for the Wales school performance adapter (mylocalschool.gov.wales).

The HTML fragments below are entirely invented (values and the school
adjacent to them are made up) but shaped exactly like a real school page's
Summary section, verified live against mylocalschool.gov.wales on
2026-08-03.
"""

from __future__ import annotations

import httpx
import pytest

from catchment_zone_ingestor.adapters.wales_performance import (
    fetch_all_schools_performance,
    fetch_school_performance,
)

_SECONDARY_SCHOOL_HTML = """
<div class="statistic-block">
<div class="statistic-value">
537                </div>
<div class="statistic-name">
    Number of pupils, 2025
</div>
<div class="statistic-year">
    2025
</div>
</div>
<div class="statistic-block">
<div class="statistic-value">
335.5                </div>
<div class="statistic-name">
    Capped 9 points score (interim measures version)
</div>
<div class="statistic-year">
    2025
</div>
</div>
<div class="statistic-block">
<div class="statistic-value">
37                </div>
<div class="statistic-name">
    Literacy points score
</div>
<div class="statistic-year">
    2025
</div>
</div>
"""

_SPECIAL_SCHOOL_HTML = """
<div class="statistic-block">
<div class="statistic-value">
123                </div>
<div class="statistic-name">
    Number of pupils, 2025
</div>
<div class="statistic-year">
    2025
</div>
</div>
<div class="statistic-block">
<div class="statistic-value">
£29306                </div>
<div class="statistic-name">
    School budget per pupil
</div>
<div class="statistic-year">
    2025
</div>
</div>
"""


def _client_returning(html: str) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_extracts_known_performance_metrics() -> None:
    with _client_returning(_SECONDARY_SCHOOL_HTML) as client:
        metrics = fetch_school_performance(client, "9999001")
    codes = {m.metric_code for m in metrics}
    assert codes == {"wales_ks4_capped9_points_score", "wales_ks4_literacy_points_score"}


def test_converts_calendar_year_to_academic_year() -> None:
    with _client_returning(_SECONDARY_SCHOOL_HTML) as client:
        metrics = fetch_school_performance(client, "9999001")
    assert all(m.academic_year == "2024-2025" for m in metrics)


def test_parses_numeric_value_correctly() -> None:
    with _client_returning(_SECONDARY_SCHOOL_HTML) as client:
        metrics = fetch_school_performance(client, "9999001")
    capped9 = next(m for m in metrics if m.metric_code == "wales_ks4_capped9_points_score")
    assert capped9.value_numeric == pytest.approx(335.5)


def test_school_with_no_performance_blocks_returns_empty_list() -> None:
    """A special school's page (verified live) omits all key stage 4
    blocks entirely rather than showing a placeholder - must not be
    treated as a fetch error."""
    with _client_returning(_SPECIAL_SCHOOL_HTML) as client:
        metrics = fetch_school_performance(client, "9999002")
    assert metrics == []


def test_ignores_non_performance_statistic_blocks() -> None:
    with _client_returning(_SECONDARY_SCHOOL_HTML) as client:
        metrics = fetch_school_performance(client, "9999001")
    assert all(m.metric_code != "number_of_pupils" for m in metrics)


def test_fetch_all_tolerates_one_school_failing() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        urn = request.url.path.rsplit("/", 1)[-1]
        calls.append(urn)
        if urn == "9999999":
            return httpx.Response(500, text="server error")
        return httpx.Response(200, text=_SECONDARY_SCHOOL_HTML)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_all_schools_performance(client, ["9999001", "9999999", "9999003"])

    assert result.schools_fetched == 2
    assert result.schools_failed == 1
    assert len(result.failure_samples) == 1
    assert "9999999" in result.failure_samples[0]
    # Two successful schools x two metrics each in the fixture.
    assert len(result.metrics) == 4
