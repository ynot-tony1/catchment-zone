import { describe, expect, it } from "vitest";
import { parseSchoolSearchParams, schoolFiltersToSearchParams } from "./school";

describe("parseSchoolSearchParams", () => {
  it("applies defaults when no params are given", () => {
    const parsed = parseSchoolSearchParams({});
    expect(parsed.sort).toBe("name_asc");
    expect(parsed.limit).toBe(20);
  });

  it("parses a full set of filters from Next.js-shaped searchParams", () => {
    const parsed = parseSchoolSearchParams({
      q: "Springfield",
      status: "OPEN,CLOSED",
      hasSenProvision: "true",
      minAge: "3",
      maxAge: "11",
      sort: "opening_date_desc",
      limit: "50",
    });
    expect(parsed.q).toBe("Springfield");
    expect(parsed.status).toEqual(["OPEN", "CLOSED"]);
    expect(parsed.hasSenProvision).toBe(true);
    expect(parsed.minAge).toBe(3);
    expect(parsed.maxAge).toBe(11);
    expect(parsed.sort).toBe("opening_date_desc");
    expect(parsed.limit).toBe(50);
  });

  it("rejects sort=distance without lat/lon", () => {
    expect(() => parseSchoolSearchParams({ sort: "distance" })).toThrow();
  });

  it("accepts sort=distance with lat and lon", () => {
    const parsed = parseSchoolSearchParams({
      sort: "distance",
      lat: "53.38",
      lon: "-1.47",
    });
    expect(parsed.sort).toBe("distance");
  });

  it("rejects minAge greater than maxAge", () => {
    expect(() =>
      parseSchoolSearchParams({ minAge: "11", maxAge: "3" }),
    ).toThrow();
  });

  it("accepts alphanumeric URNs (Scotland's SchUID, Northern Ireland's Reference)", () => {
    expect(parseSchoolSearchParams({ urn: "8212627P" }).urn).toBe("8212627P");
    expect(parseSchoolSearchParams({ urn: "1AB0427" }).urn).toBe("1AB0427");
  });

  it("rejects a URN with invalid characters", () => {
    expect(() => parseSchoolSearchParams({ urn: "abc 123!" })).toThrow();
  });
});

describe("schoolFiltersToSearchParams round trip", () => {
  it("round-trips through parseSchoolSearchParams", () => {
    const original = parseSchoolSearchParams({
      q: "Springfield",
      phaseCode: "primary",
      status: "OPEN",
      sort: "opening_date_asc",
      limit: "10",
    });
    const params = schoolFiltersToSearchParams(original);
    const rawFromUrl = Object.fromEntries(params.entries());
    const reparsed = parseSchoolSearchParams(rawFromUrl);
    expect(reparsed).toEqual(original);
  });

  it("omits default values from the URL for a clean address bar", () => {
    const params = schoolFiltersToSearchParams({ sort: "name_asc", limit: 20 });
    expect(params.has("sort")).toBe(false);
    expect(params.has("limit")).toBe(false);
  });
});
