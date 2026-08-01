import { describe, expect, it } from "vitest";
import {
  getMetricDefinition,
  listMetricDefinitions,
  METRIC_CODES,
} from "./metric-definitions";

describe("metric definitions loaded from config/metric-definitions.yml", () => {
  it("loads at least the known baseline metrics", () => {
    expect(METRIC_CODES).toEqual(
      expect.arrayContaining([
        "capacity_total_places",
        "overall_absence_rate",
        "persistent_absence_rate",
        "pupil_teacher_ratio",
        "fsm_eligibility_rate",
      ]),
    );
  });

  it("returns a full definition for a known code", () => {
    const def = getMetricDefinition("overall_absence_rate");
    expect(def).not.toBeNull();
    expect(def?.label).toBe("Overall absence rate");
    expect(def?.unit).toBe("percent");
    expect(def?.comparability_notes.length).toBeGreaterThan(0);
  });

  it("returns null for an unknown metric code rather than throwing", () => {
    expect(getMetricDefinition("does_not_exist")).toBeNull();
  });

  it("every listed definition has a non-empty comparability note", () => {
    for (const def of listMetricDefinitions()) {
      expect(def.comparability_notes.trim().length).toBeGreaterThan(0);
    }
  });
});
