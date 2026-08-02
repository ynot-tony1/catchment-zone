-- Northern Ireland is excluded from this project by decision: the only
-- machine-readable register found for it (Open Data NI's "School
-- Locations" dataset) has been stale since February 2016, with no newer
-- extract available. All 1,555 NORTHERN_IRELAND schools rows were deleted
-- from production before this migration ran (verified: 0 remaining), so
-- dropping the enum value is safe - no row references it.
ALTER TYPE "Nation" DROP VALUE 'NORTHERN_IRELAND';
