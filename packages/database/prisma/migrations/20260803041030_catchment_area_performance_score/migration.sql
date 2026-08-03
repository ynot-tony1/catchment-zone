-- Adds a computed performance score to each catchment area, populated by
-- the ingestor's refresh-catchment-scores command (not at import time):
-- the percentile rank (0-1, higher is better) on whichever performance
-- metric applies to the area's phase and nation, averaged across every
-- school whose point falls inside the polygon. Both columns are
-- nullable and start NULL for every existing row - most catchment areas
-- currently have no matching metric (e.g. every Scottish catchment,
-- since Scotland has no performance metrics at all), and this must
-- never be backfilled with a guess.
ALTER TABLE "catchment_areas" ADD COLUMN "performance_percentile" FLOAT8;
ALTER TABLE "catchment_areas" ADD COLUMN "performance_metric_code" STRING;
