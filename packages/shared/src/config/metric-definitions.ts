import { z } from "zod";
import raw from "../generated/metric-definitions.json";

// Mirrors the shape of config/metric-definitions.yml. Validated once at
// module load so a malformed config file fails loudly (build/test time)
// rather than silently rendering an incomplete UI.
const MetricDefinitionSchema = z.object({
  label: z.string(),
  description: z.string(),
  denominator: z.string(),
  unit: z.string(),
  phases: z.array(z.string()),
  comparability_notes: z.string(),
});

const MetricDefinitionsFileSchema = z.object({
  metrics: z.record(z.string(), MetricDefinitionSchema),
});

export type MetricDefinition = z.infer<typeof MetricDefinitionSchema> & {
  code: string;
};

const parsed = MetricDefinitionsFileSchema.parse(raw);

const definitionsByCode: Record<string, MetricDefinition> = Object.fromEntries(
  Object.entries(parsed.metrics).map(([code, def]) => [code, { code, ...def }]),
);

/** All known metric codes, in config file order. */
export const METRIC_CODES = Object.keys(definitionsByCode);

/** Looks up a metric's definition. Returns null for an unrecognised code
 * rather than throwing, since metric codes ultimately come from the
 * database and the config file is versioned independently. Callers should
 * treat a null result as "do not render this figure without a definition". */
export function getMetricDefinition(code: string): MetricDefinition | null {
  return definitionsByCode[code] ?? null;
}

/** Every configured metric definition, for the /about/data methodology page. */
export function listMetricDefinitions(): MetricDefinition[] {
  return Object.values(definitionsByCode);
}
