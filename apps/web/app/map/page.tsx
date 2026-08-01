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
          Schools currently in view are loaded as you pan and zoom. Select a
          school for details.
        </p>
      </div>
      <SchoolMap styleUrl={mapStyleUrl} attribution={mapAttribution} />
    </div>
  );
}
