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
import { getMetricDefinition } from "@catchment-zone/shared";
import { formatNation, formatNumber } from "@/lib/format";

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
  performancePercentile: number | null;
  performanceMetricCode: string | null;
};

// Colours the served school's performance percentile (0 = worst, 1 =
// best) within its own metric's population: green at the top, through
// light red, to dark red at the bottom. Areas with no computed score
// (most of them right now - see refresh-catchment-scores in the
// ingestor for exactly which areas qualify) fall through to a neutral
// colour outline/fill instead of implying an unearned grade. Deliberately
// a saturated blue-grey rather than a plain grey: catchment coverage is
// still sparse (a couple dozen local authorities out of 200+), and most
// of those areas are unscored (only England and Wales have performance
// metrics right now), so a low-contrast grey against a similarly-toned
// basemap made the whole feature look broken - toggling it on produced
// no perceptible change unless you happened to already be zoomed into a
// covered area.
const UNSCORED_CATCHMENT_COLOR = "#4263eb";

// Individual catchment polygons (typically a few km across) are visually
// imperceptible at the initial full-GB zoom (around 5) even when real data
// is loaded and coloured - there just aren't enough pixels per polygon.
// Below this zoom, the "no data in this view" hint is shown regardless of
// how many features actually came back, since a non-zero count doesn't
// mean anything is visible to the user.
const CATCHMENT_VISIBLE_ZOOM_THRESHOLD = 9;

// Covers Great Britain (England, Scotland and Wales) - west to Scotland's
// Outer Hebrides, north to Shetland - not just England. Northern Ireland
// is deliberately excluded from this project (see PROJECT_STATUS.md).
const GB_BOUNDS: [number, number, number, number] = [-8.7, 49.8, 1.9, 61.0];

// Coalesces bursts of "moveend" events (a mouse-wheel zoom or a drag-pan
// fires several in quick succession) into a single fetch after the user
// actually stops moving, instead of firing one full schools+catchments
// round-trip per intermediate event - verified live this was the main
// cause of the map feeling slow and of school pins visibly "jumping"
// between positions (see the request-sequence guards in loadSchoolsInView/
// loadCatchmentsInView below for the other half of that fix: even with
// debouncing, a slow request for an earlier viewport can still resolve
// after a faster request for a later one, so both also drop any response
// that isn't for the most recent request they themselves issued).
const MOVE_DEBOUNCE_MS = 300;

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
  const onlyCatchmentsRef = useRef(false);
  const moveDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const schoolsRequestIdRef = useRef(0);
  const catchmentsRequestIdRef = useRef(0);
  const [selected, setSelected] = useState<SchoolFeatureProperties | null>(
    null,
  );
  const [selectedCatchment, setSelectedCatchment] =
    useState<CatchmentFeatureProperties | null>(null);
  const [showCatchments, setShowCatchments] = useState(false);
  const [onlyCatchments, setOnlyCatchments] = useState(false);
  const [catchmentCountInView, setCatchmentCountInView] = useState<
    number | null
  >(null);
  const [zoom, setZoom] = useState<number | null>(null);
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
          "fill-color": [
            "case",
            ["!=", ["get", "performancePercentile"], null],
            [
              "interpolate",
              ["linear"],
              ["get", "performancePercentile"],
              0,
              "#9c1c1c",
              0.5,
              "#ff8787",
              1,
              "#2f9e44",
            ],
            UNSCORED_CATCHMENT_COLOR,
          ],
          "fill-opacity": 0.55,
        },
      });
      map.addLayer({
        id: "catchments-outline",
        type: "line",
        source: "catchments",
        paint: {
          "line-color": [
            "case",
            ["!=", ["get", "performancePercentile"], null],
            [
              "interpolate",
              ["linear"],
              ["get", "performancePercentile"],
              0,
              "#9c1c1c",
              0.5,
              "#ff8787",
              1,
              "#2f9e44",
            ],
            UNSCORED_CATCHMENT_COLOR,
          ],
          "line-width": 2,
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
        layout: { visibility: onlyCatchmentsRef.current ? "none" : "visible" },
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

      function loadCurrentView() {
        if (!onlyCatchmentsRef.current) {
          loadSchoolsInView(map, schoolsRequestIdRef, setError);
        }
        if (showCatchmentsRef.current) {
          loadCatchmentsInView(
            map,
            catchmentsRequestIdRef,
            setError,
            setCatchmentCountInView,
          );
        }
      }

      loadCurrentView();
      setZoom(map.getZoom());
      map.on("moveend", () => {
        setZoom(map.getZoom());
        if (moveDebounceRef.current) clearTimeout(moveDebounceRef.current);
        moveDebounceRef.current = setTimeout(loadCurrentView, MOVE_DEBOUNCE_MS);
      });
    });

    return () => {
      if (moveDebounceRef.current) clearTimeout(moveDebounceRef.current);
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- map is created once; styleUrl/attribution are effectively static config
  }, []);

  useEffect(() => {
    showCatchmentsRef.current = showCatchments;
    const map = mapRef.current;
    if (!map || !showCatchments) return;
    loadCatchmentsInView(
      map,
      catchmentsRequestIdRef,
      setError,
      setCatchmentCountInView,
    );
  }, [showCatchments]);

  function handleOnlyCatchmentsChange(checked: boolean) {
    onlyCatchmentsRef.current = checked;
    setOnlyCatchments(checked);
    const map = mapRef.current;
    if (!map || !map.getLayer("schools-points")) return;
    map.setLayoutProperty(
      "schools-points",
      "visibility",
      checked ? "none" : "visible",
    );
    if (checked) {
      setSelected(null);
    } else {
      loadSchoolsInView(map, schoolsRequestIdRef, setError);
    }
  }

  function handleShowCatchmentsChange(checked: boolean) {
    setShowCatchments(checked);
    setCatchmentCountInView(null);
    if (checked) return;
    setSelectedCatchment(null);
    if (onlyCatchments) handleOnlyCatchmentsChange(false);
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
        Show catchment areas (where published)
      </label>
      {showCatchments && (
        <label className="flex w-fit items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={onlyCatchments}
            onChange={(event) =>
              handleOnlyCatchmentsChange(event.target.checked)
            }
          />
          Show only catchment zones (hide school pins, faster on slower
          connections)
        </label>
      )}
      {showCatchments && (
        <div className="flex w-fit items-center gap-2 text-xs">
          <span className="text-muted-foreground">Performance grade:</span>
          <span
            className="h-3 w-16 rounded-sm"
            style={{
              background:
                "linear-gradient(to right, #9c1c1c, #ff8787, #2f9e44)",
            }}
          />
          <span className="text-muted-foreground">worst to best</span>
          <span
            className="ml-2 h-3 w-3 rounded-sm"
            style={{ background: UNSCORED_CATCHMENT_COLOR }}
          />
          <span className="text-muted-foreground">no data</span>
        </div>
      )}
      {showCatchments &&
        zoom !== null &&
        zoom < CATCHMENT_VISIBLE_ZOOM_THRESHOLD && (
          <p className="text-muted-foreground text-xs">
            Catchment area boundaries are too small to see at this zoom level -
            zoom in to a covered area (try Sheffield, several Scottish council
            areas, or Powys and Pembrokeshire in Wales) to see them, or check
            the{" "}
            <Link
              href="/local-authorities"
              className="text-primary underline underline-offset-2"
            >
              local authorities page
            </Link>{" "}
            for the full coverage list.
          </p>
        )}
      {showCatchments &&
        zoom !== null &&
        zoom >= CATCHMENT_VISIBLE_ZOOM_THRESHOLD &&
        catchmentCountInView === 0 && (
          <p className="text-muted-foreground text-xs">
            No catchment areas are published for this area. See the{" "}
            <Link
              href="/local-authorities"
              className="text-primary underline underline-offset-2"
            >
              local authorities page
            </Link>{" "}
            for the full coverage list.
          </p>
        )}
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
          {selectedCatchment.performancePercentile !== null && (
            <p className="mt-1">
              Performance grade:{" "}
              <span className="font-medium">
                {formatNumber(selectedCatchment.performancePercentile * 100, 0)}
                th percentile
              </span>{" "}
              <span className="text-muted-foreground">
                on{" "}
                {selectedCatchment.performanceMetricCode
                  ? (getMetricDefinition(
                      selectedCatchment.performanceMetricCode,
                    )?.label ?? selectedCatchment.performanceMetricCode)
                  : "an unknown metric"}
                , among schools with that same measure.
              </span>
            </p>
          )}
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
  requestIdRef: { current: number },
  setError: (message: string | null) => void,
) {
  const bounds = map.getBounds();
  const bbox = [
    bounds.getWest(),
    bounds.getSouth(),
    bounds.getEast(),
    bounds.getNorth(),
  ].join(",");
  const requestId = ++requestIdRef.current;

  try {
    const response = await fetch(
      `/api/map/schools?bbox=${encodeURIComponent(bbox)}`,
    );
    // A slower request for an earlier viewport can resolve after a faster
    // one for a later viewport (the map may have moved again in between,
    // debounced or not) - applying it now would flash stale pins into the
    // wrong positions, which is what "dancing" pins actually was.
    if (requestIdRef.current !== requestId) return;
    if (!response.ok) {
      setError("Could not load schools for this area.");
      return;
    }
    const featureCollection = await response.json();
    if (requestIdRef.current !== requestId) return;
    const source = map.getSource("schools") as GeoJSONSource | undefined;
    source?.setData(featureCollection);
    setError(null);
  } catch {
    if (requestIdRef.current === requestId) {
      setError("Could not load schools for this area.");
    }
  }
}

async function loadCatchmentsInView(
  map: MapLibreMap,
  requestIdRef: { current: number },
  setError: (message: string | null) => void,
  setCatchmentCountInView: (count: number | null) => void,
) {
  const bounds = map.getBounds();
  const bbox = [
    bounds.getWest(),
    bounds.getSouth(),
    bounds.getEast(),
    bounds.getNorth(),
  ].join(",");
  const requestId = ++requestIdRef.current;

  try {
    const response = await fetch(
      `/api/map/catchments?bbox=${encodeURIComponent(bbox)}`,
    );
    if (requestIdRef.current !== requestId) return;
    if (!response.ok) {
      setError("Could not load catchment areas for this area.");
      return;
    }
    const featureCollection = await response.json();
    if (requestIdRef.current !== requestId) return;
    const source = map.getSource("catchments") as GeoJSONSource | undefined;
    source?.setData(featureCollection);
    setCatchmentCountInView(featureCollection.features?.length ?? 0);
    setError(null);
  } catch {
    if (requestIdRef.current === requestId) {
      setError("Could not load catchment areas for this area.");
    }
  }
}
