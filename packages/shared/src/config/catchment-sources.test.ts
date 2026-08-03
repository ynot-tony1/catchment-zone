import { describe, expect, it } from "vitest";
import {
  findCatchmentSource,
  getPilotLocalAuthorityCodes,
  hasAnyCatchmentSourceForLa,
  listEnabledCatchmentSources,
} from "./catchment-sources";

// Local authorities with real pilot catchment coverage; kept as a single
// list so adding another authority only means editing here and in
// catchment-sources.yml, not chasing a hardcoded global total that grows
// every time a new one is added.
const PILOT_LOCAL_AUTHORITIES = [
  { code: "373", name: "Sheffield", sourceTypeCount: 2 },
  { code: "S12000033", name: "Aberdeen City", sourceTypeCount: 2 },
  { code: "S12000036", name: "City of Edinburgh", sourceTypeCount: 4 },
  { code: "S12000049", name: "Glasgow City", sourceTypeCount: 4 },
  { code: "S12000047", name: "Fife", sourceTypeCount: 4 },
  { code: "S12000050", name: "North Lanarkshire", sourceTypeCount: 4 },
  { code: "S12000017", name: "Highland", sourceTypeCount: 2 },
  { code: "S12000042", name: "Dundee City", sourceTypeCount: 4 },
  { code: "S12000048", name: "Perth and Kinross", sourceTypeCount: 4 },
  { code: "S12000021", name: "North Ayrshire", sourceTypeCount: 4 },
  { code: "S12000028", name: "South Ayrshire", sourceTypeCount: 4 },
  { code: "S12000041", name: "Angus", sourceTypeCount: 3 },
  { code: "S12000005", name: "Clackmannanshire", sourceTypeCount: 4 },
  { code: "S12000034", name: "Aberdeenshire", sourceTypeCount: 2 },
  { code: "S12000023", name: "Orkney Islands", sourceTypeCount: 1 },
  { code: "S12000030", name: "Stirling", sourceTypeCount: 2 },
  { code: "S12000035", name: "Argyll and Bute", sourceTypeCount: 4 },
  { code: "S12000020", name: "Moray", sourceTypeCount: 3 },
  { code: "S12000006", name: "Dumfries and Galloway", sourceTypeCount: 1 },
];

describe("catchment sources loaded from config/catchment-sources.yml", () => {
  it("reflects every local authority with real pilot catchment coverage", () => {
    expect(getPilotLocalAuthorityCodes().sort()).toEqual(
      PILOT_LOCAL_AUTHORITIES.map((la) => la.code).sort(),
    );
  });

  it("has the expected number of enabled sources for each pilot authority", () => {
    const sources = listEnabledCatchmentSources();
    expect(sources).toHaveLength(
      PILOT_LOCAL_AUTHORITIES.reduce((sum, la) => sum + la.sourceTypeCount, 0),
    );
    for (const la of PILOT_LOCAL_AUTHORITIES) {
      const laSources = sources.filter(
        (s) => s.local_authority_code === la.code,
      );
      expect(laSources).toHaveLength(la.sourceTypeCount);
      expect(laSources.every((s) => s.local_authority_name === la.name)).toBe(
        true,
      );
    }
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
