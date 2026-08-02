"""Wales school register adapter: DataMapWales maintained-schools WFS layer.

Wales has no GIAS equivalent either. The real, live source used here is
DataMapWales (a GeoNode/GeoServer instance run by Welsh Government),
layer geonode:maintained_schools_wg, queried via standard OGC WFS 2.0
GetFeature requests
(https://datamap.gov.wales/geoserver/wfs?service=WFS&version=2.0.0&...).
Verified live 2026-08-02: 1,440 schools, srsName=EPSG:4326 returns
coordinates already in WGS84 (no reprojection needed), standard
startIndex/count pagination, no special headers required. DataMapWales's
own documentation states this layer is compiled from OS AddressBase,
mylocalschool.gov.wales and Welsh Government's own published address
list of schools.

Like Scotland's ScottishSchoolRoll, this layer carries no open/closed
status column - only "maintained" (i.e. currently operating, state
funded) schools appear at all - so every row here is treated as
SchoolStatus.OPEN. A real, stated limitation, not an oversight.

Local authority code collision: Wales's la_code values (e.g. 660 for
Isle of Anglesey) are small 3-digit numbers in the same numeric format as
England's GIAS local authority codes (e.g. 373 for Sheffield). Whether
the two schemes' actual values ever collide could not be confirmed
against a live, definitive source (GIAS was unavailable when this was
written), so Wales's local authority codes are prefixed "W-" here
purely as a collision-safety measure - local_authorities.code is this
service's own internal primary key, not required to reproduce Wales's
raw la_code unmodified, and getting this wrong silently (two different
authorities sharing one row) would be a much worse failure mode than an
unnecessary prefix.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from catchment_zone_ingestor.models import LocalAuthority, Nation, School, SchoolStatus

logger = logging.getLogger(__name__)

#: GeoServer WFS endpoint for DataMapWales's maintained-schools layer.
#: Verified live 2026-08-02: 1,440 features, no browser User-Agent required
#: (unlike GIAS/Open Data NI).
WALES_WFS_URL = "https://datamap.gov.wales/geoserver/wfs"
WALES_SCHOOLS_TYPE_NAME = "geonode:maintained_schools_wg"

#: GeoServer serves whatever count is asked for in one response for this
#: layer's current size (~1,440), but pagination is still implemented
#: defensively rather than requesting an unbounded count in one call, matching
#: this service's general "always page" policy for external sources.
_PAGE_SIZE = 500

#: Religious-character values this layer uses to mean "none recorded",
#: which must not be stored as a literal religious character.
_BLANK_RELIGIOUS_CHARACTER_MARKERS = {"---", "not available", ""}

#: Wales's own local authority codes are prefixed with this to guarantee no
#: collision with England's GIAS local authority codes; see module
#: docstring for why this could not be confirmed unnecessary instead.
_WALES_LA_CODE_PREFIX = "W-"


class WalesDiscoveryError(RuntimeError):
    """Raised when the Wales schools WFS layer returns an unexpected shape."""


class _RawWalesFeature(BaseModel):
    """Loosely-typed model for one maintained_schools_wg feature's properties."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    school_code: int = Field(alias="school_code")
    school_name: str = Field(alias="school_name")
    la_code: int | None = Field(default=None, alias="la_code")
    local_authority: str | None = Field(default=None, alias="local_authority")
    sector: str | None = Field(default=None, alias="sector")
    governance: str | None = Field(default=None, alias="governance")
    school_type: str | None = Field(default=None, alias="school_type")
    religious_character: str | None = Field(default=None, alias="religious_character")
    address_1: str | None = Field(default=None, alias="address_1")
    address_2: str | None = Field(default=None, alias="address_2")
    address_3: str | None = Field(default=None, alias="address_3")
    address_4: str | None = Field(default=None, alias="address_4")
    postcode: str | None = Field(default=None, alias="postcode")
    phone_number: str | None = Field(default=None, alias="phone_number")
    pupils: str | None = Field(default=None, alias="pupils")


@dataclass
class WalesParseResult:
    """Mirrors gias.ParseResult/scotland.ScotlandParseResult: local
    authorities must be upserted before schools (foreign key)."""

    schools: list[School]
    local_authorities: list[LocalAuthority] = field(default_factory=list)
    rows_processed: int = 0
    rows_rejected: int = 0
    rejection_samples: list[str] = field(default_factory=list)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    retry=retry_if_exception_type(httpx.TransportError),
)
def _fetch_page(client: httpx.Client, start_index: int) -> dict[str, Any]:
    params: dict[str, str | int] = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": WALES_SCHOOLS_TYPE_NAME,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "count": _PAGE_SIZE,
        "startIndex": start_index,
    }
    response = client.get(WALES_WFS_URL, params=params)
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    if payload.get("type") != "FeatureCollection":
        raise WalesDiscoveryError(f"unexpected WFS response shape: {payload!r}"[:500])
    return payload


def fetch_wales_schools(client: httpx.Client) -> list[dict[str, Any]]:
    """Page through the maintained_schools_wg WFS layer and return all
    features as GeoJSON."""
    all_features: list[dict[str, Any]] = []
    start_index = 0

    while True:
        payload = _fetch_page(client, start_index)
        features = payload.get("features", [])
        all_features.extend(features)
        if len(features) < _PAGE_SIZE:
            break
        start_index += _PAGE_SIZE

    return all_features


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


def _clean_religious_character(raw: str | None) -> str | None:
    if raw is None:
        return None
    cleaned = raw.strip()
    if cleaned.lower() in _BLANK_RELIGIOUS_CHARACTER_MARKERS:
        return None
    return cleaned


def _parse_optional_int(raw: str | None) -> int | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _feature_to_school(feature: dict[str, Any]) -> School:
    properties = feature.get("properties", {}) or {}
    parsed = _RawWalesFeature.model_validate(properties)

    urn = str(parsed.school_code).strip()
    if not urn or urn == "0":
        raise ValueError(f"school_code is missing or invalid: {parsed.school_code!r}")
    name = parsed.school_name.strip()
    if not name:
        raise ValueError("school_name is blank")

    local_authority_code = (
        f"{_WALES_LA_CODE_PREFIX}{parsed.la_code}" if parsed.la_code is not None else None
    )

    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") or [None, None]
    longitude, latitude = [*coordinates, None, None][:2]

    return School(
        urn=urn,
        nation=Nation.WALES,
        school_name=name,
        normalised_name=_normalise_name(name),
        # No closure/status field exists in this source; see module
        # docstring - every row is treated as currently open (maintained).
        status=SchoolStatus.OPEN,
        establishment_type_code="",
        establishment_type_name=parsed.governance or "",
        phase_code="",
        phase_name=parsed.school_type or parsed.sector or "",
        religious_character=_clean_religious_character(parsed.religious_character),
        street=parsed.address_1 or None,
        locality=parsed.address_2 or None,
        town=parsed.address_3 or None,
        county=parsed.address_4 or None,
        postcode=parsed.postcode or None,
        postcode_prefix=_postcode_prefix(parsed.postcode),
        latitude=latitude,
        longitude=longitude,
        local_authority_code=local_authority_code,
        number_of_pupils=_parse_optional_int(parsed.pupils),
        telephone=parsed.phone_number or None,
    )


def _collect_local_authority(properties: dict[str, Any], seen: dict[str, str]) -> None:
    """Record a (prefixed la_code -> local_authority name) pair, mirroring
    gias._collect_local_authority: best-effort, never rejects the row's
    school."""
    raw_code = properties.get("la_code")
    name = str(properties.get("local_authority") or "").strip()
    if raw_code is None or not name:
        return
    code = f"{_WALES_LA_CODE_PREFIX}{raw_code}"
    if code not in seen:
        seen[code] = name


def parse_wales_schools(features: list[dict[str, Any]], row_limit: int | None = None) -> WalesParseResult:
    """Map raw maintained_schools_wg GeoJSON features to School rows, plus
    the distinct local authorities referenced.

    Defensive per-feature, mirroring gias.parse_establishment_csv /
    scotland.parse_scotland_schools.
    """
    result = WalesParseResult(schools=[])
    local_authorities_by_code: dict[str, str] = {}

    for feature in features:
        if row_limit is not None and result.rows_processed >= row_limit:
            break
        result.rows_processed += 1
        properties = feature.get("properties", {}) or {}
        _collect_local_authority(properties, local_authorities_by_code)
        try:
            school = _feature_to_school(feature)
            result.schools.append(school)
        except (ValidationError, ValueError, KeyError) as exc:
            result.rows_rejected += 1
            if len(result.rejection_samples) < 20:
                school_code = properties.get("school_code", "?")
                result.rejection_samples.append(f"school_code={school_code}: {exc}")

    result.local_authorities = [
        LocalAuthority(code=code, name=name, nation=Nation.WALES)
        for code, name in local_authorities_by_code.items()
    ]
    return result
