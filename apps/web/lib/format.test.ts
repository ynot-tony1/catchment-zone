import { describe, expect, it } from "vitest";
import {
  formatDate,
  formatDateTime,
  formatDistanceMetres,
  formatMetricValue,
  formatNumber,
  formatSchoolStatus,
} from "./format";

describe("formatNumber", () => {
  it("formats with UK grouping", () => {
    expect(formatNumber(1234)).toBe("1,234");
  });

  it("respects maximumFractionDigits", () => {
    expect(formatNumber(1.2345, 2)).toBe("1.23");
  });
});

describe("formatDate / formatDateTime", () => {
  it("returns a placeholder for null or undefined", () => {
    expect(formatDate(null)).toBe("Not available");
    expect(formatDate(undefined)).toBe("Not available");
    expect(formatDateTime(null)).toBe("Not available");
  });

  it("returns a placeholder for an invalid date string", () => {
    expect(formatDate("not-a-date")).toBe("Not available");
  });

  it("formats a valid date", () => {
    expect(formatDate("2025-09-01T00:00:00.000Z")).toBe("1 September 2025");
  });
});

describe("formatSchoolStatus", () => {
  it("maps every known enum value to a human label", () => {
    expect(formatSchoolStatus("OPEN")).toBe("Open");
    expect(formatSchoolStatus("OPEN_BUT_PROPOSED_TO_CLOSE")).toBe("Open, proposed to close");
    expect(formatSchoolStatus("PROPOSED_TO_OPEN")).toBe("Proposed to open");
    expect(formatSchoolStatus("CLOSED")).toBe("Closed");
  });

  it("falls back to the raw value for an unrecognised status", () => {
    expect(formatSchoolStatus("SOMETHING_ELSE")).toBe("SOMETHING_ELSE");
  });
});

describe("formatDistanceMetres", () => {
  it("formats sub-kilometre distances in metres", () => {
    expect(formatDistanceMetres(450)).toBe("450 m");
  });

  it("formats distances of a kilometre or more in km", () => {
    expect(formatDistanceMetres(1500)).toBe("1.5 km");
  });
});

describe("formatMetricValue", () => {
  it("returns a placeholder for a null value regardless of definition", () => {
    expect(formatMetricValue(null, null)).toBe("Not available");
  });

  it("formats a percent metric with one decimal place", () => {
    const definition = {
      code: "test",
      label: "Test",
      description: "",
      denominator: "",
      unit: "percent",
      phases: [],
      comparability_notes: "",
    };
    expect(formatMetricValue(87.654, definition)).toBe("87.7%");
  });

  it("formats a value with no definition using the default two decimal places", () => {
    expect(formatMetricValue(3.14159, null)).toBe("3.14");
  });
});
