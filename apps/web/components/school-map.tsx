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

// Covers all four UK nations (west coast of Northern Ireland to Shetland
// in the north-east), not just England - schools from all four nations are
// loaded here now.
const UK_BOUNDS: [number, number, number, number] = [-8.7, 49.8, 1.9, 61.0];

export function SchoolMap({
  styleUrl,
  attribution,
}: {
  styleUrl: string;
  attribution: string;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [selected, setSelected] = useState<SchoolFeatureProperties | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new MapLibreMap({
      container: containerRef.current,
      style: styleUrl,
      bounds: UK_BOUNDS,
      attributionControl: { customAttribution: attribution },
    });
    mapRef.current = map;
    map.addControl(new NavigationControl(), "top-right");

    map.on("load", () => {
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
        setSelected(feature.properties as SchoolFeatureProperties);
      });
      map.on("mouseenter", "schools-points", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "schools-points", () => {
        map.getCanvas().style.cursor = "";
      });

      loadSchoolsInView(map, setError);
      map.on("moveend", () => loadSchoolsInView(map, setError));
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- map is created once; styleUrl/attribution are effectively static config
  }, []);

  return (
    <div className="flex flex-col gap-2">
      <div
        ref={containerRef}
        className="border-border h-[70vh] w-full rounded-lg border"
      />
      {error && <p className="text-destructive text-sm">{error}</p>}
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
