import { describe, expect, it } from "vitest";
import {
  BboxQuerySchema,
  decodeCursor,
  encodeCursor,
  firstValue,
  splitCsv,
} from "./common";

describe("firstValue", () => {
  it("returns the value unchanged for a single string", () => {
    expect(firstValue("a")).toBe("a");
  });
  it("returns the first element for an array", () => {
    expect(firstValue(["a", "b"])).toBe("a");
  });
  it("returns undefined for undefined", () => {
    expect(firstValue(undefined)).toBeUndefined();
  });
});

describe("splitCsv", () => {
  it("splits and trims comma-separated values", () => {
    expect(splitCsv("a, b ,c")).toEqual(["a", "b", "c"]);
  });
  it("returns undefined for an empty string", () => {
    expect(splitCsv("")).toBeUndefined();
  });
});

describe("cursor encode/decode", () => {
  it("round-trips a payload", () => {
    const payload = { name: "Foo", urn: "123456" };
    const cursor = encodeCursor(payload);
    expect(decodeCursor(cursor)).toEqual(payload);
  });

  it("returns null for a malformed cursor instead of throwing", () => {
    expect(decodeCursor("not-valid-base64url-json")).toBeNull();
  });
});

describe("BboxQuerySchema", () => {
  it("parses a valid bbox string", () => {
    const result = BboxQuerySchema.parse("-1.5,53.3,-1.4,53.4");
    expect(result).toEqual([-1.5, 53.3, -1.4, 53.4]);
  });

  it("rejects an inverted bbox", () => {
    expect(() => BboxQuerySchema.parse("-1.4,53.3,-1.5,53.4")).toThrow();
  });

  it("rejects a bbox larger than the maximum area", () => {
    expect(() => BboxQuerySchema.parse("-10,45,10,65")).toThrow();
  });

  it("rejects out-of-range coordinates", () => {
    expect(() => BboxQuerySchema.parse("-200,53.3,-1.4,53.4")).toThrow();
  });
});
