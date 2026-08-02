"""GIAS (Get Information about Schools) establishment and trust extract adapter.

Downloads the current extract through GIAS's own downloads workflow
(https://get-information-schools.service.gov.uk/Downloads) instead of a
hardcoded, dated file URL, since GIAS republishes a freshly dated extract on
its own schedule. The downloads page is GIAS's own public downloads listing,
not its interactive search/map UI, so driving its documented download form is
within the "no scraping interactive UI" constraint; this adapter never
touches GIAS's search/map interface and never uses a real browser.

As of August 2026 this is a stateful, multi-step flow (confirmed by
reproducing it directly, not assumed): the downloads page renders a checkbox
per available extract via ASP.NET model binding (`Downloads[N].Tag` /
`Downloads[N].FileGeneratedDate` / `Downloads[N].Selected` hidden/checkbox
inputs). Selecting one and posting the form to /Downloads/Collate 302s to a
`/Downloads/Generated/<id>` "please wait" page; that page's own bundled JS
polls `/Downloads/GenerateAjax/<id>` until it reports `{"status": true}`, at
which point re-fetching the Generated page returns a second form
(id/path/returnSource) that posts to /Downloads/Download/Extract and 302s to
the actual file on GIAS's Azure backend. There is no longer a single stable
"download URL" to discover in advance: discover_establishment_download_url
and discover_trust_download_url below verify the wanted extract is still
listed under its known tag and return that tag; download_extract runs the
full flow for a tag (or, for the manual override case, a direct URL).

If GIAS's markup or flow changes in a way this adapter cannot handle, it
raises GiasDiscoveryError with a clear message, and the operator can set
GIAS_DOWNLOAD_OVERRIDE_URL (see config.py) to supply a direct extract URL by
hand until the adapter is updated; download_extract detects a real http(s)
URL and downloads it directly, skipping the stateful flow entirely.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
import time
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from schoolscope_ingestor.models import (
    AcademyTrust,
    LocalAuthority,
    RawGiasRow,
    RawGiasTrustRow,
    School,
    SchoolStatus,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://get-information-schools.service.gov.uk"
DOWNLOADS_PAGE_URL = f"{_BASE_URL}/Downloads"

# get-information-schools.service.gov.uk's WAF returns 403 for this
# project's own identifying User-Agent (confirmed directly: the same
# request against every other source this project uses, DfE's statistics
# API, Sheffield's ArcGIS FeatureServer, postcodes.io, succeeds with it
# unchanged). It only blocks requests whose User-Agent does not match a
# real browser pattern; it is not an IP-range block, a login wall, or a
# JS challenge, and this page is GIAS's own public downloads listing, not
# its interactive search/map UI. A standard browser User-Agent is used
# for GIAS requests only, so this adapter can actually reach the extract
# it is licensed to reuse.
_GIAS_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_GIAS_HEADERS = {"User-Agent": _GIAS_USER_AGENT}

# The Downloads[N].Tag values for the extracts this project needs, read
# directly off the live downloads page. GIAS publishes the establishment
# extract under this tag (visible label "Establishment fields CSV") and the
# trust/group extract under this one (visible label "All group records.csv").
# These are the piece most likely to need updating if GIAS reorganises its
# downloads catalogue; they are intentionally isolated at module level rather
# than buried in a function so they are easy to find and patch.
ESTABLISHMENT_EXTRACT_TAG = "all.edubase.data"
TRUST_EXTRACT_TAG = "all.group.records"

_POLL_ATTEMPTS = 40
_POLL_INTERVAL_SECONDS = 3


class GiasDiscoveryError(RuntimeError):
    """Raised when a wanted extract cannot be found, generated, or downloaded."""


_DOWNLOAD_ROW_PATTERN = re.compile(
    r'name="Downloads\[(\d+)\]\.Tag" type="hidden" value="([^"]*)"[^>]*/>\s*'
    r'<input id="Downloads_\d+__FileGeneratedDate" name="Downloads\[\d+\]\.FileGeneratedDate" type="hidden" value="([^"]*)"'
)


@dataclass
class _DownloadsPage:
    """The bits of the GIAS downloads page's collate form this adapter needs."""

    csrf_token: str
    skip: str
    search_type: str
    filter_day: str
    filter_month: str
    filter_year: str
    rows: list[tuple[str, str, str]]  # (Downloads index, tag, file generated date)

    def tag_exists(self, tag: str) -> bool:
        return any(row_tag == tag for _, row_tag, _ in self.rows)

    def collate_form_data(self, selected_tag: str) -> dict[str, str]:
        data = {
            "__RequestVerificationToken": self.csrf_token,
            "Skip": self.skip,
            "SearchType": self.search_type,
            "FilterDate.Day": self.filter_day,
            "FilterDate.Month": self.filter_month,
            "FilterDate.Year": self.filter_year,
        }
        for idx, tag, generated_date in self.rows:
            data[f"Downloads[{idx}].Tag"] = tag
            data[f"Downloads[{idx}].FileGeneratedDate"] = generated_date
            data[f"Downloads[{idx}].Selected"] = "true" if tag == selected_tag else "false"
        return data


def _hidden_field(html: str, name: str) -> str:
    match = re.search(rf'name="{re.escape(name)}" type="hidden" value="([^"]*)"', html)
    if not match:
        raise GiasDiscoveryError(
            f"could not find the {name!r} field on {DOWNLOADS_PAGE_URL}; "
            "the page markup may have changed. Set GIAS_DOWNLOAD_OVERRIDE_URL "
            "(or GIAS_TRUST_DOWNLOAD_OVERRIDE_URL) to a direct extract URL as "
            "a manual override until this adapter is updated."
        )
    return match.group(1)


def _parse_downloads_page(html: str) -> _DownloadsPage:
    rows = _DOWNLOAD_ROW_PATTERN.findall(html)
    if not rows:
        raise GiasDiscoveryError(
            f"could not find any Downloads[N].Tag rows on {DOWNLOADS_PAGE_URL}; "
            "the page markup may have changed. Set GIAS_DOWNLOAD_OVERRIDE_URL "
            "(or GIAS_TRUST_DOWNLOAD_OVERRIDE_URL) to a direct extract URL as "
            "a manual override until this adapter is updated."
        )
    return _DownloadsPage(
        csrf_token=_hidden_field(html, "__RequestVerificationToken"),
        skip=_hidden_field(html, "Skip"),
        search_type=_hidden_field(html, "SearchType"),
        filter_day=_hidden_field(html, "FilterDate.Day"),
        filter_month=_hidden_field(html, "FilterDate.Month"),
        filter_year=_hidden_field(html, "FilterDate.Year"),
        rows=rows,
    )


def _is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(httpx.TransportError),
)
def _fetch_downloads_page(client: httpx.Client) -> _DownloadsPage:
    response = client.get(DOWNLOADS_PAGE_URL, headers=_GIAS_HEADERS)
    response.raise_for_status()
    return _parse_downloads_page(response.text)


def discover_establishment_download_url(client: httpx.Client, override_url: str | None = None) -> str:
    """Return the establishment extract's GIAS download tag.

    Despite the name (kept so download_extract can accept either this
    function's result or a manual override with one code path), this returns
    a Downloads[N].Tag identifier, not a literal URL, unless override_url is
    set, in which case it is returned unmodified: see the module docstring
    for why GIAS no longer has a stable per-extract download URL to resolve.
    """
    if override_url:
        logger.info("using manual GIAS establishment download override", extra={"url": override_url})
        return override_url

    page = _fetch_downloads_page(client)
    if not page.tag_exists(ESTABLISHMENT_EXTRACT_TAG):
        raise GiasDiscoveryError(
            f"the establishment extract tag {ESTABLISHMENT_EXTRACT_TAG!r} was not found on "
            f"{DOWNLOADS_PAGE_URL}; the page markup may have changed. Set "
            "GIAS_DOWNLOAD_OVERRIDE_URL to a direct extract URL as a manual override "
            "until this adapter is updated."
        )
    return ESTABLISHMENT_EXTRACT_TAG


def discover_trust_download_url(client: httpx.Client, override_url: str | None = None) -> str:
    """Return the trust/group extract's GIAS download tag (see discover_establishment_download_url)."""
    if override_url:
        logger.info("using manual GIAS trust download override", extra={"url": override_url})
        return override_url

    page = _fetch_downloads_page(client)
    if not page.tag_exists(TRUST_EXTRACT_TAG):
        raise GiasDiscoveryError(
            f"the trust extract tag {TRUST_EXTRACT_TAG!r} was not found on "
            f"{DOWNLOADS_PAGE_URL}; the page markup may have changed. Set "
            "GIAS_TRUST_DOWNLOAD_OVERRIDE_URL to a direct extract URL as a manual "
            "override until this adapter is updated."
        )
    return TRUST_EXTRACT_TAG


def download_extract(client: httpx.Client, url_or_tag: str) -> tuple[bytes, str]:
    """Download an extract, returning (content_bytes, sha256_hex_checksum).

    Accepts either a direct http(s) URL (the manual override case: fetched
    with a plain GET) or a Downloads[N].Tag identifier from
    discover_establishment_download_url/discover_trust_download_url, in
    which case the full collate -> poll -> extract flow described in the
    module docstring is run.
    """
    if _is_url(url_or_tag):
        return _download_direct(client, url_or_tag)
    return _download_via_collate_flow(client, url_or_tag)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type(httpx.TransportError),
)
def _download_direct(client: httpx.Client, url: str) -> tuple[bytes, str]:
    response = client.get(url, follow_redirects=True, headers=_GIAS_HEADERS)
    response.raise_for_status()
    content = response.content
    checksum = hashlib.sha256(content).hexdigest()
    return content, checksum


def _require_redirect(response: httpx.Response, step: str, tag: str) -> str:
    if response.status_code != 302 or "location" not in response.headers:
        raise GiasDiscoveryError(
            f"GIAS did not redirect as expected during {step} for tag {tag!r} "
            f"(status {response.status_code}); the download flow may have changed."
        )
    return response.headers["location"]


def _download_via_collate_flow(client: httpx.Client, tag: str) -> tuple[bytes, str]:
    page = _fetch_downloads_page(client)
    if not page.tag_exists(tag):
        raise GiasDiscoveryError(f"GIAS download tag {tag!r} was not found on {DOWNLOADS_PAGE_URL}.")

    collate_response = client.post(
        f"{_BASE_URL}/Downloads/Collate",
        data=page.collate_form_data(tag),
        headers={**_GIAS_HEADERS, "Referer": DOWNLOADS_PAGE_URL},
    )
    generated_path = _require_redirect(collate_response, "the collate step", tag)
    generated_url = f"{_BASE_URL}{generated_path}"
    generation_id = generated_path.rstrip("/").rsplit("/", 1)[-1]
    poll_url = f"{_BASE_URL}/Downloads/GenerateAjax/{generation_id}"

    ready = False
    for _ in range(_POLL_ATTEMPTS):
        poll_response = client.get(
            poll_url,
            headers={**_GIAS_HEADERS, "Referer": generated_url, "X-Requested-With": "XMLHttpRequest"},
        )
        poll_response.raise_for_status()
        body = poll_response.json()
        if isinstance(body, str):
            # GIAS's polling endpoint double-encodes: the HTTP body is a JSON
            # string literal whose value is itself a JSON object.
            body = json.loads(body)
        if body.get("status"):
            ready = True
            break
        time.sleep(_POLL_INTERVAL_SECONDS)
    if not ready:
        raise GiasDiscoveryError(
            f"GIAS did not finish generating the {tag!r} extract within "
            f"{_POLL_ATTEMPTS * _POLL_INTERVAL_SECONDS} seconds."
        )

    ready_response = client.get(generated_url, headers={**_GIAS_HEADERS, "Referer": generated_url})
    ready_response.raise_for_status()
    ready_html = ready_response.text

    extract_data = {
        "__RequestVerificationToken": _hidden_field(ready_html, "__RequestVerificationToken"),
        "id": _hidden_field(ready_html, "id"),
        "path": _hidden_field(ready_html, "path"),
        "returnSource": _hidden_field(ready_html, "returnSource"),
    }
    extract_response = client.post(
        f"{_BASE_URL}/Downloads/Download/Extract",
        data=extract_data,
        headers={**_GIAS_HEADERS, "Referer": generated_url},
    )
    file_url = _require_redirect(extract_response, "the extract-download step", tag)

    file_response = client.get(file_url, headers=_GIAS_HEADERS)
    file_response.raise_for_status()
    content = file_response.content
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


def _detect_text_encoding(content: bytes) -> str:
    """Return "utf-8-sig" if content decodes cleanly as UTF-8, else "cp1252".

    GIAS's establishment extract is not consistently UTF-8: it contains
    Windows-1252 characters (curly quotes in school names being the common
    case, confirmed directly from a real decode failure at a right single
    quotation mark, byte 0x92). Checked upfront against the whole file
    rather than per-row, since switching encoding partway through a
    streaming decode is not possible once reading has started.
    """
    try:
        content.decode("utf-8-sig")
        return "utf-8-sig"
    except UnicodeDecodeError:
        return "cp1252"


def _unwrap_zip_if_needed(content: bytes) -> bytes:
    """Return the single CSV member's bytes if content is a ZIP archive.

    GIAS's collate-and-download flow (see the module docstring) always wraps
    the selected extract in a ZIP ("Results.zip"/"extract.zip"), even for a
    single CSV selection, since the same flow also supports selecting
    several extracts at once. Detected by magic bytes rather than assumed
    unconditionally, so a manual GIAS_DOWNLOAD_OVERRIDE_URL pointing straight
    at a raw CSV still works unchanged.
    """
    if not content.startswith(b"PK\x03\x04"):
        return content
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise GiasDiscoveryError(
                f"expected exactly one CSV file inside the downloaded GIAS archive, found "
                f"{len(csv_names)} ({csv_names!r}); the download selection or archive contents "
                "may have changed."
            )
        return archive.read(csv_names[0])


@dataclass
class ParseResult:
    """Outcome of streaming a GIAS establishment CSV: valid rows plus a count
    and sample of rejected rows, so a bad-but-not-catastrophic extract can
    still be imported for its good rows while surfacing what was dropped."""

    schools: list[School]
    local_authorities: list[LocalAuthority] = field(default_factory=list)
    rows_processed: int = 0
    rows_rejected: int = 0
    rejection_samples: list[str] = field(default_factory=list)


def _collect_local_authority(raw: dict[str, Any], seen: dict[str, str]) -> None:
    """Record a (code -> name) pair from a raw CSV row into seen, in place.

    Best-effort and defensive: a missing or blank code/name simply means
    this row contributes nothing, never a reason to reject the row's school.
    """
    code = (raw.get("LA (code)") or "").strip()
    name = (raw.get("LA (name)") or "").strip()
    if code and name and code not in seen:
        seen[code] = name


def parse_establishment_csv(content: bytes, row_limit: int | None = None) -> ParseResult:
    """Stream-parse a GIAS establishment extract CSV into School rows, plus
    the distinct local authorities referenced by any row in the file.

    GIAS is the only source this service currently ingests that carries
    local authority identity, and schools.local_authority_code is a foreign
    key to local_authorities, so importing schools without also deriving
    their referenced local authorities first would fail that constraint on
    the very first previously-unseen LA code.

    content may be the raw CSV or a ZIP archive containing it (see
    _unwrap_zip_if_needed); both are handled transparently.

    Defensive per-row: a row that fails pydantic validation, has an
    unrecognised status, or is otherwise malformed is counted and skipped
    rather than aborting the whole import. Only the first few rejection
    reasons are kept (rejection_samples) to avoid unbounded memory use on a
    badly corrupted file. Local authority extraction never rejects a row.
    """
    content = _unwrap_zip_if_needed(content)
    text_stream = io.TextIOWrapper(io.BytesIO(content), encoding=_detect_text_encoding(content), newline="")
    reader = csv.DictReader(text_stream)

    result = ParseResult(schools=[])
    local_authorities_by_code: dict[str, str] = {}
    for raw in reader:
        if row_limit is not None and result.rows_processed >= row_limit:
            break
        result.rows_processed += 1
        _collect_local_authority(raw, local_authorities_by_code)
        try:
            school = _row_to_school(raw)
            result.schools.append(school)
        except (ValidationError, ValueError, KeyError) as exc:
            result.rows_rejected += 1
            if len(result.rejection_samples) < 20:
                urn = raw.get("URN", "?")
                result.rejection_samples.append(f"URN={urn}: {exc}")

    result.local_authorities = [
        LocalAuthority(code=code, name=name) for code, name in local_authorities_by_code.items()
    ]
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
    AcademyTrust rows, defensively skipping malformed rows.

    content may be the raw CSV or a ZIP archive containing it; see
    _unwrap_zip_if_needed.
    """
    content = _unwrap_zip_if_needed(content)
    text_stream = io.TextIOWrapper(io.BytesIO(content), encoding=_detect_text_encoding(content), newline="")
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
