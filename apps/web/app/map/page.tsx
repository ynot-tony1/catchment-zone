import type { Metadata } from "next";
import { SchoolMap } from "@/components/school-map";
import { getPublicEnv } from "@/lib/env";
import { getCatchmentsFeatureCollection } from "@/lib/catchments";

export const metadata: Metadata = {
  title: "Map",
};

// Fetches catchment areas server-side and embeds them in the page's
// initial render, rather than having the client fetch them after mount -
// that gap is exactly what made the map look broken/slow to load. This
// reads the same pre-built map_catchments_cache row the API route now
// serves (see lib/catchments.ts), so it's one fast query, not a rebuild
// from ~9,000+ individual catchment_areas rows.
export default async function MapPage() {
  const { mapStyleUrl, mapAttribution } = getPublicEnv();
  const initialCatchments = await getCatchmentsFeatureCollection();

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Map</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Every published catchment area is shown, coloured by performance where
          a score is available. Select a catchment for details, or turn on
          individual school pins to see and select schools directly.
        </p>
      </div>
      <SchoolMap
        styleUrl={mapStyleUrl}
        attribution={mapAttribution}
        initialCatchments={initialCatchments}
      />
    </div>
  );
}
