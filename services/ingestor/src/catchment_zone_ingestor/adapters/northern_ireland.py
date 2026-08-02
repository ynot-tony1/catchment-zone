"""Northern Ireland school register adapter: Open Data NI "School Locations".

Northern Ireland has no GIAS equivalent either. The only real source found
for this project is Open Data NI's CKAN-hosted "School Locations" dataset
(package id "locate-a-school", https://admin.opendatani.gov.uk), published
by the Department of Education.

Unlike GIAS/Scotland/Wales, this source is genuinely stale: its only
resource is a single CSV whose filename and content both date it to
February 2016 (verified live 2026-08-02 - the CKAN package metadata claims
"quarterly" update frequency, but num_resources is 1 and that one resource
is a decade old). Importing this as if it were current would misrepresent
it, so every School row sourced from here carries an explicit
source_extract_date of 2016-02-01 - this project's principle throughout
(suppressed statistics shown as suppressed, provisional releases labelled
provisional, catchment coverage marked NOT_AVAILABLE rather than guessed)
is to label a caveat honestly rather than omit the data outright, and this
is the same move applied to source recency. Any UI surfacing Northern
Ireland schools must show this date prominently, not just store it.

Like Open Data NI's underlying WAF, this dataset requires a browser
User-Agent (verified live: the default httpx/CLI user agent gets a 403,
a browser UA gets 200 - the same pattern GIAS uses, handled the same way
here rather than applying it service-wide).

There is no local-authority-equivalent field in this dataset: Northern
Ireland schools are administered centrally by the Education Authority, not
by county councils, so School.local_authority_code is left null throughout
and no LocalAuthority rows are derived from this source. The traditional
six counties are recorded in School.county instead, since that is what the
source actually provides.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from catchment_zone_ingestor.models import Nation, School, SchoolStatus

logger = logging.getLogger(__name__)

_BASE_URL = "https://admin.opendatani.gov.uk"
_PACKAGE_SHOW_URL = f"{_BASE_URL}/api/3/action/package_show"
NORTHERN_IRELAND_PACKAGE_ID = "locate-a-school"

#: Open Data NI blocks non-browser User-Agents (verified live: default
#: httpx UA -> 403, this UA -> 200), the same WAF pattern GIAS uses.
_NI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

#: This source's only resource is dated February 2016 (verified live
#: 2026-08-02: filename "locate-a-school-open-data-feb-2016.csv", CKAN
#: package has num_resources=1 despite claiming quarterly updates). See
#: module docstring for why this is imported anyway, honestly labelled,
#: rather than omitted.
NORTHERN_IRELAND_SOURCE_EXTRACT_DATE = datetime(2016, 2, 1)


class NorthernIrelandDiscoveryError(RuntimeError):
    """Raised when Open Data NI's package metadata has an unexpected shape."""


class _RawNorthernIrelandRow(BaseModel):
    """Loosely-typed model for one row of the School Locations CSV."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    reference: str = Field(alias="Reference")
    institution_name: str = Field(alias="Institution_Name")
    address_1: str | None = Field(default=None, alias="Address_1")
    address_2: str | None = Field(default=None, alias="Address_2")
    address_3: str | None = Field(default=None, alias="Address_3")
    town_name: str | None = Field(default=None, alias="Town_Name")
    county_name: str | None = Field(default=None, alias="County_Name")
    postcode: str | None = Field(default=None, alias="Postcode")
    telephone: str | None = Field(default=None, alias="Telephone")
    institution_type: str | None = Field(default=None, alias="Institution_Type")
    management_type: str | None = Field(default=None, alias="Management_Type")
    latitude: str | None = Field(default=None, alias="Latitude")
    longitude: str | None = Field(default=None, alias="Longitude")
    current_approved_enrolment: str | None = Field(default=None, alias="Current_Approved_Enrolment")


@dataclass
class NorthernIrelandParseResult:
    schools: list[School]
    rows_processed: int = 0
    rows_rejected: int = 0
    rejection_samples: list[str] = field(default_factory=list)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    retry=retry_if_exception_type(httpx.TransportError),
)
def _get_json(client: httpx.Client, url: str, params: dict[str, str] | None = None) -> Any:
    response = client.get(url, params=params, headers=_NI_HEADERS)
    response.raise_for_status()
    return response.json()


def discover_csv_url(client: httpx.Client) -> str:
    """Resolve the current download URL for the School Locations CSV via
    CKAN's package_show API, rather than a hardcoded resource URL, since a
    resource's storage URL is an opaque signed link that can change."""
    payload = _get_json(client, _PACKAGE_SHOW_URL, params={"id": NORTHERN_IRELAND_PACKAGE_ID})
    if not payload.get("success"):
        raise NorthernIrelandDiscoveryError(f"package_show did not succeed: {payload!r}"[:500])
    resources = payload.get("result", {}).get("resources", [])
    csv_resources = [r for r in resources if str(r.get("format", "")).upper() == "CSV"]
    if len(csv_resources) != 1:
        raise NorthernIrelandDiscoveryError(
            f"expected exactly one CSV resource on package {NORTHERN_IRELAND_PACKAGE_ID!r}, "
            f"found {len(csv_resources)}"
        )
    url = csv_resources[0].get("url")
    if not url:
        raise NorthernIrelandDiscoveryError("CSV resource has no url field")
    return str(url)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    retry=retry_if_exception_type(httpx.TransportError),
)
def download_csv(client: httpx.Client, url: str) -> bytes:
    response = client.get(url, follow_redirects=True, headers=_NI_HEADERS)
    response.raise_for_status()
    return response.content


def _postcode_prefix(postcode: str | None) -> str | None:
    if not postcode:
        return None
    stripped = postcode.strip().upper()
    if not stripped:
        return None
    if len(stripped) > 3:
        return stripped[:-3].strip()
    return stripped


def _normalise_name(name: str) -> str:
    return " ".join(name.strip().split()).lower()


def _parse_optional_float(raw: str | None) -> float | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_optional_int(raw: str | None) -> int | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _row_to_school(raw: dict[str, Any]) -> School:
    parsed = _RawNorthernIrelandRow.model_validate(raw)
    urn = parsed.reference.strip()
    if not urn:
        raise ValueError("Reference is blank")
    name = parsed.institution_name.strip()
    if not name:
        raise ValueError("Institution_Name is blank")

    return School(
        urn=urn,
        nation=Nation.NORTHERN_IRELAND,
        school_name=name,
        normalised_name=_normalise_name(name),
        # No closure/status field exists in this source; see module
        # docstring - every row is treated as open as of the 2016 extract.
        status=SchoolStatus.OPEN,
        establishment_type_code="",
        establishment_type_name=parsed.management_type or "",
        phase_code="",
        phase_name=parsed.institution_type or "",
        street=parsed.address_1 or None,
        locality=parsed.address_2 or None,
        town=parsed.town_name or parsed.address_3 or None,
        county=parsed.county_name or None,
        postcode=parsed.postcode or None,
        postcode_prefix=_postcode_prefix(parsed.postcode),
        latitude=_parse_optional_float(parsed.latitude),
        longitude=_parse_optional_float(parsed.longitude),
        number_of_pupils=_parse_optional_int(parsed.current_approved_enrolment),
        telephone=parsed.telephone or None,
        source_extract_date=NORTHERN_IRELAND_SOURCE_EXTRACT_DATE,
    )


def parse_school_locations_csv(content: bytes, row_limit: int | None = None) -> NorthernIrelandParseResult:
    """Parse the School Locations CSV into School rows.

    Defensive per-row, mirroring gias.parse_establishment_csv: a row that
    fails validation is counted and skipped rather than aborting the whole
    import. No local authority derivation here - see module docstring.
    """
    text_stream = io.TextIOWrapper(io.BytesIO(content), encoding="utf-8-sig", newline="")
    reader = csv.DictReader(text_stream)

    result = NorthernIrelandParseResult(schools=[])
    for raw in reader:
        if row_limit is not None and result.rows_processed >= row_limit:
            break
        result.rows_processed += 1
        try:
            school = _row_to_school(raw)
            result.schools.append(school)
        except (ValidationError, ValueError, KeyError) as exc:
            result.rows_rejected += 1
            if len(result.rejection_samples) < 20:
                reference = raw.get("Reference", "?")
                result.rejection_samples.append(f"Reference={reference}: {exc}")

    return result
