-- Add a unique constraint so a catchment source's (local authority,
-- academic year, source type) triple is a real conflict target for
-- upserts. Without this, re-running the catchment importer for the same
-- local authority/year has no idempotency key and would insert a
-- duplicate catchment_sources row on every run.
CREATE UNIQUE INDEX "catchment_sources_la_code_academic_year_source_type_key" ON "catchment_sources"("local_authority_code", "academic_year", "source_type");
