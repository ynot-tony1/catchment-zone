import { describe, expect, it } from "vitest";
import {
  findCatchmentSource,
  getPilotLocalAuthorityCodes,
  hasAnyCatchmentSourceForLa,
  listEnabledCatchmentSources,
} from "./catchment-sources";

describe("catchment sources loaded from config/catchment-sources.yml", () => {
  it("reflects the current pilot-authority reality (Sheffield, Aberdeen City, City of Edinburgh)", () => {
    expect(getPilotLocalAuthorityCodes().sort()).toEqual([
      "373",
      "S12000033",
      "S12000036",
    ]);
  });

  it("has both a primary and secondary source for Sheffield and Aberdeen City, and four denomination-split sources for Edinburgh", () => {
    const sources = listEnabledCatchmentSources();
    expect(sources).toHaveLength(8);
    expect(sources.map((s) => s.source_type).sort()).toEqual([
      "primary_catchment",
      "primary_catchment",
      "primary_catchment_nd",
      "primary_catchment_rc",
      "secondary_catchment",
      "secondary_catchment",
      "secondary_catchment_nd",
      "secondary_catchment_rc",
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

  it("finds Edinburgh's non-denominational primary source, but not under the plain primary_catchment type", () => {
    const ndSource = findCatchmentSource(
      "S12000036",
      "2025-2026",
      "primary_catchment_nd",
    );
    expect(ndSource).toBeDefined();
    expect(ndSource?.local_authority_name).toBe("City of Edinburgh");
    // Deliberate: ND/RC catchments overlap geographically, so they must
    // not be reachable under the exact source_type the /admissions
    // point-in-polygon checker looks up (see catchment-sources.yml's notes
    // on the Edinburgh entries).
    expect(
      findCatchmentSource("S12000036", "2025-2026", "primary_catchment"),
    ).toBeUndefined();
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
