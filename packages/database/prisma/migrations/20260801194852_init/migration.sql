-- CreateEnum
CREATE TYPE "SchoolStatus" AS ENUM ('OPEN', 'OPEN_BUT_PROPOSED_TO_CLOSE', 'PROPOSED_TO_OPEN', 'CLOSED');

-- CreateEnum
CREATE TYPE "RelationshipType" AS ENUM ('PREDECESSOR', 'SUCCESSOR', 'TRUST_TRANSFER', 'FEDERATION', 'LINKED_ESTABLISHMENT');

-- CreateEnum
CREATE TYPE "CatchmentCoverageStatus" AS ENUM ('NOT_AVAILABLE', 'PILOT', 'PARTIAL', 'FULL');

-- CreateEnum
CREATE TYPE "CatchmentSourceStatus" AS ENUM ('PENDING', 'VALID', 'FAILED', 'SUPERSEDED');

-- CreateEnum
CREATE TYPE "IngestionStatus" AS ENUM ('RUNNING', 'SUCCEEDED', 'FAILED', 'SKIPPED_UNCHANGED');

-- CreateTable
CREATE TABLE "schools" (
    "urn" STRING NOT NULL,
    "school_name" STRING NOT NULL,
    "normalised_name" STRING NOT NULL,
    "status" "SchoolStatus" NOT NULL,
    "establishment_type_code" STRING NOT NULL,
    "establishment_type_name" STRING NOT NULL,
    "phase_code" STRING NOT NULL,
    "phase_name" STRING NOT NULL,
    "minimum_age" INT4,
    "maximum_age" INT4,
    "gender" STRING,
    "religious_character" STRING,
    "admissions_policy_type" STRING,
    "street" STRING,
    "locality" STRING,
    "town" STRING,
    "county" STRING,
    "postcode" STRING,
    "postcode_prefix" STRING,
    "latitude" FLOAT8,
    "longitude" FLOAT8,
    "local_authority_code" STRING,
    "region_code" STRING,
    "urban_rural_code" STRING,
    "opening_date" TIMESTAMP(3),
    "closing_date" TIMESTAMP(3),
    "capacity" INT4,
    "number_of_pupils" INT4,
    "website" STRING,
    "telephone" STRING,
    "trust_id" STRING,
    "federation_id" STRING,
    "has_sen_provision" BOOL NOT NULL DEFAULT false,
    "source_updated_at" TIMESTAMP(3),
    "source_extract_date" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "schools_pkey" PRIMARY KEY ("urn")
);

-- CreateTable
CREATE TABLE "academy_trusts" (
    "trust_id" STRING NOT NULL,
    "trust_name" STRING NOT NULL,
    "trust_type" STRING,
    "companies_house_number" STRING,
    "address" STRING,
    "postcode" STRING,
    "open_school_count" INT4 NOT NULL DEFAULT 0,
    "source_updated_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "academy_trusts_pkey" PRIMARY KEY ("trust_id")
);

-- CreateTable
CREATE TABLE "school_relationships" (
    "id" STRING NOT NULL,
    "from_urn" STRING NOT NULL,
    "to_urn" STRING NOT NULL,
    "relationship_type" "RelationshipType" NOT NULL,
    "effective_date" TIMESTAMP(3),
    "source_updated_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "school_relationships_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "local_authorities" (
    "code" STRING NOT NULL,
    "name" STRING NOT NULL,
    "region_code" STRING,
    "admissions_website" STRING,
    "official_catchment_checker_url" STRING,
    "catchment_coverage_status" "CatchmentCoverageStatus" NOT NULL DEFAULT 'NOT_AVAILABLE',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "local_authorities_pkey" PRIMARY KEY ("code")
);

-- CreateTable
CREATE TABLE "school_metrics" (
    "id" STRING NOT NULL,
    "school_urn" STRING NOT NULL,
    "metric_code" STRING NOT NULL,
    "academic_year" STRING NOT NULL,
    "value_numeric" FLOAT8,
    "value_text" STRING,
    "denominator" STRING,
    "suppressed" BOOL NOT NULL DEFAULT false,
    "provisional" BOOL NOT NULL DEFAULT false,
    "source_release" STRING,
    "source_published_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "school_metrics_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "catchment_sources" (
    "id" STRING NOT NULL,
    "local_authority_code" STRING NOT NULL,
    "academic_year" STRING NOT NULL,
    "source_url" STRING NOT NULL,
    "download_url" STRING NOT NULL,
    "source_type" STRING NOT NULL,
    "format" STRING NOT NULL,
    "licence" STRING NOT NULL,
    "checksum" STRING,
    "retrieved_at" TIMESTAMP(3),
    "verified_at" TIMESTAMP(3),
    "status" "CatchmentSourceStatus" NOT NULL DEFAULT 'PENDING',
    "error_summary" STRING,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "catchment_sources_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "catchment_areas" (
    "id" STRING NOT NULL,
    "source_id" STRING NOT NULL,
    "area_name" STRING NOT NULL,
    "area_type" STRING NOT NULL,
    "academic_year" STRING NOT NULL,
    "geometry_geojson" STRING NOT NULL,
    "simplified_geometry_geojson" STRING NOT NULL,
    "minimum_latitude" FLOAT8 NOT NULL,
    "maximum_latitude" FLOAT8 NOT NULL,
    "minimum_longitude" FLOAT8 NOT NULL,
    "maximum_longitude" FLOAT8 NOT NULL,
    "geometry_checksum" STRING NOT NULL,
    "valid_from" TIMESTAMP(3) NOT NULL,
    "valid_to" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "catchment_areas_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "school_catchment_areas" (
    "id" STRING NOT NULL,
    "school_urn" STRING NOT NULL,
    "catchment_area_id" STRING NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "school_catchment_areas_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "admission_arrangements" (
    "id" STRING NOT NULL,
    "school_urn" STRING NOT NULL,
    "admission_authority_name" STRING NOT NULL,
    "academic_year" STRING NOT NULL,
    "policy_url" STRING,
    "application_url" STRING,
    "published_admission_number" INT4,
    "uses_catchment" BOOL NOT NULL DEFAULT false,
    "uses_distance" BOOL NOT NULL DEFAULT false,
    "uses_nodal_point" BOOL NOT NULL DEFAULT false,
    "uses_feeder_school" BOOL NOT NULL DEFAULT false,
    "uses_faith_criteria" BOOL NOT NULL DEFAULT false,
    "uses_selection" BOOL NOT NULL DEFAULT false,
    "summary" STRING,
    "source_verified_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "admission_arrangements_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "historical_offers" (
    "id" STRING NOT NULL,
    "school_urn" STRING NOT NULL,
    "academic_year" STRING NOT NULL,
    "published_admission_number" INT4,
    "applications" INT4,
    "places_offered" INT4,
    "last_criterion_offered" STRING,
    "furthest_distance_offered_metres" FLOAT8,
    "on_time_applications" INT4,
    "late_applications" INT4,
    "source" STRING NOT NULL,
    "methodology" STRING,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "historical_offers_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "postcode_cache" (
    "normalised_postcode" STRING NOT NULL,
    "latitude" FLOAT8 NOT NULL,
    "longitude" FLOAT8 NOT NULL,
    "local_authority_code" STRING,
    "source" STRING NOT NULL,
    "fetched_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expires_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "postcode_cache_pkey" PRIMARY KEY ("normalised_postcode")
);

-- CreateTable
CREATE TABLE "ingestion_runs" (
    "id" STRING NOT NULL,
    "source" STRING NOT NULL,
    "source_date" TIMESTAMP(3),
    "status" "IngestionStatus" NOT NULL DEFAULT 'RUNNING',
    "rows_processed" INT4 NOT NULL DEFAULT 0,
    "rows_inserted" INT4 NOT NULL DEFAULT 0,
    "rows_updated" INT4 NOT NULL DEFAULT 0,
    "rows_rejected" INT4 NOT NULL DEFAULT 0,
    "geometry_records" INT4 NOT NULL DEFAULT 0,
    "metrics_records" INT4 NOT NULL DEFAULT 0,
    "duration_seconds" FLOAT8,
    "workflow_run_url" STRING,
    "git_sha" STRING,
    "error_summary" STRING,
    "started_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finished_at" TIMESTAMP(3),

    CONSTRAINT "ingestion_runs_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "schools_normalised_name_idx" ON "schools"("normalised_name");

-- CreateIndex
CREATE INDEX "schools_postcode_idx" ON "schools"("postcode");

-- CreateIndex
CREATE INDEX "schools_postcode_prefix_idx" ON "schools"("postcode_prefix");

-- CreateIndex
CREATE INDEX "schools_local_authority_code_idx" ON "schools"("local_authority_code");

-- CreateIndex
CREATE INDEX "schools_phase_code_idx" ON "schools"("phase_code");

-- CreateIndex
CREATE INDEX "schools_establishment_type_code_idx" ON "schools"("establishment_type_code");

-- CreateIndex
CREATE INDEX "schools_status_idx" ON "schools"("status");

-- CreateIndex
CREATE INDEX "schools_trust_id_idx" ON "schools"("trust_id");

-- CreateIndex
CREATE INDEX "schools_latitude_longitude_idx" ON "schools"("latitude", "longitude");

-- CreateIndex
CREATE INDEX "academy_trusts_trust_name_idx" ON "academy_trusts"("trust_name");

-- CreateIndex
CREATE INDEX "school_relationships_from_urn_idx" ON "school_relationships"("from_urn");

-- CreateIndex
CREATE INDEX "school_relationships_to_urn_idx" ON "school_relationships"("to_urn");

-- CreateIndex
CREATE INDEX "school_relationships_relationship_type_idx" ON "school_relationships"("relationship_type");

-- CreateIndex
CREATE INDEX "school_metrics_metric_code_academic_year_idx" ON "school_metrics"("metric_code", "academic_year");

-- CreateIndex
CREATE INDEX "school_metrics_school_urn_academic_year_idx" ON "school_metrics"("school_urn", "academic_year");

-- CreateIndex
CREATE UNIQUE INDEX "school_metrics_school_urn_metric_code_academic_year_key" ON "school_metrics"("school_urn", "metric_code", "academic_year");

-- CreateIndex
CREATE INDEX "catchment_sources_local_authority_code_academic_year_idx" ON "catchment_sources"("local_authority_code", "academic_year");

-- CreateIndex
CREATE INDEX "catchment_areas_source_id_idx" ON "catchment_areas"("source_id");

-- CreateIndex
CREATE INDEX "catchment_areas_academic_year_idx" ON "catchment_areas"("academic_year");

-- CreateIndex
CREATE INDEX "catchment_areas_minimum_latitude_maximum_latitude_minimum_l_idx" ON "catchment_areas"("minimum_latitude", "maximum_latitude", "minimum_longitude", "maximum_longitude");

-- CreateIndex
CREATE INDEX "school_catchment_areas_catchment_area_id_idx" ON "school_catchment_areas"("catchment_area_id");

-- CreateIndex
CREATE UNIQUE INDEX "school_catchment_areas_school_urn_catchment_area_id_key" ON "school_catchment_areas"("school_urn", "catchment_area_id");

-- CreateIndex
CREATE INDEX "admission_arrangements_academic_year_idx" ON "admission_arrangements"("academic_year");

-- CreateIndex
CREATE UNIQUE INDEX "admission_arrangements_school_urn_academic_year_key" ON "admission_arrangements"("school_urn", "academic_year");

-- CreateIndex
CREATE INDEX "historical_offers_academic_year_idx" ON "historical_offers"("academic_year");

-- CreateIndex
CREATE UNIQUE INDEX "historical_offers_school_urn_academic_year_key" ON "historical_offers"("school_urn", "academic_year");

-- CreateIndex
CREATE INDEX "postcode_cache_expires_at_idx" ON "postcode_cache"("expires_at");

-- CreateIndex
CREATE INDEX "ingestion_runs_source_started_at_idx" ON "ingestion_runs"("source", "started_at");

-- AddForeignKey
ALTER TABLE "schools" ADD CONSTRAINT "schools_local_authority_code_fkey" FOREIGN KEY ("local_authority_code") REFERENCES "local_authorities"("code") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "schools" ADD CONSTRAINT "schools_trust_id_fkey" FOREIGN KEY ("trust_id") REFERENCES "academy_trusts"("trust_id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "school_relationships" ADD CONSTRAINT "school_relationships_from_urn_fkey" FOREIGN KEY ("from_urn") REFERENCES "schools"("urn") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "school_relationships" ADD CONSTRAINT "school_relationships_to_urn_fkey" FOREIGN KEY ("to_urn") REFERENCES "schools"("urn") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "school_metrics" ADD CONSTRAINT "school_metrics_school_urn_fkey" FOREIGN KEY ("school_urn") REFERENCES "schools"("urn") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "catchment_sources" ADD CONSTRAINT "catchment_sources_local_authority_code_fkey" FOREIGN KEY ("local_authority_code") REFERENCES "local_authorities"("code") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "catchment_areas" ADD CONSTRAINT "catchment_areas_source_id_fkey" FOREIGN KEY ("source_id") REFERENCES "catchment_sources"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "school_catchment_areas" ADD CONSTRAINT "school_catchment_areas_school_urn_fkey" FOREIGN KEY ("school_urn") REFERENCES "schools"("urn") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "school_catchment_areas" ADD CONSTRAINT "school_catchment_areas_catchment_area_id_fkey" FOREIGN KEY ("catchment_area_id") REFERENCES "catchment_areas"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "admission_arrangements" ADD CONSTRAINT "admission_arrangements_school_urn_fkey" FOREIGN KEY ("school_urn") REFERENCES "schools"("urn") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "historical_offers" ADD CONSTRAINT "historical_offers_school_urn_fkey" FOREIGN KEY ("school_urn") REFERENCES "schools"("urn") ON DELETE RESTRICT ON UPDATE CASCADE;

