import { z } from "zod";
import raw from "../generated/statistics-sources.json";

// Mirrors config/statistics-sources.yml. Used by the /about/data page to
// list where each metric comes from without hardcoding prose that could
// drift from the actual ingestion config.
const PublicationSchema = z.object({
  publication_slug: z.string(),
  display_name: z.string(),
  metric_codes: z.array(z.string()),
  update_frequency: z.string(),
  applies_to_phases: z.array(z.string()),
  notes: z.string().optional(),
});

const StatisticsSourcesFileSchema = z.object({
  api: z.object({
    base_url: z.string(),
    docs_url: z.string(),
  }),
  publications: z.array(PublicationSchema),
});

export type Publication = z.infer<typeof PublicationSchema>;

const parsed = StatisticsSourcesFileSchema.parse(raw);

export function listPublications(): Publication[] {
  return parsed.publications;
}

export function getStatisticsApiInfo(): { base_url: string; docs_url: string } {
  return parsed.api;
}

/** Publications that supply a given metric code, for cross-referencing on
 * the school detail page ("where does this figure come from"). */
export function findPublicationsForMetric(metricCode: string): Publication[] {
  return parsed.publications.filter((p) => p.metric_codes.includes(metricCode));
}
