"""ArcGIS FeatureServer catchment area adapter.

Queries a local authority's documented ArcGIS FeatureServer /query REST
endpoint (f=geojson, where=1=1, outSR=4326) to retrieve catchment area
features. This is the same documented public REST API the publisher's own
open data portal uses; this adapter never drives the interactive map viewer
UI and never bypasses any access control; every source it reads is public,
documented and licensed for reuse (see config/catchment-sources.yml, which
records the licence text verified for each source and refuses to import a
source without one).

Sheffield's own published metadata (see catchment-sources.yml notes) states
its catchment boundaries are illustrative only, and that legal catchment
membership is defined by postcode and street number lists the council holds
separately. This adapter and everything downstream of it must preserve that
caveat; nothing in this module or its output may claim that falling inside a
catchment polygon guarantees, or makes a household eligible for, a place at
the associated school.
"""

from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass, field
from typing import Any

import httpx
import shapefile
from pyproj import Transformer
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from catchment_zone_ingestor.geometry import (
    InvalidGeometryError,
    compute_bbox,
    compute_geometry_checksum,
    geometry_to_geojson_str,
    simplify_geometry,
    validate_and_repair,
)
from catchment_zone_ingestor.models import CatchmentArea

logger = logging.getLogger(__name__)

WGS84 = "EPSG:4326"

#: ArcGIS query result pagination page size. Kept well under typical server
#: maxRecordCount limits (commonly 1000 or 2000).
PAGE_SIZE = 500


class CatchmentSourceError(RuntimeError):
    """Raised when the FeatureServer cannot be queried at all (network,
    HTTP error, or an unparseable response), as opposed to a single bad
    feature, which is rejected and logged rather than raised."""


@dataclass
class FeatureQueryResult:
    features: list[dict[str, Any]]
    detected_wkid: int | None


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    retry=retry_if_exception_type(httpx.TransportError),
)
def _query_page(client: httpx.Client, feature_server_url: str, offset: int, where: str) -> dict[str, Any]:
    query_url = feature_server_url.rstrip("/") + "/query"
    params: dict[str, str | int] = {
        "where": where,
        "outFields": "*",
        "f": "geojson",
        "outSR": "4326",
        "resultOffset": offset,
        "resultRecordCount": PAGE_SIZE,
    }
    response = client.get(query_url, params=params)
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    if "error" in payload:
        raise CatchmentSourceError(f"ArcGIS query error for {feature_server_url}: {payload['error']}")
    return payload


def query_all_features(client: httpx.Client, feature_server_url: str, where: str = "1=1") -> FeatureQueryResult:
    """Page through an ArcGIS FeatureServer's /query endpoint and return all
    features as GeoJSON, requesting outSR=4326 (WGS84) directly from the
    server so no client-side reprojection is normally needed.

    where defaults to "1=1" (every feature), but some sources publish
    several denomination catchments (e.g. non-denominational, Roman
    Catholic, Gaelic) as attribute values within one shared layer rather
    than as separate layers/services - Argyll and Bute's combined
    Primary/Secondary School Catchment Areas layers, verified live,
    where a where clause like "DENOM='Roman Catholic'" is the only way
    to import one denomination as its own catchment-sources.yml entry
    with its own source_type.
    """
    all_features: list[dict[str, Any]] = []
    offset = 0
    detected_wkid: int | None = None

    while True:
        payload = _query_page(client, feature_server_url, offset, where)
        features = payload.get("features", [])
        crs = payload.get("crs") or {}
        wkid = _extract_wkid(crs)
        if wkid is not None:
            detected_wkid = wkid

        all_features.extend(features)
        if len(features) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return FeatureQueryResult(features=all_features, detected_wkid=detected_wkid)


#: GeoServer refuses startIndex/count pagination on a layer with no
#: declared primary key ("Cannot do natural order without a primary
#: key..."), e.g. Powys's opendata workspace. sortBy=id (GeoServer's
#: built-in feature-id pseudo-column, distinct from any real attribute
#: named "id") gives it a stable order to paginate against; only added
#: as a retry once the plain request has proven necessary, since Angus's
#: XMap Cloud and Clackmannanshire's Cadcorp servers already paginate
#: fine without it and are not known to support this param.
_GEOSERVER_MISSING_PRIMARY_KEY_MARKER = "natural order without a primary key"


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    retry=retry_if_exception_type(httpx.TransportError),
)
def _query_wfs_page(
    client: httpx.Client, service_url: str, type_name: str, start_index: int, sort_by: str | None = None
) -> dict[str, Any]:
    params: dict[str, str | int] = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        # "typenames" (lowercase, plural) is the strict WFS 2.0 spec name
        # and the only form Clackmannanshire's Cadcorp server accepts
        # ("typeName is mandatory" otherwise); verified live that Angus's
        # XMap Cloud server accepts it too, so one param name works for both.
        "typenames": type_name,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "count": PAGE_SIZE,
        "startIndex": start_index,
    }
    if sort_by:
        params["sortBy"] = sort_by
    try:
        response = client.get(service_url, params=params)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if sort_by is None and exc.response.status_code == 400 and _GEOSERVER_MISSING_PRIMARY_KEY_MARKER in exc.response.text:
            return _query_wfs_page(client, service_url, type_name, start_index, sort_by="id")
        raise
    payload: dict[str, Any] = response.json()
    if payload.get("type") != "FeatureCollection":
        raise CatchmentSourceError(f"unexpected WFS response shape for {service_url}: {payload!r}"[:500])
    return payload


def query_all_wfs_features(client: httpx.Client, service_url: str, type_name: str) -> FeatureQueryResult:
    """Page through a generic OGC WFS 2.0 GetFeature endpoint and return all
    features as GeoJSON, requesting srsName=EPSG:4326 directly from the
    server so no client-side reprojection is normally needed.

    Not ArcGIS-specific (unlike query_all_features above): several
    Scottish councils publish catchments through a plain WFS server
    (XMap Cloud, Cadcorp) rather than ArcGIS. Verified live against
    Angus's XMap Cloud WFS, which needs exactly this GetFeature +
    startIndex/count pagination shape.
    """
    all_features: list[dict[str, Any]] = []
    start_index = 0
    detected_wkid: int | None = None

    while True:
        payload = _query_wfs_page(client, service_url, type_name, start_index)
        features = payload.get("features", [])
        crs = payload.get("crs") or {}
        wkid = _extract_wkid(crs)
        if wkid is not None:
            detected_wkid = wkid

        all_features.extend(features)
        if len(features) < PAGE_SIZE:
            break
        start_index += PAGE_SIZE

    return FeatureQueryResult(features=all_features, detected_wkid=detected_wkid)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    retry=retry_if_exception_type(httpx.TransportError),
)
def download_shapefile_zip_features(client: httpx.Client, zip_url: str) -> FeatureQueryResult:
    """Download a zipped ESRI Shapefile and return its records as GeoJSON
    features. Some councils (e.g. Aberdeenshire, Orkney, via Spatial Hub
    Scotland) publish catchments this way instead of ArcGIS or WFS.

    Coordinates are left in the shapefile's native CRS (declared per-source
    as coordinate_reference_system in catchment-sources.yml, e.g.
    EPSG:27700) - detected_wkid is always None here, so downstream
    reproject_if_needed always falls back to that declared CRS rather than
    trying to detect one from a response, unlike the ArcGIS/WFS adapters
    above which usually get EPSG:4326 straight from the server.
    """
    response = client.get(zip_url)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        shp_names = [name for name in archive.namelist() if name.lower().endswith(".shp")]
        if len(shp_names) != 1:
            raise CatchmentSourceError(f"expected exactly one .shp file in {zip_url}, found {shp_names!r}")
        base_name = shp_names[0][: -len(".shp")]

        def _member(extension: str) -> io.BytesIO:
            return io.BytesIO(archive.read(base_name + extension))

        reader = shapefile.Reader(shp=_member(".shp"), dbf=_member(".dbf"), shx=_member(".shx"))
        features = [
            {"type": "Feature", "properties": shape_record.record.as_dict(), "geometry": shape_record.shape.__geo_interface__}
            for shape_record in reader.iterShapeRecords()
        ]

    return FeatureQueryResult(features=features, detected_wkid=None)


def _extract_wkid(crs: dict[str, Any]) -> int | None:
    properties = crs.get("properties", {})
    name = properties.get("name", "")
    # GeoJSON CRS URNs look like "urn:ogc:def:crs:EPSG::4326".
    if "EPSG" in name:
        tail = name.rsplit(":", 1)[-1]
        if tail.isdigit():
            return int(tail)
    return None


def reproject_if_needed(geometry: BaseGeometry, detected_wkid: int | None, fallback_source_crs: str) -> BaseGeometry:
    """Reproject geometry to WGS84 if the server did not already return
    EPSG:4326 despite the outSR=4326 request. Uses detected_wkid from the
    response's crs block when present, otherwise falls back to the CRS
    declared for this source in catchment-sources.yml (e.g. EPSG:27700 for
    Sheffield's native British National Grid data).
    """
    if detected_wkid in (4326, None):
        # Either confirmed already WGS84, or no CRS was reported at all, which
        # for an f=geojson ArcGIS response means the server's default of
        # WGS84 applies (GeoJSON's implicit CRS).
        if detected_wkid == 4326:
            return geometry
        if detected_wkid is None:
            return geometry

    source_epsg = fallback_source_crs.split(":")[-1]
    transformer = Transformer.from_crs(f"EPSG:{source_epsg}", WGS84, always_xy=True)

    from shapely.ops import transform as shapely_transform

    return shapely_transform(transformer.transform, geometry)


def _to_2d_geojson_geometry(geometry: dict[str, Any]) -> dict[str, Any]:
    """Strips any Z/M dimensions beyond X,Y from a raw GeoJSON geometry's
    coordinates. Some ArcGIS servers (e.g. South Lanarkshire's
    Non-Denominational catchments layer, verified live) return 4D
    [lon, lat, z, m] coordinate tuples with a null M (measure) value on
    every point, which shapely's shape() cannot parse - only X, Y and a
    numeric Z are ever meaningful for a catchment boundary, so anything
    past the second coordinate is simply discarded rather than repaired.
    """

    def strip(coords: Any) -> Any:
        if not coords:
            return coords
        if isinstance(coords[0], int | float):
            return coords[:2]
        return [strip(item) for item in coords]

    if "coordinates" not in geometry:
        return geometry
    return {**geometry, "coordinates": strip(geometry["coordinates"])}


@dataclass
class CatchmentBuildResult:
    areas: list[CatchmentArea]
    rejected_count: int = 0
    rejection_samples: list[str] = field(default_factory=list)


def build_catchment_areas(
    features: list[dict[str, Any]],
    source_id: str,
    area_type: str,
    academic_year: str,
    name_field_candidates: list[str],
    detected_wkid: int | None,
    fallback_source_crs: str,
    valid_from_iso: str,
    simplify_tolerance: float | None = None,
) -> CatchmentBuildResult:
    """Turn raw ArcGIS GeoJSON features into validated CatchmentArea rows.

    Each feature is handled independently: an invalid or unrepairable
    geometry is counted and logged, not raised, so one bad polygon in a
    council's dataset does not block importing the rest of that council's
    catchment areas.
    """
    from catchment_zone_ingestor.geometry import DEFAULT_SIMPLIFY_TOLERANCE_DEGREES

    tolerance = simplify_tolerance if simplify_tolerance is not None else DEFAULT_SIMPLIFY_TOLERANCE_DEGREES
    result = CatchmentBuildResult(areas=[])

    for index, feature in enumerate(features):
        area_name = _extract_name(feature, name_field_candidates, index)
        try:
            geometry = shape(_to_2d_geojson_geometry(feature["geometry"]))
            geometry = reproject_if_needed(geometry, detected_wkid, fallback_source_crs)
            geometry = validate_and_repair(geometry)
        except (InvalidGeometryError, KeyError, ValueError, TypeError) as exc:
            result.rejected_count += 1
            if len(result.rejection_samples) < 20:
                result.rejection_samples.append(f"feature[{index}] ({area_name}): {exc}")
            logger.warning(
                "rejected invalid catchment feature",
                extra={"feature_index": index, "area_name": area_name, "reason": str(exc)},
            )
            continue

        min_lon, min_lat, max_lon, max_lat = compute_bbox(geometry)
        simplified = simplify_geometry(geometry, tolerance=tolerance)

        result.areas.append(
            CatchmentArea(
                source_id=source_id,
                area_name=area_name,
                area_type=area_type,
                academic_year=academic_year,
                geometry_geojson=geometry_to_geojson_str(geometry),
                simplified_geometry_geojson=geometry_to_geojson_str(simplified),
                minimum_latitude=min_lat,
                maximum_latitude=max_lat,
                minimum_longitude=min_lon,
                maximum_longitude=max_lon,
                geometry_checksum=compute_geometry_checksum(geometry),
                valid_from=valid_from_iso,
            )
        )

    return result


def _extract_name(feature: dict[str, Any], candidates: list[str], index: int) -> str:
    properties = feature.get("properties", {}) or {}
    for field_name in candidates:
        value = properties.get(field_name)
        if value:
            return str(value)
    return f"Unnamed catchment area {index}"
