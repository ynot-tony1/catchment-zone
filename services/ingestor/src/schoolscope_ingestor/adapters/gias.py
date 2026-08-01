"""GIAS (Get Information about Schools) establishment and trust extract adapter.

Discovers the current download link from the public GIAS downloads page
(https://get-information-schools.service.gov.uk/Downloads) instead of
hardcoding a dated URL, since GIAS publishes a freshly dated extract file on
a regular cycle and a hardcoded link goes stale. The downloads page is a
plain static HTML page listing extract links, not an interactive map or
search UI, so parsing its markup for documented download links is within the
"no scraping interactive UI" constraint; this adapter never drives a browser
and never touches GIAS's search/map interface.

If the page's markup changes in a way this parser cannot handle, discovery
raises GiasDiscoveryError with a clear message, and the operator can set
GIAS_DOWNLOAD_OVERRIDE_URL (see config.py) to supply the current extract URL
by hand until the discovery pattern below is updated. This override path is
the documented manual fallback referenced in the module docstring above.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

import httpx
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from schoolscope_ingestor.models import (
    AcademyTrust,
    RawGiasRow,
    RawGiasTrustRow,
    School,
    SchoolStatus,
)

logger = logging.getLogger(__name__)

DOWNLOADS_PAGE_URL = "https://get-information-schools.service.gov.uk/Downloads"

# GIAS has published the all-establishments extract under link text matching
# this pattern for years (e.g. "Establishment fields CSV", "All establishment
# data (CSV)"). Matched case-insensitively against each anchor's visible text.
# This is the piece most likely to need updating if the site is redesigned;
# it is intentionally isolated at module level rather than buried in a
# function so it's easy to find and patch.
ESTABLISHMENT_LINK_TEXT_PATTERN = re.compile(r"establishment.*\bcsv\b|all\s+establishment", re.IGNORECASE)
TRUST_LINK_TEXT_PATTERN = re.compile(r"group.*\bcsv\b|trust.*\bcsv\b", re.IGNORECASE)


class GiasDiscoveryError(RuntimeError):
    """Raised when the current extract download link cannot be discovered."""


@dataclass
class _Anchor:
    href: str
    text_parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(self.text_parts).strip()


class _AnchorExtractor(HTMLParser):
    """Minimal stdlib HTML parser that collects <a href=...>text</a> pairs.

    Deliberately avoids adding a third-party HTML parsing dependency for a
    single, narrow use: reading anchor tags off one static page.
    """

    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[_Anchor] = []
        self._current: _Anchor | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = next((v for k, v in attrs if k.lower() == "href" and v), None)
        if href:
            self._current = _Anchor(href=href)

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._current.text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current is not None:
            self.anchors.append(self._current)
            self._current = None


def _resolve_url(href: str, base: str = DOWNLOADS_PAGE_URL) -> str:
    return str(httpx.URL(base).join(href))


def _find_link(html: str, pattern: re.Pattern[str], kind: str) -> str:
    parser = _AnchorExtractor()
    parser.feed(html)
    candidates = [a for a in parser.anchors if pattern.search(a.text) or pattern.search(a.href)]
    if not candidates:
        raise GiasDiscoveryError(
            f"could not find a {kind} download link on {DOWNLOADS_PAGE_URL}; "
            "the page markup may have changed. Set GIAS_DOWNLOAD_OVERRIDE_URL "
            "(or GIAS_TRUST_DOWNLOAD_OVERRIDE_URL for the trust extract) to "
            "the correct URL as a manual override until this parser is updated."
        )
    return _resolve_url(candidates[0].href)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(httpx.TransportError),
)
def discover_establishment_download_url(client: httpx.Client, override_url: str | None = None) -> str:
    """Return the current GIAS establishment extract CSV URL.

    Uses override_url unmodified if provided (the documented manual fallback).
    Otherwise fetches the downloads page and looks for the establishment
    extract link.
    """
    if override_url:
        logger.info("using manual GIAS establishment download override", extra={"url": override_url})
        return override_url

    response = client.get(DOWNLOADS_PAGE_URL)
    response.raise_for_status()
    return _find_link(response.text, ESTABLISHMENT_LINK_TEXT_PATTERN, "establishment extract")


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(httpx.TransportError),
)
def discover_trust_download_url(client: httpx.Client, override_url: str | None = None) -> str:
    """Return the current GIAS academy trust / group extract CSV URL."""
    if override_url:
        logger.info("using manual GIAS trust download override", extra={"url": override_url})
        return override_url

    response = client.get(DOWNLOADS_PAGE_URL)
    response.raise_for_status()
    return _find_link(response.text, TRUST_LINK_TEXT_PATTERN, "trust")


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type(httpx.TransportError),
)
def download_extract(client: httpx.Client, url: str) -> tuple[bytes, str]:
    """Download an extract file, returning (content_bytes, sha256_hex_checksum)."""
    response = client.get(url, follow_redirects=True)
    response.raise_for_status()
    content = response.content
    checksum = hashlib.sha256(content).hexdigest()
    return content, checksum


_STATUS_MAP = {
    "open": SchoolStatus.OPEN,
    "open, but proposed to close": SchoolStatus.OPEN_BUT_PROPOSED_TO_CLOSE,
    "proposed to open": SchoolStatus.PROPOSED_TO_OPEN,
    "closed": SchoolStatus.CLOSED,
}


def _map_status(raw: str) -> SchoolStatus:
    key = raw.strip().lower()
    if key not in _STATUS_MAP:
        raise ValueError(f"unrecognised establishment status: {raw!r}")
    return _STATUS_MAP[key]


def _parse_optional_int(raw: str | None) -> int | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _parse_optional_date(raw: str | None) -> str | None:
    """GIAS dates are typically DD-MM-YYYY. Returned as an ISO string, or None
    if blank or unparseable (defensive: a bad date should not fail the row)."""
    if raw is None or raw.strip() == "":
        return None
    from datetime import datetime as _dt

    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return _dt.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _normalise_name(name: str) -> str:
    return " ".join(name.strip().split()).lower()


@dataclass
class ParseResult:
    """Outcome of streaming a GIAS establishment CSV: valid rows plus a count
    and sample of rejected rows, so a bad-but-not-catastrophic extract can
    still be imported for its good rows while surfacing what was dropped."""

    schools: list[School]
    rows_processed: int = 0
    rows_rejected: int = 0
    rejection_samples: list[str] = field(default_factory=list)


def parse_establishment_csv(content: bytes, row_limit: int | None = None) -> ParseResult:
    """Stream-parse a GIAS establishment extract CSV into School rows.

    Defensive per-row: a row that fails pydantic validation, has an
    unrecognised status, or is otherwise malformed is counted and skipped
    rather than aborting the whole import. Only the first few rejection
    reasons are kept (rejection_samples) to avoid unbounded memory use on a
    badly corrupted file.
    """
    text_stream = io.TextIOWrapper(io.BytesIO(content), encoding="utf-8-sig", newline="")
    reader = csv.DictReader(text_stream)

    result = ParseResult(schools=[])
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
                urn = raw.get("URN", "?")
                result.rejection_samples.append(f"URN={urn}: {exc}")
    return result


def _validate_urn(raw_urn: str) -> str:
    urn = raw_urn.strip()
    if not urn.isdigit():
        raise ValueError(f"URN must be numeric, got {raw_urn!r}")
    return urn


def _validate_name(raw_name: str) -> str:
    name = raw_name.strip()
    if not name:
        raise ValueError("establishment name is blank")
    return name


def _row_to_school(raw: dict[str, Any]) -> School:
    parsed = RawGiasRow.model_validate(raw)
    urn = _validate_urn(parsed.urn)
    name = _validate_name(parsed.establishment_name)

    return School(
        urn=urn,
        school_name=name,
        normalised_name=_normalise_name(name),
        status=_map_status(parsed.establishment_status_name),
        establishment_type_code="",  # GIAS extracts carry the code in a separate column not modelled here; left blank rather than guessed.
        establishment_type_name=parsed.type_of_establishment_name,
        phase_code="",
        phase_name=parsed.phase_of_education_name,
        minimum_age=_parse_optional_int(parsed.statutory_low_age),
        maximum_age=_parse_optional_int(parsed.statutory_high_age),
        gender=parsed.gender_name or None,
        religious_character=parsed.religious_character_name or None,
        street=parsed.street or None,
        locality=parsed.locality or None,
        town=parsed.town or None,
        county=parsed.county_name or None,
        postcode=(parsed.postcode or None),
        postcode_prefix=_postcode_prefix(parsed.postcode),
        local_authority_code=parsed.la_code or None,
        opening_date=_parse_optional_date(parsed.open_date),
        closing_date=_parse_optional_date(parsed.close_date),
        capacity=_parse_optional_int(parsed.school_capacity),
        number_of_pupils=_parse_optional_int(parsed.number_of_pupils),
        website=parsed.school_website or None,
        telephone=parsed.telephone_num or None,
        trust_id=parsed.trusts_code or None,
    )


def _postcode_prefix(postcode: str | None) -> str | None:
    if not postcode:
        return None
    stripped = postcode.strip().upper()
    if not stripped:
        return None
    # The outward code is everything before the final 3-character inward code.
    if len(stripped) > 3:
        return stripped[:-3].strip()
    return stripped


def iter_school_batches(schools: list[School], batch_size: int) -> Iterator[list[School]]:
    """Yield schools in fixed-size batches for batched database upserts."""
    for start in range(0, len(schools), batch_size):
        yield schools[start : start + batch_size]


@dataclass
class TrustParseResult:
    """Outcome of streaming a GIAS trust/group extract CSV, mirroring
    ParseResult's tolerant per-row behaviour above."""

    trusts: list[AcademyTrust]
    rows_processed: int = 0
    rows_rejected: int = 0
    rejection_samples: list[str] = field(default_factory=list)


def parse_trust_csv(content: bytes, row_limit: int | None = None) -> TrustParseResult:
    """Stream-parse a GIAS academy trust / group extract CSV into
    AcademyTrust rows, defensively skipping malformed rows."""
    text_stream = io.TextIOWrapper(io.BytesIO(content), encoding="utf-8-sig", newline="")
    reader = csv.DictReader(text_stream)

    result = TrustParseResult(trusts=[])
    for raw in reader:
        if row_limit is not None and result.rows_processed >= row_limit:
            break
        result.rows_processed += 1
        try:
            result.trusts.append(_row_to_trust(raw))
        except (ValidationError, ValueError, KeyError) as exc:
            result.rows_rejected += 1
            if len(result.rejection_samples) < 20:
                uid = raw.get("Group UID", "?")
                result.rejection_samples.append(f"Group UID={uid}: {exc}")
    return result


def _row_to_trust(raw: dict[str, Any]) -> AcademyTrust:
    parsed = RawGiasTrustRow.model_validate(raw)
    return AcademyTrust(
        trust_id=parsed.trust_uid.strip(),
        trust_name=parsed.trust_name,
        trust_type=parsed.trust_type or None,
        companies_house_number=parsed.companies_house_number or None,
        address=parsed.address_1 or None,
        postcode=parsed.postcode or None,
    )
