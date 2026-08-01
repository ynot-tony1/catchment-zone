import { describe, expect, it } from "vitest";
import { currentAcademicYear } from "./catchments";

describe("currentAcademicYear", () => {
  it("returns the year pair starting in September for a date after September", () => {
    expect(currentAcademicYear(new Date("2026-10-15T00:00:00.000Z"))).toBe("2026-2027");
  });

  it("returns the previous September's year pair for a date before September", () => {
    expect(currentAcademicYear(new Date("2026-08-01T00:00:00.000Z"))).toBe("2025-2026");
  });

  it("treats 1 September itself as the start of the new academic year", () => {
    expect(currentAcademicYear(new Date("2026-09-01T00:00:00.000Z"))).toBe("2026-2027");
  });

  it("treats 31 August as still the previous academic year", () => {
    expect(currentAcademicYear(new Date("2026-08-31T23:59:59.000Z"))).toBe("2025-2026");
  });
});
