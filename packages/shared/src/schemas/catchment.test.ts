import { describe, expect, it } from "vitest";
import {
  CatchmentCheckRequestSchema,
  CatchmentCheckStatusEnum,
} from "./catchment";

describe("CatchmentCheckRequestSchema", () => {
  it("accepts a request with a postcode", () => {
    const result = CatchmentCheckRequestSchema.parse({
      postcode: "S1 2HH",
      phase: "primary",
    });
    expect(result.postcode).toBe("S1 2HH");
  });

  it("accepts a request with a point", () => {
    const result = CatchmentCheckRequestSchema.parse({
      point: { lat: 53.38, lon: -1.47 },
      phase: "secondary",
    });
    expect(result.point).toEqual({ lat: 53.38, lon: -1.47 });
  });

  it("rejects a request with neither postcode nor point", () => {
    expect(() =>
      CatchmentCheckRequestSchema.parse({ phase: "primary" }),
    ).toThrow();
  });

  it("rejects a request with both postcode and point", () => {
    expect(() =>
      CatchmentCheckRequestSchema.parse({
        postcode: "S1 2HH",
        point: { lat: 53.38, lon: -1.47 },
        phase: "primary",
      }),
    ).toThrow();
  });

  it("rejects a malformed academic year", () => {
    expect(() =>
      CatchmentCheckRequestSchema.parse({
        postcode: "S1 2HH",
        phase: "primary",
        academicYear: "2025",
      }),
    ).toThrow();
  });
});

describe("CatchmentCheckStatusEnum", () => {
  it("rejects a status outside the closed vocabulary", () => {
    expect(() => CatchmentCheckStatusEnum.parse("ELIGIBLE")).toThrow();
    expect(() => CatchmentCheckStatusEnum.parse("GUARANTEED")).toThrow();
  });
});
