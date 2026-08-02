"use client";

import { useEffect, useRef, useState } from "react";
import {
  MapLibreMap,
  NavigationControl,
  type GeoJSONSource,
  type MapLayerMouseEvent,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import Link from "next/link";
import { formatNation } from "@/lib/format";

type SchoolFeatureProperties = {
  urn: string;
  nation: string;
  schoolName: string;
  phaseName: string;
  status: string;
  sourceExtractDate: string | null;
};

type CatchmentFeatureProperties = {
  id: string;
  areaName: string;
  areaType: string;
  academicYear: string;
};

// Covers Great Britain (England, Scotland and Wales) - west to Scotland's
// Outer Hebrides, north to Shetland - not just England. Northern Ireland
// is deliberately excluded from this project (see PROJECT_STATUS.md).
const GB_BOUNDS: [number, number, number, number] = [-8.7, 49.8, 1.9, 61.0];

export function SchoolMap({
  styleUrl,
  attribution,
}: {
  styleUrl: string;
  attribution: string;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const showCatchmentsRef = useRef(false);
  const [selected, setSelected] = useState<SchoolFeatureProperties | null>(
    null,
  );
  const [selectedCatchment, setSelectedCatchment] =
    useState<CatchmentFeatureProperties | null>(null);
  const [showCatchments, setShowCatchments] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new MapLibreMap({
      container: containerRef.current,
      style: styleUrl,
      bounds: GB_BOUNDS,
      attributionControl: { customAttribution: attribution },
    });
    mapRef.current = map;
    map.addControl(new NavigationControl(), "top-right");

    map.on("load", () => {
      map.addSource("catchments", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "catchments-fill",
        type: "fill",
        source: "catchments",
        paint: {
          "fill-color": "#f08c00",
          "fill-opacity": 0.15,
        },
      });
      map.addLayer({
        id: "catchments-outline",
        type: "line",
        source: "catchments",
        paint: {
          "line-color": "#f08c00",
          "line-width": 1.5,
        },
      });

      map.addSource("schools", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "schools-points",
        type: "circle",
        source: "schools",
        paint: {
          "circle-radius": 5,
          "circle-color": "#3b5bdb",
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
        },
      });

      map.on("click", "schools-points", (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0];
        if (!feature || feature.geometry.type !== "Point") return;
        setSelectedCatchment(null);
        setSelected(feature.properties as SchoolFeatureProperties);
      });
      map.on("mouseenter", "schools-points", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "schools-points", () => {
        map.getCanvas().style.cursor = "";
      });

      map.on("click", "catchments-fill", (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0];
        if (!feature) return;
        setSelected(null);
        setSelectedCatchment(feature.properties as CatchmentFeatureProperties);
      });
      map.on("mouseenter", "catchments-fill", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "catchments-fill", () => {
        map.getCanvas().style.cursor = "";
      });

      loadSchoolsInView(map, setError);
      map.on("moveend", () => {
        loadSchoolsInView(map, setError);
        if (showCatchmentsRef.current) loadCatchmentsInView(map, setError);
      });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- map is created once; styleUrl/attribution are effectively static config
  }, []);

  useEffect(() => {
    showCatchmentsRef.current = showCatchments;
    const map = mapRef.current;
    if (!map || !showCatchments) return;
    loadCatchmentsInView(map, setError);
  }, [showCatchments]);

  function handleShowCatchmentsChange(checked: boolean) {
    setShowCatchments(checked);
    if (checked) return;
    setSelectedCatchment(null);
    const source = mapRef.current?.getSource("catchments") as
      GeoJSONSource | undefined;
    source?.setData({ type: "FeatureCollection", features: [] });
  }

  return (
    <div className="flex flex-col gap-2">
      <label className="flex w-fit items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={showCatchments}
          onChange={(event) => handleShowCatchmentsChange(event.target.checked)}
        />
        Show catchment areas (Sheffield, Aberdeen City pilots only)
      </label>
      <div
        ref={containerRef}
        className="border-border h-[70vh] w-full rounded-lg border"
      />
      {error && <p className="text-destructive text-sm">{error}</p>}
      {selectedCatchment && (
        <div className="border-border rounded-md border p-3 text-sm">
          <p className="font-medium">{selectedCatchment.areaName}</p>
          <p className="text-muted-foreground">
            {selectedCatchment.areaType} &middot;{" "}
            {selectedCatchment.academicYear}
          </p>
          <p className="text-muted-foreground mt-1 text-xs">
            Illustrative only: catchment boundaries are not a legal guarantee of
            a school place. Check the local authority&apos;s own admissions page
            before relying on this.
          </p>
        </div>
      )}
      {selected && (
        <div className="border-border rounded-md border p-3 text-sm">
          <Link
            href={`/schools/${selected.urn}`}
            className="text-primary font-medium underline underline-offset-2"
          >
            {selected.schoolName}
          </Link>
          <p className="text-muted-foreground">
            {selected.phaseName} &middot; {selected.status} &middot;{" "}
            {formatNation(selected.nation)}
          </p>
          {selected.sourceExtractDate && (
            <p className="text-muted-foreground mt-1 text-xs">
              Not live data: source dated{" "}
              {new Date(selected.sourceExtractDate).toLocaleDateString(
                "en-GB",
                { day: "numeric", month: "long", year: "numeric" },
              )}
              .
            </p>
          )}
        </div>
      )}
    </div>
  );
}

async function loadSchoolsInView(
  map: MapLibreMap,
  setError: (message: string | null) => void,
) {
  const bounds = map.getBounds();
  const bbox = [
    bounds.getWest(),
    bounds.getSouth(),
    bounds.getEast(),
    bounds.getNorth(),
  ].join(",");

  try {
    const response = await fetch(
      `/api/map/schools?bbox=${encodeURIComponent(bbox)}`,
    );
    if (!response.ok) {
      setError("Could not load schools for this area.");
      return;
    }
    const featureCollection = await response.json();
    const source = map.getSource("schools") as GeoJSONSource | undefined;
    source?.setData(featureCollection);
    setError(null);
  } catch {
    setError("Could not load schools for this area.");
  }
}

async function loadCatchmentsInView(
  map: MapLibreMap,
  setError: (message: string | null) => void,
) {
  const bounds = map.getBounds();
  const bbox = [
    bounds.getWest(),
    bounds.getSouth(),
    bounds.getEast(),
    bounds.getNorth(),
  ].join(",");

  try {
    const response = await fetch(
      `/api/map/catchments?bbox=${encodeURIComponent(bbox)}`,
    );
    if (!response.ok) {
      setError("Could not load catchment areas for this area.");
      return;
    }
    const featureCollection = await response.json();
    const source = map.getSource("catchments") as GeoJSONSource | undefined;
    source?.setData(featureCollection);
    setError(null);
  } catch {
    setError("Could not load catchment areas for this area.");
  }
}
