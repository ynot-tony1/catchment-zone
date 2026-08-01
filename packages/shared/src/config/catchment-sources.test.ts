import { describe, expect, it } from "vitest";
import {
  findCatchmentSource,
  getPilotLocalAuthorityCodes,
  hasAnyCatchmentSourceForLa,
  listEnabledCatchmentSources,
} from "./catchment-sources";

describe("catchment sources loaded from config/catchment-sources.yml", () => {
  it("reflects the current single-pilot-authority reality (Sheffield only)", () => {
    expect(getPilotLocalAuthorityCodes()).toEqual(["373"]);
  });

  it("has both a primary and secondary source for Sheffield 2025-2026", () => {
    const sources = listEnabledCatchmentSources();
    expect(sources).toHaveLength(2);
    expect(sources.map((s) => s.source_type).sort()).toEqual(["primary_catchment", "secondary_catchment"]);
  });

  it("finds the Sheffield primary source for the current academic year", () => {
    const source = findCatchmentSource("373", "2025-2026", "primary_catchment");
    expect(source).toBeDefined();
    expect(source?.local_authority_name).toBe("Sheffield");
  });

  it("returns undefined for a local authority with no coverage", () => {
    expect(findCatchmentSource("999", "2025-2026", "primary_catchment")).toBeUndefined();
    expect(hasAnyCatchmentSourceForLa("999")).toBe(false);
  });

  it("returns undefined for a covered authority but an unavailable academic year", () => {
    expect(findCatchmentSource("373", "2030-2031", "primary_catchment")).toBeUndefined();
    expect(hasAnyCatchmentSourceForLa("373")).toBe(true);
  });
});
