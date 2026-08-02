-- Adds UK-nation support ahead of ingesting non-England data. Existing
-- rows are all GIAS/England-sourced, so the DEFAULT backfills them
-- correctly without a separate UPDATE step.
CREATE TYPE "Nation" AS ENUM ('ENGLAND', 'SCOTLAND', 'WALES', 'NORTHERN_IRELAND');

ALTER TABLE "schools" ADD COLUMN "nation" "Nation" NOT NULL DEFAULT 'ENGLAND';
ALTER TABLE "local_authorities" ADD COLUMN "nation" "Nation" NOT NULL DEFAULT 'ENGLAND';
