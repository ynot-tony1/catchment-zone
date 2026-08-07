import type { Metadata } from "next";
import { SchoolMap } from "@/components/school-map";
import { getPublicEnv } from "@/lib/env";

export const metadata: Metadata = {
  title: "Map",
};

export default function MapPage() {
  const { mapStyleUrl, mapAttribution } = getPublicEnv();

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Map</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Catchment areas in view are loaded as you pan and zoom, coloured by
          performance where a score is available. Select a catchment for
          details, or turn on individual school pins to see and select schools
          directly.
        </p>
      </div>
      <SchoolMap styleUrl={mapStyleUrl} attribution={mapAttribution} />
    </div>
  );
}
