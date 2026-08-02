import { describe, expect, it } from "vitest";
import {
  findCatchmentSource,
  getPilotLocalAuthorityCodes,
  hasAnyCatchmentSourceForLa,
  listEnabledCatchmentSources,
} from "./catchment-sources";

describe("catchment sources loaded from config/catchment-sources.yml", () => {
  it("reflects the current pilot-authority reality (Sheffield, Aberdeen City)", () => {
    expect(getPilotLocalAuthorityCodes().sort()).toEqual(["373", "S12000033"]);
  });

  it("has both a primary and secondary source for each pilot authority", () => {
    const sources = listEnabledCatchmentSources();
    expect(sources).toHaveLength(4);
    expect(sources.map((s) => s.source_type).sort()).toEqual([
      "primary_catchment",
      "primary_catchment",
      "secondary_catchment",
      "secondary_catchment",
    ]);
  });

  it("finds the Sheffield primary source for the current academic year", () => {
    const source = findCatchmentSource("373", "2025-2026", "primary_catchment");
    expect(source).toBeDefined();
    expect(source?.local_authority_name).toBe("Sheffield");
  });

  it("finds the Aberdeen City primary source for the current academic year", () => {
    const source = findCatchmentSource(
      "S12000033",
      "2025-2026",
      "primary_catchment",
    );
    expect(source).toBeDefined();
    expect(source?.local_authority_name).toBe("Aberdeen City");
  });

  it("returns undefined for a local authority with no coverage", () => {
    expect(
      findCatchmentSource("999", "2025-2026", "primary_catchment"),
    ).toBeUndefined();
    expect(hasAnyCatchmentSourceForLa("999")).toBe(false);
  });

  it("returns undefined for a covered authority but an unavailable academic year", () => {
    expect(
      findCatchmentSource("373", "2030-2031", "primary_catchment"),
    ).toBeUndefined();
    expect(hasAnyCatchmentSourceForLa("373")).toBe(true);
  });
});
