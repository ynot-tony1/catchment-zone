-- Add a unique constraint so a catchment area's (source, geometry checksum)
-- pair is a real conflict target for upserts. Without this, re-running the
-- catchment importer for the same source has no idempotency key and would
-- insert duplicate polygons on every run.
CREATE UNIQUE INDEX "catchment_areas_source_id_geometry_checksum_key" ON "catchment_areas"("source_id", "geometry_checksum");
