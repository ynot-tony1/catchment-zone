import { describe, expect, it } from "vitest";
import {
  boundingBoxAroundPoint,
  distanceKm,
  distanceToBoundaryMetres,
  isPointInBbox,
  isPointInGeometry,
  parseCatchmentGeometry,
} from "./geo";

describe("isPointInBbox", () => {
  const bounds = {
    minimumLatitude: 50,
    maximumLatitude: 51,
    minimumLongitude: -1,
    maximumLongitude: 0,
  };

  it("returns true for a point inside the box", () => {
    expect(isPointInBbox(50.5, -0.5, bounds)).toBe(true);
  });

  it("returns false for a point outside the box", () => {
    expect(isPointInBbox(52, -0.5, bounds)).toBe(false);
  });

  it("treats the boundary as inclusive", () => {
    expect(isPointInBbox(50, -1, bounds)).toBe(true);
  });
});

describe("parseCatchmentGeometry", () => {
  it("parses a valid Polygon", () => {
    const geojson = JSON.stringify({
      type: "Polygon",
      coordinates: [
        [
          [0, 0],
          [0, 1],
          [1, 1],
          [1, 0],
          [0, 0],
        ],
      ],
    });
    expect(parseCatchmentGeometry(geojson)?.type).toBe("Polygon");
  });

  it("returns null for malformed JSON rather than throwing", () => {
    expect(parseCatchmentGeometry("{not json")).toBeNull();
  });

  it("returns null for a well-formed but unsupported geometry type", () => {
    const geojson = JSON.stringify({ type: "Point", coordinates: [0, 0] });
    expect(parseCatchmentGeometry(geojson)).toBeNull();
  });
});

describe("isPointInGeometry", () => {
  const square = {
    type: "Polygon" as const,
    coordinates: [
      [
        [0, 0],
        [0, 10],
        [10, 10],
        [10, 0],
        [0, 0],
      ],
    ],
  };

  it("detects a point inside the polygon", () => {
    expect(isPointInGeometry(5, 5, square)).toBe(true);
  });

  it("detects a point outside the polygon", () => {
    expect(isPointInGeometry(20, 20, square)).toBe(false);
  });
});

describe("distanceToBoundaryMetres", () => {
  it("returns a small distance for a point near the edge of a Polygon", () => {
    const square = {
      type: "Polygon" as const,
      coordinates: [
        [
          [0, 0],
          [0, 1],
          [1, 1],
          [1, 0],
          [0, 0],
        ],
      ],
    };
    const distance = distanceToBoundaryMetres(0.5, 0.001, square);
    expect(distance).toBeGreaterThan(0);
    expect(distance).toBeLessThan(1000);
  });

  it("handles a MultiPolygon without throwing", () => {
    const multi = {
      type: "MultiPolygon" as const,
      coordinates: [
        [
          [
            [0, 0],
            [0, 1],
            [1, 1],
            [1, 0],
            [0, 0],
          ],
        ],
        [
          [
            [5, 5],
            [5, 6],
            [6, 6],
            [6, 5],
            [5, 5],
          ],
        ],
      ],
    };
    const distance = distanceToBoundaryMetres(0.5, 0.5, multi);
    expect(Number.isFinite(distance)).toBe(true);
    expect(distance).toBeGreaterThanOrEqual(0);
  });
});

describe("distanceKm", () => {
  it("returns zero for identical points", () => {
    expect(
      distanceKm({ lat: 51.5, lon: -0.1 }, { lat: 51.5, lon: -0.1 }),
    ).toBeCloseTo(0, 5);
  });

  it("returns a plausible distance between two known UK points", () => {
    // London to Manchester is roughly 260-300km great-circle.
    const km = distanceKm(
      { lat: 51.5074, lon: -0.1278 },
      { lat: 53.4808, lon: -2.2426 },
    );
    expect(km).toBeGreaterThan(250);
    expect(km).toBeLessThan(320);
  });
});

describe("boundingBoxAroundPoint", () => {
  it("produces a symmetric box around the centre point", () => {
    const box = boundingBoxAroundPoint(51, 0, 10);
    expect(box.minLat).toBeLessThan(51);
    expect(box.maxLat).toBeGreaterThan(51);
    expect(box.minLon).toBeLessThan(0);
    expect(box.maxLon).toBeGreaterThan(0);
  });
});
