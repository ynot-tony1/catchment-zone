"""Pydantic models mirroring the Prisma schema rows this service writes.

These deliberately shadow packages/database/prisma/schema.prisma (read-only
reference for this service) field-for-field for the tables the ingestor
populates: School, AcademyTrust, SchoolMetric, CatchmentSource, CatchmentArea,
SchoolCatchmentArea, AdmissionArrangement and IngestionRun. Field names use
snake_case here (matching the database column names) rather than the Prisma
client's camelCase, since this service talks to the database directly over
psycopg rather than through the generated Prisma client.

This service never defines a model for user-submitted postcodes or addresses;
that data does not exist on this side of the system.
"""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SchoolStatus(str, enum.Enum):
    OPEN = "OPEN"
    OPEN_BUT_PROPOSED_TO_CLOSE = "OPEN_BUT_PROPOSED_TO_CLOSE"
    PROPOSED_TO_OPEN = "PROPOSED_TO_OPEN"
    CLOSED = "CLOSED"


class RelationshipType(str, enum.Enum):
    PREDECESSOR = "PREDECESSOR"
    SUCCESSOR = "SUCCESSOR"
    TRUST_TRANSFER = "TRUST_TRANSFER"
    FEDERATION = "FEDERATION"
    LINKED_ESTABLISHMENT = "LINKED_ESTABLISHMENT"


class CatchmentCoverageStatus(str, enum.Enum):
    NOT_AVAILABLE = "NOT_AVAILABLE"
    PILOT = "PILOT"
    PARTIAL = "PARTIAL"
    FULL = "FULL"


class CatchmentSourceStatus(str, enum.Enum):
    PENDING = "PENDING"
    VALID = "VALID"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class IngestionStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED_UNCHANGED = "SKIPPED_UNCHANGED"


class _Row(BaseModel):
    """Base class for rows this service writes. Forbids unexpected fields
    so a source schema drift is caught as a validation error, not silently
    dropped data."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class School(_Row):
    urn: str
    school_name: str
    normalised_name: str
    status: SchoolStatus
    establishment_type_code: str
    establishment_type_name: str
    phase_code: str
    phase_name: str
    minimum_age: int | None = None
    maximum_age: int | None = None
    gender: str | None = None
    religious_character: str | None = None
    admissions_policy_type: str | None = None

    street: str | None = None
    locality: str | None = None
    town: str | None = None
    county: str | None = None
    postcode: str | None = None
    postcode_prefix: str | None = None

    latitude: float | None = None
    longitude: float | None = None

    local_authority_code: str | None = None
    region_code: str | None = None
    urban_rural_code: str | None = None

    opening_date: datetime | None = None
    closing_date: datetime | None = None
    capacity: int | None = None
    number_of_pupils: int | None = None

    website: str | None = None
    telephone: str | None = None

    trust_id: str | None = None
    federation_id: str | None = None

    has_sen_provision: bool = False

    source_updated_at: datetime | None = None
    source_extract_date: datetime | None = None


class AcademyTrust(_Row):
    trust_id: str
    trust_name: str
    trust_type: str | None = None
    companies_house_number: str | None = None
    address: str | None = None
    postcode: str | None = None
    open_school_count: int = 0
    source_updated_at: datetime | None = None


class SchoolRelationship(_Row):
    from_urn: str
    to_urn: str
    relationship_type: RelationshipType
    effective_date: datetime | None = None
    source_updated_at: datetime | None = None


class SchoolMetric(_Row):
    school_urn: str
    metric_code: str
    academic_year: str
    value_numeric: float | None = None
    value_text: str | None = None
    denominator: str | None = None
    suppressed: bool = False
    provisional: bool = False
    source_release: str | None = None
    source_published_at: datetime | None = None


class CatchmentSource(_Row):
    local_authority_code: str
    academic_year: str
    source_url: str
    download_url: str
    source_type: str
    format: str
    licence: str
    checksum: str | None = None
    retrieved_at: datetime | None = None
    verified_at: datetime | None = None
    status: CatchmentSourceStatus = CatchmentSourceStatus.PENDING
    error_summary: str | None = None


class CatchmentArea(_Row):
    source_id: str
    area_name: str
    area_type: str
    academic_year: str
    geometry_geojson: str
    simplified_geometry_geojson: str
    minimum_latitude: float
    maximum_latitude: float
    minimum_longitude: float
    maximum_longitude: float
    geometry_checksum: str
    valid_from: datetime
    valid_to: datetime | None = None


class SchoolCatchmentArea(_Row):
    school_urn: str
    catchment_area_id: str


class AdmissionArrangement(_Row):
    school_urn: str
    admission_authority_name: str
    academic_year: str
    policy_url: str | None = None
    application_url: str | None = None
    published_admission_number: int | None = None
    uses_catchment: bool = False
    uses_distance: bool = False
    uses_nodal_point: bool = False
    uses_feeder_school: bool = False
    uses_faith_criteria: bool = False
    uses_selection: bool = False
    summary: str | None = None
    source_verified_at: datetime | None = None

    @classmethod
    def summary_avoids_certainty_language(cls, summary: str) -> bool:
        """True if a free-text summary avoids implying a guaranteed outcome.

        A catchment or admissions summary must never claim a result guarantees
        admission. This is a defensive check, not a substitute for careful
        drafting of the summary text at the source.
        """
        banned = ("eligible", "guaranteed", "will be accepted", "guarantees admission")
        lowered = summary.lower()
        return not any(term in lowered for term in banned)


class IngestionRun(_Row):
    id: str | None = None
    source: str
    source_date: datetime | None = None
    status: IngestionStatus = IngestionStatus.RUNNING
    rows_processed: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_rejected: int = 0
    geometry_records: int = 0
    metrics_records: int = 0
    duration_seconds: float | None = None
    workflow_run_url: str | None = None
    git_sha: str | None = None
    error_summary: str | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None


class RawGiasRow(BaseModel):
    """Loosely-typed intermediate model for a single raw GIAS CSV row.

    GIAS extracts are wide (100+ columns) and column names vary in casing and
    punctuation between extract dates. This model captures only the columns
    the service maps to School fields; unmapped columns are ignored rather
    than rejected, since GIAS periodically adds new descriptive columns that
    this service does not need. Extra fields are therefore allowed here, in
    contrast to the strict _Row models above.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    urn: str = Field(alias="URN")
    establishment_name: str = Field(alias="EstablishmentName")
    establishment_status_name: str = Field(alias="EstablishmentStatus (name)")
    type_of_establishment_name: str = Field(alias="TypeOfEstablishment (name)")
    phase_of_education_name: str = Field(alias="PhaseOfEducation (name)")
    statutory_low_age: str | None = Field(default=None, alias="StatutoryLowAge")
    statutory_high_age: str | None = Field(default=None, alias="StatutoryHighAge")
    gender_name: str | None = Field(default=None, alias="Gender (name)")
    religious_character_name: str | None = Field(
        default=None, alias="ReligiousCharacter (name)"
    )
    street: str | None = Field(default=None, alias="Street")
    locality: str | None = Field(default=None, alias="Locality")
    town: str | None = Field(default=None, alias="Town")
    county_name: str | None = Field(default=None, alias="County (name)")
    postcode: str | None = Field(default=None, alias="Postcode")
    la_code: str | None = Field(default=None, alias="LA (code)")
    trust_school_flag_code: str | None = Field(default=None, alias="TrustSchoolFlag (code)")
    trusts_code: str | None = Field(default=None, alias="Trusts (code)")
    trusts_name: str | None = Field(default=None, alias="Trusts (name)")
    open_date: str | None = Field(default=None, alias="OpenDate")
    close_date: str | None = Field(default=None, alias="CloseDate")
    school_capacity: str | None = Field(default=None, alias="SchoolCapacity")
    number_of_pupils: str | None = Field(default=None, alias="NumberOfPupils")
    telephone_num: str | None = Field(default=None, alias="TelephoneNum")
    school_website: str | None = Field(default=None, alias="SchoolWebsite")


class RawGiasTrustRow(BaseModel):
    """Loosely-typed intermediate model for a single raw row of the GIAS
    academy trust / group extract. Column names again vary in casing between
    extract dates, hence the tolerant, ignore-unknown-fields config."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    trust_uid: str = Field(alias="Group UID")
    trust_name: str = Field(alias="Group Name")
    trust_type: str | None = Field(default=None, alias="Group Type")
    companies_house_number: str | None = Field(default=None, alias="Companies House Number")
    address_1: str | None = Field(default=None, alias="Group Contact Str1")
    postcode: str | None = Field(default=None, alias="Group Contact Postcode")
