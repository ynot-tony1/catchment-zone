import { describe, expect, it } from "vitest";
import {
  CATCHMENT_CHECK_STATUSES,
  CATCHMENT_DISCLAIMER_TEXT,
  CATCHMENT_NEAR_BOUNDARY_TEXT,
  FORBIDDEN_ADMISSIONS_WORDS,
} from "./constants";

describe("catchment status vocabulary", () => {
  it("contains exactly the six allowed statuses and nothing else", () => {
    expect(CATCHMENT_CHECK_STATUSES).toEqual([
      "INSIDE_OFFICIAL_PRIORITY_AREA",
      "OUTSIDE_OFFICIAL_PRIORITY_AREA",
      "NO_FIXED_CATCHMENT_USED",
      "OFFICIAL_BOUNDARY_NOT_AVAILABLE",
      "POSTCODE_RESULT_NEAR_BOUNDARY",
      "ACADEMIC_YEAR_NOT_AVAILABLE",
    ]);
  });

  it("never includes a forbidden guarantee word as a status value", () => {
    for (const status of CATCHMENT_CHECK_STATUSES) {
      for (const forbidden of FORBIDDEN_ADMISSIONS_WORDS) {
        expect(status).not.toContain(forbidden);
      }
    }
  });
});

describe("disclaimer copy", () => {
  it("the disclaimer text does not itself contain a forbidden word", () => {
    for (const forbidden of FORBIDDEN_ADMISSIONS_WORDS) {
      expect(CATCHMENT_DISCLAIMER_TEXT.toUpperCase()).not.toContain(forbidden);
      expect(CATCHMENT_NEAR_BOUNDARY_TEXT.toUpperCase()).not.toContain(forbidden);
    }
  });

  it("states that a place is not guaranteed", () => {
    expect(CATCHMENT_DISCLAIMER_TEXT).toContain("does not guarantee");
  });

  it("uses no em dash or double-hyphen punctuation", () => {
    for (const text of [CATCHMENT_DISCLAIMER_TEXT, CATCHMENT_NEAR_BOUNDARY_TEXT]) {
      expect(text).not.toContain("—");
      expect(text).not.toContain("--");
    }
  });
});
