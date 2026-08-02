"""Tests for the GIAS downloads-page parsing and collate/download helpers.

The sample HTML fragments below are a trimmed, hand-written approximation of
GIAS's real downloads page markup (verified directly against the live site
in August 2026), not scraped content, and contain no real data.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from schoolscope_ingestor.adapters.gias import (
    GiasDiscoveryError,
    _detect_text_encoding,
    _is_url,
    _parse_downloads_page,
    _unwrap_zip_if_needed,
)

SAMPLE_DOWNLOADS_HTML = """
<form action="/Downloads/Collate" method="post">
<input name="__RequestVerificationToken" type="hidden" value="token-abc" />
<input id="Skip" name="Skip" type="hidden" value="" />
<input id="SearchType" name="SearchType" type="hidden" value="Latest" />
<input id="FilterDate_Day" name="FilterDate.Day" type="hidden" value="2" />
<input id="FilterDate_Month" name="FilterDate.Month" type="hidden" value="8" />
<input id="FilterDate_Year" name="FilterDate.Year" type="hidden" value="2026" />
<input id="Downloads_0__Tag" name="Downloads[0].Tag" type="hidden" value="all.edubase.data" />
<input id="Downloads_0__FileGeneratedDate" name="Downloads[0].FileGeneratedDate" type="hidden" value="8/2/2026 12:00:00 AM" />
<input id="Downloads_9__Tag" name="Downloads[9].Tag" type="hidden" value="all.group.records" />
<input id="Downloads_9__FileGeneratedDate" name="Downloads[9].FileGeneratedDate" type="hidden" value="8/2/2026 12:00:00 AM" />
</form>
"""


def test_parse_downloads_page_extracts_form_fields() -> None:
    page = _parse_downloads_page(SAMPLE_DOWNLOADS_HTML)
    assert page.csrf_token == "token-abc"
    assert page.search_type == "Latest"
    assert page.filter_day == "2"
    assert len(page.rows) == 2


def test_parse_downloads_page_tag_exists() -> None:
    page = _parse_downloads_page(SAMPLE_DOWNLOADS_HTML)
    assert page.tag_exists("all.edubase.data")
    assert page.tag_exists("all.group.records")
    assert not page.tag_exists("some.other.tag")


def test_parse_downloads_page_raises_on_missing_rows() -> None:
    with pytest.raises(GiasDiscoveryError):
        _parse_downloads_page("<html><body>no download form here</body></html>")


def test_parse_downloads_page_raises_on_missing_csrf_field() -> None:
    html_without_token = SAMPLE_DOWNLOADS_HTML.replace(
        '<input name="__RequestVerificationToken" type="hidden" value="token-abc" />', ""
    )
    with pytest.raises(GiasDiscoveryError):
        _parse_downloads_page(html_without_token)


def test_collate_form_data_selects_only_the_requested_tag() -> None:
    page = _parse_downloads_page(SAMPLE_DOWNLOADS_HTML)
    data = page.collate_form_data("all.edubase.data")
    assert data["Downloads[0].Selected"] == "true"
    assert data["Downloads[9].Selected"] == "false"
    assert data["__RequestVerificationToken"] == "token-abc"


def test_is_url() -> None:
    assert _is_url("https://example.com/file.csv")
    assert _is_url("http://example.com/file.csv")
    assert not _is_url("all.edubase.data")


def test_unwrap_zip_if_needed_passes_through_plain_csv() -> None:
    raw = b"URN,EstablishmentName\r\n900001,Test School\r\n"
    assert _unwrap_zip_if_needed(raw) == raw


def test_unwrap_zip_if_needed_extracts_single_csv_member() -> None:
    csv_bytes = b"URN,EstablishmentName\r\n900001,Test School\r\n"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("extract.csv", csv_bytes)
    assert _unwrap_zip_if_needed(buffer.getvalue()) == csv_bytes


def test_unwrap_zip_if_needed_raises_on_multiple_csv_members() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("a.csv", b"a")
        archive.writestr("b.csv", b"b")
    with pytest.raises(GiasDiscoveryError):
        _unwrap_zip_if_needed(buffer.getvalue())


def test_unwrap_zip_if_needed_raises_on_no_csv_members() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", b"not a csv")
    with pytest.raises(GiasDiscoveryError):
        _unwrap_zip_if_needed(buffer.getvalue())


def test_detect_text_encoding_prefers_utf8() -> None:
    assert _detect_text_encoding(b"hello") == "utf-8-sig"


def test_detect_text_encoding_falls_back_to_cp1252() -> None:
    # 0x92 is a right single quotation mark in cp1252; not valid standalone UTF-8.
    content = b"St Mary" + b"\x92" + b"s School"
    assert _detect_text_encoding(content) == "cp1252"
