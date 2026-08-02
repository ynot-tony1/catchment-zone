"""Admission arrangement metadata adapter.

Machine-readable admissions criteria are rarely published in a structured
form; most admission authorities publish a PDF policy document. This adapter
therefore only ever stores metadata about admission arrangements (which
criteria a school's policy uses, links to the authority's own policy and
application pages) from a simple structured source (CSV or YAML) that a
maintainer has read and transcribed by hand. It never parses or interprets
PDF text itself, and it never generates or infers criteria from a policy
document; doing so would risk asserting something the source document does
not actually say.

Any free-text summary field is checked against a small banned-word list
(see AdmissionArrangement.summary_avoids_certainty_language in models.py) so
that a summary can never claim a result is guaranteed, eligible, or will be
accepted; those words describe a decision only the admission authority can
make.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field

import yaml
from pydantic import ValidationError

from catchment_zone_ingestor.models import AdmissionArrangement

logger = logging.getLogger(__name__)


class AdmissionSourceFormatError(RuntimeError):
    """Raised when a structured admissions source file cannot be parsed at all."""


@dataclass
class AdmissionParseResult:
    arrangements: list[AdmissionArrangement]
    rows_processed: int = 0
    rows_rejected: int = 0
    rejection_samples: list[str] = field(default_factory=list)


_BOOLEAN_TRUE_VALUES = {"true", "1", "yes", "y"}


def _to_bool(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in _BOOLEAN_TRUE_VALUES


def parse_admissions_csv(content: str) -> AdmissionParseResult:
    """Parse a hand-maintained CSV of admission arrangement metadata.

    Expected columns: school_urn, admission_authority_name, academic_year,
    policy_url, application_url, published_admission_number, uses_catchment,
    uses_distance, uses_nodal_point, uses_feeder_school, uses_faith_criteria,
    uses_selection, summary.
    """
    reader = csv.DictReader(io.StringIO(content))
    result = AdmissionParseResult(arrangements=[])

    for raw in reader:
        result.rows_processed += 1
        try:
            arrangement = _row_to_arrangement(raw)
            result.arrangements.append(arrangement)
        except (ValidationError, ValueError) as exc:
            result.rows_rejected += 1
            if len(result.rejection_samples) < 20:
                urn = raw.get("school_urn", "?")
                result.rejection_samples.append(f"school_urn={urn}: {exc}")

    return result


def parse_admissions_yaml(content: str) -> AdmissionParseResult:
    """Parse a hand-maintained YAML list of admission arrangement metadata,
    for maintainers who prefer YAML's support for a longer freeform summary
    field over CSV's single-line cells."""
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise AdmissionSourceFormatError(f"invalid YAML admissions source: {exc}") from exc

    entries = data.get("admission_arrangements", []) if isinstance(data, dict) else data
    if not isinstance(entries, list):
        raise AdmissionSourceFormatError("admissions YAML must be a list, or a mapping with an 'admission_arrangements' list")

    result = AdmissionParseResult(arrangements=[])
    for raw in entries:
        result.rows_processed += 1
        try:
            arrangement = _row_to_arrangement(raw)
            result.arrangements.append(arrangement)
        except (ValidationError, ValueError) as exc:
            result.rows_rejected += 1
            if len(result.rejection_samples) < 20:
                urn = raw.get("school_urn", "?") if isinstance(raw, dict) else "?"
                result.rejection_samples.append(f"school_urn={urn}: {exc}")

    return result


def _row_to_arrangement(raw: dict[str, object]) -> AdmissionArrangement:
    summary = raw.get("summary")
    if isinstance(summary, str) and not AdmissionArrangement.summary_avoids_certainty_language(summary):
        raise ValueError(
            "summary text uses certainty language (e.g. 'guaranteed', 'eligible') "
            "that this service must not assert; rephrase the source data"
        )

    published_admission_number = raw.get("published_admission_number")
    return AdmissionArrangement(
        school_urn=str(raw["school_urn"]).strip(),
        admission_authority_name=str(raw["admission_authority_name"]).strip(),
        academic_year=str(raw["academic_year"]).strip(),
        policy_url=_none_if_blank(raw.get("policy_url")),
        application_url=_none_if_blank(raw.get("application_url")),
        published_admission_number=(
            int(str(published_admission_number))
            if published_admission_number not in (None, "")
            else None
        ),
        uses_catchment=_as_bool(raw.get("uses_catchment")),
        uses_distance=_as_bool(raw.get("uses_distance")),
        uses_nodal_point=_as_bool(raw.get("uses_nodal_point")),
        uses_feeder_school=_as_bool(raw.get("uses_feeder_school")),
        uses_faith_criteria=_as_bool(raw.get("uses_faith_criteria")),
        uses_selection=_as_bool(raw.get("uses_selection")),
        summary=_none_if_blank(summary),
    )


def _none_if_blank(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return _to_bool(str(value))
