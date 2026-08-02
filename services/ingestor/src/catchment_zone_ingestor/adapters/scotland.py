"""Scotland school register adapter: ScottishSchoolRoll ArcGIS MapServer.

Scotland has no GIAS equivalent (no single DfE-style API). The real,
live source used here is the Scottish Government's ScottishSchoolRoll
layer, published as an ArcGIS MapServer/FeatureServer at
https://maps.gov.scot/server/rest/services/ScotGov/UtilityGovernmental/MapServer/0
(verified live: 2,483 schools, standard ArcGIS /query pagination, no
special headers required, unlike GIAS/Open Data NI's WAFs). Its own field
documentation states the dataset is derived from two published Scottish
Government statistics releases ("School contact details" and "School
level summary statistics"), refreshed periodically, not a live
transactional register.

The dataset carries no open/closed status column at all (unlike GIAS,
which has an explicit EstablishmentStatus field): every row here is
treated as SchoolStatus.OPEN. This is a real, stated limitation, not an
oversight - the source itself only appears to list currently operating
schools, so there is nothing to read a closure state from. If Scotland
ever publishes a closure/status field, this should switch to reading it
rather than assuming.

The dataset's own field documentation states the "SchUID" field (a SEED
code with a P/S/SP suffix distinguishing primary/secondary/special
provision that share a campus and SEED code) should be used as the
unique identifier, not the bare SEED code, since a single SEED code can
have multiple SchUID rows. schuid is used as School.urn here for exactly
that reason.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from catchment_zone_ingestor.adapters.catchments import query_all_features
from catchment_zone_ingestor.models import LocalAuthority, Nation, School, SchoolStatus

logger = logging.getLogger(__name__)

#: The ArcGIS REST endpoint for the ScottishSchoolRoll layer (layer id 0 on
#: this MapServer). Verified live 2026-08-02: 2,483 features, maxRecordCount
#: 1000, requires no browser User-Agent (unlike GIAS/Open Data NI).
SCOTLAND_SCHOOLS_LAYER_URL = (
    "https://maps.gov.scot/server/rest/services/ScotGov/UtilityGovernmental/MapServer/0"
)


class ScotlandDiscoveryError(RuntimeError):
    """Raised when the Scotland schools layer returns an unexpected shape."""


class _RawScotlandFeature(BaseModel):
    """Loosely-typed model for one ScottishSchoolRoll feature's properties.

    Column names are lowercase and fixed (unlike GIAS's CSV, which varies
    casing between extract dates), but extra="ignore" is kept for the same
    reason as GIAS's RawGiasRow: the layer carries many deprivation/rurality
    columns this service does not use, and a future field addition should
    not break parsing.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    schuid: str = Field(alias="schuid")
    schoolname: str = Field(alias="schoolname")
    schooltype: str | None = Field(default=None, alias="schooltype")
    centretype: str | None = Field(default=None, alias="centretype")
    denomination: str | None = Field(default=None, alias="denomination")
    addressline1: str | None = Field(default=None, alias="addressline1")
    addressline2: str | None = Field(default=None, alias="addressline2")
    addressline3: str | None = Field(default=None, alias="addressline3")
    postcode: str | None = Field(default=None, alias="postcode")
    lacode: str | None = Field(default=None, alias="lacode")
    laname: str | None = Field(default=None, alias="laname")
    latitude: float | None = Field(default=None, alias="latitude")
    longitude: float | None = Field(default=None, alias="longitude")
    email: str | None = Field(default=None, alias="email")
    phone: str | None = Field(default=None, alias="phone")
    website: str | None = Field(default=None, alias="website")
    pupilroll: float | None = Field(default=None, alias="pupilroll")


@dataclass
class ScotlandParseResult:
    """Outcome of mapping raw ScottishSchoolRoll features to School rows,
    plus the distinct local authorities referenced, mirroring GIAS's
    ParseResult shape for the same reason: local_authorities must be
    upserted before schools in the same import (schools.local_authority_code
    is a foreign key)."""

    schools: list[School]
    local_authorities: list[LocalAuthority] = field(default_factory=list)
    rows_processed: int = 0
    rows_rejected: int = 0
    rejection_samples: list[str] = field(default_factory=list)


def fetch_scotland_schools(client: httpx.Client) -> list[dict[str, Any]]:
    """Fetch every ScottishSchoolRoll feature, paginated, as GeoJSON.

    Reuses the existing ArcGIS FeatureServer pagination helper from the
    catchments adapter: the ScottishSchoolRoll MapServer is queried with
    the same /query?f=geojson&outSR=4326 shape as the Sheffield catchment
    FeatureServer, just a point layer instead of a polygon layer.
    """
    result = query_all_features(client, SCOTLAND_SCHOOLS_LAYER_URL)
    return result.features


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


def _feature_to_school(feature: dict[str, Any]) -> School:
    properties = feature.get("properties", {}) or {}
    parsed = _RawScotlandFeature.model_validate(properties)

    urn = parsed.schuid.strip()
    if not urn:
        raise ValueError("schuid is blank")
    name = parsed.schoolname.strip()
    if not name:
        raise ValueError("schoolname is blank")

    number_of_pupils = int(parsed.pupilroll) if parsed.pupilroll is not None else None

    return School(
        urn=urn,
        nation=Nation.SCOTLAND,
        school_name=name,
        normalised_name=_normalise_name(name),
        # No closure/status field exists in this source; see module
        # docstring - every row is treated as currently open.
        status=SchoolStatus.OPEN,
        establishment_type_code="",
        establishment_type_name=parsed.centretype or "",
        phase_code="",
        phase_name=parsed.schooltype or "",
        religious_character=parsed.denomination or None,
        street=parsed.addressline1 or None,
        locality=parsed.addressline2 or None,
        town=parsed.addressline3 or None,
        postcode=parsed.postcode or None,
        postcode_prefix=_postcode_prefix(parsed.postcode),
        latitude=parsed.latitude,
        longitude=parsed.longitude,
        local_authority_code=parsed.lacode or None,
        number_of_pupils=number_of_pupils,
        website=parsed.website or None,
        telephone=parsed.phone or None,
    )


def _collect_local_authority(properties: dict[str, Any], seen: dict[str, str]) -> None:
    """Record a (lacode -> laname) pair, mirroring gias._collect_local_authority:
    best-effort and defensive, never a reason to reject the row's school."""
    code = str(properties.get("lacode") or "").strip()
    name = str(properties.get("laname") or "").strip()
    if code and name and code not in seen:
        seen[code] = name


def parse_scotland_schools(
    features: list[dict[str, Any]], row_limit: int | None = None
) -> ScotlandParseResult:
    """Map raw ScottishSchoolRoll GeoJSON features to School rows, plus the
    distinct local authorities referenced by any feature.

    Defensive per-feature, mirroring gias.parse_establishment_csv: a
    feature that fails validation is counted and skipped rather than
    aborting the whole import.
    """
    result = ScotlandParseResult(schools=[])
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
                schuid = properties.get("schuid", "?")
                result.rejection_samples.append(f"schuid={schuid}: {exc}")

    result.local_authorities = [
        LocalAuthority(code=code, name=name, nation=Nation.SCOTLAND)
        for code, name in local_authorities_by_code.items()
    ]
    return result
