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
  { code: "S12000006", name: "Dumfries and Galloway", sourceTypeCount: 3 },
  { code: "S12000008", name: "East Ayrshire", sourceTypeCount: 4 },
  { code: "S12000013", name: "Na h-Eileanan an Iar", sourceTypeCount: 2 },
  { code: "W-666", name: "Powys", sourceTypeCount: 2 },
  { code: "W-668", name: "Pembrokeshire", sourceTypeCount: 1 },
  { code: "S12000038", name: "Renfrewshire", sourceTypeCount: 4 },
  { code: "S12000011", name: "East Renfrewshire", sourceTypeCount: 4 },
  { code: "S12000019", name: "Midlothian", sourceTypeCount: 4 },
  { code: "S12000040", name: "West Lothian", sourceTypeCount: 4 },
  { code: "S12000029", name: "South Lanarkshire", sourceTypeCount: 4 },
  { code: "S12000039", name: "West Dunbartonshire", sourceTypeCount: 4 },
  { code: "S12000014", name: "Falkirk", sourceTypeCount: 4 },
  { code: "S12000026", name: "Scottish Borders", sourceTypeCount: 3 },
  { code: "S12000045", name: "East Dunbartonshire", sourceTypeCount: 4 },
  { code: "S12000010", name: "East Lothian", sourceTypeCount: 3 },
  { code: "926", name: "Norfolk", sourceTypeCount: 3 },
  { code: "825", name: "Buckinghamshire", sourceTypeCount: 5 },
  { code: "869", name: "West Berkshire", sourceTypeCount: 2 },
  { code: "892", name: "Nottingham", sourceTypeCount: 2 },
  { code: "801", name: "Bristol, City of", sourceTypeCount: 2 },
  { code: "865", name: "Wiltshire", sourceTypeCount: 2 },
  { code: "929", name: "Northumberland", sourceTypeCount: 3 },
  { code: "816", name: "York", sourceTypeCount: 2 },
  { code: "895", name: "Cheshire East", sourceTypeCount: 2 },
  { code: "896", name: "Cheshire West and Chester", sourceTypeCount: 2 },
  { code: "882", name: "Southend-on-Sea", sourceTypeCount: 2 },
  { code: "878", name: "Devon", sourceTypeCount: 2 },
  { code: "867", name: "Bracknell Forest", sourceTypeCount: 2 },
  { code: "874", name: "Peterborough", sourceTypeCount: 2 },
  { code: "392", name: "North Tyneside", sourceTypeCount: 3 },
  { code: "211", name: "Tower Hamlets", sourceTypeCount: 2 },
  { code: "316", name: "Newham", sourceTypeCount: 2 },
  { code: "872", name: "Wokingham", sourceTypeCount: 2 },
  { code: "894", name: "Telford and Wrekin", sourceTypeCount: 2 },
  { code: "390", name: "Gateshead", sourceTypeCount: 2 },
  { code: "813", name: "North Lincolnshire", sourceTypeCount: 2 },
  { code: "940", name: "North Northamptonshire", sourceTypeCount: 4 },
  { code: "873", name: "Cambridgeshire", sourceTypeCount: 2 },
  { code: "937", name: "Warwickshire", sourceTypeCount: 7 },
  { code: "893", name: "Shropshire", sourceTypeCount: 2 },
  { code: "885", name: "Worcestershire", sourceTypeCount: 3 },
  { code: "933", name: "Somerset", sourceTypeCount: 3 },
  { code: "908", name: "Cornwall", sourceTypeCount: 2 },
  { code: "811", name: "East Riding of Yorkshire", sourceTypeCount: 2 },
  { code: "891", name: "Nottinghamshire", sourceTypeCount: 2 },
  { code: "888", name: "Lancashire", sourceTypeCount: 1 },
  { code: "838", name: "Dorset", sourceTypeCount: 3 },
  { code: "371", name: "Doncaster", sourceTypeCount: 2 },
  { code: "334", name: "Solihull", sourceTypeCount: 2 },
  { code: "381", name: "Calderdale", sourceTypeCount: 6 },
  { code: "845", name: "East Sussex", sourceTypeCount: 2 },
  {
    code: "839",
    name: "Bournemouth, Christchurch and Poole",
    sourceTypeCount: 2,
  },
  { code: "383", name: "Leeds", sourceTypeCount: 2 },
  { code: "931", name: "Oxfordshire", sourceTypeCount: 2 },
  { code: "876", name: "Halton", sourceTypeCount: 1 },
  { code: "815", name: "North Yorkshire", sourceTypeCount: 2 },
  { code: "919", name: "Hertfordshire", sourceTypeCount: 1 },
  { code: "382", name: "Kirklees", sourceTypeCount: 3 },
  { code: "850", name: "Hampshire", sourceTypeCount: 3 },
  { code: "330", name: "Birmingham", sourceTypeCount: 1 },
  { code: "359", name: "Wigan", sourceTypeCount: 1 },
  { code: "942", name: "Cumberland", sourceTypeCount: 2 },
  { code: "831", name: "Derby", sourceTypeCount: 2 },
  { code: "861", name: "Stoke-on-Trent", sourceTypeCount: 1 },
  { code: "851", name: "Portsmouth", sourceTypeCount: 3 },
  { code: "806", name: "Middlesbrough", sourceTypeCount: 1 },
  { code: "807", name: "Redcar and Cleveland", sourceTypeCount: 4 },
  { code: "393", name: "South Tyneside", sourceTypeCount: 1 },
  { code: "884", name: "Herefordshire", sourceTypeCount: 2 },
  { code: "S12000027", name: "Shetland Islands", sourceTypeCount: 2 },
  { code: "W-681", name: "Cardiff", sourceTypeCount: 4 },
  { code: "W-679", name: "Monmouthshire", sourceTypeCount: 3 },
  { code: "823", name: "Central Bedfordshire", sourceTypeCount: 3 },
  { code: "372", name: "Rotherham", sourceTypeCount: 2 },
  { code: "S12000018", name: "Inverclyde", sourceTypeCount: 4 },
  { code: "860", name: "Staffordshire", sourceTypeCount: 3 },
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
