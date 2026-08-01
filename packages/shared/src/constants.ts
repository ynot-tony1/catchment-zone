// Shared, non-schema constants used by both server and client code in the
// web app. Keeping these here (rather than duplicating literals per page)
// means the disclaimer text, forbidden-word list and the allowed catchment
// statuses only exist in one place.

/**
 * The complete, closed set of catchment/admissions check outcomes. This is
 * intentionally exhaustive: no code path may emit a status outside this
 * list, and in particular nothing here may imply a guaranteed place.
 */
export const CATCHMENT_CHECK_STATUSES = [
  "INSIDE_OFFICIAL_PRIORITY_AREA",
  "OUTSIDE_OFFICIAL_PRIORITY_AREA",
  "NO_FIXED_CATCHMENT_USED",
  "OFFICIAL_BOUNDARY_NOT_AVAILABLE",
  "POSTCODE_RESULT_NEAR_BOUNDARY",
  "ACADEMIC_YEAR_NOT_AVAILABLE",
] as const;

export type CatchmentCheckStatus = (typeof CATCHMENT_CHECK_STATUSES)[number];

/**
 * Words that must never appear anywhere in admissions/catchment copy or
 * status codes, because a mapped priority area is not an offer guarantee.
 * A unit test asserts none of these appear in the check-point response
 * shapes or in the admissions page copy.
 */
export const FORBIDDEN_ADMISSIONS_WORDS = [
  "ELIGIBLE",
  "GUARANTEED",
  "WILL_BE_ACCEPTED",
] as const;

/**
 * Rendered on every catchment/admissions check result, regardless of
 * status. Wording is fixed by product spec, do not alter without updating
 * the accompanying unit test that asserts its presence.
 */
export const CATCHMENT_DISCLAIMER_TEXT =
  "This result shows the published priority or catchment area for the selected academic year. It does not guarantee that a school place will be offered. Check the official admissions policy before applying.";

/**
 * Shown in addition to the standard disclaimer when a postcode centroid
 * falls within the configured near-boundary distance of a catchment edge.
 */
export const CATCHMENT_NEAR_BOUNDARY_TEXT =
  "This postcode-centre result is too close to the boundary for a reliable address-level decision. Use the council's official checker or select the exact property location.";

export const DEFAULT_PAGE_SIZE = 20;
export const MAX_PAGE_SIZE = 100;

export const MAX_MAP_FEATURES = 500;

/** Maximum bounding-box area (in square degrees) accepted by map endpoints,
 * to stop a single request from requesting the whole of England at a zoom
 * level that would return an unbounded number of features. Roughly
 * generous enough to cover a large metropolitan county at once. */
export const MAX_BBOX_AREA_DEGREES = 4;

export const DEFAULT_CATCHMENT_BOUNDARY_WARNING_METRES = 75;

/** Fallback string shown by /status when no git SHA env var is available
 * (i.e. running locally, not on Vercel). */
export const UNKNOWN_GIT_SHA = "unknown";
