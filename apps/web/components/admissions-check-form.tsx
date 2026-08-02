"use client";

import { useState } from "react";
import type { CatchmentCheckResult } from "@catchment-zone/shared";
import Link from "next/link";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const STATUS_LABEL: Record<CatchmentCheckResult["status"], string> = {
  INSIDE_OFFICIAL_PRIORITY_AREA: "Inside the published priority area",
  OUTSIDE_OFFICIAL_PRIORITY_AREA: "Outside the published priority area",
  NO_FIXED_CATCHMENT_USED:
    "This admission authority does not use a fixed catchment",
  OFFICIAL_BOUNDARY_NOT_AVAILABLE:
    "No official catchment boundary is available for this area",
  POSTCODE_RESULT_NEAR_BOUNDARY:
    "Too close to the boundary for a reliable postcode-level result",
  ACADEMIC_YEAR_NOT_AVAILABLE:
    "No catchment data is available for the selected academic year",
};

const STATUS_VARIANT: Record<
  CatchmentCheckResult["status"],
  "success" | "warning" | "secondary"
> = {
  INSIDE_OFFICIAL_PRIORITY_AREA: "success",
  OUTSIDE_OFFICIAL_PRIORITY_AREA: "secondary",
  NO_FIXED_CATCHMENT_USED: "secondary",
  OFFICIAL_BOUNDARY_NOT_AVAILABLE: "secondary",
  POSTCODE_RESULT_NEAR_BOUNDARY: "warning",
  ACADEMIC_YEAR_NOT_AVAILABLE: "secondary",
};

type FormState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; result: CatchmentCheckResult };

export function AdmissionsCheckForm() {
  const [postcode, setPostcode] = useState("");
  const [phase, setPhase] = useState<"primary" | "secondary">("primary");
  const [state, setState] = useState<FormState>({ status: "idle" });

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setState({ status: "loading" });
    try {
      const response = await fetch("/api/admissions/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ postcode, phase }),
      });
      const body = await response.json();
      if (!response.ok) {
        setState({
          status: "error",
          message: body.error?.message ?? "Something went wrong.",
        });
        return;
      }
      setState({ status: "success", result: body as CatchmentCheckResult });
    } catch {
      setState({
        status: "error",
        message: "Could not reach the server. Please try again.",
      });
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form
        onSubmit={handleSubmit}
        className="grid gap-4 sm:grid-cols-3 sm:items-end"
      >
        <div>
          <Label htmlFor="postcode">Postcode</Label>
          <Input
            id="postcode"
            name="postcode"
            required
            value={postcode}
            onChange={(event) => setPostcode(event.target.value)}
            placeholder="e.g. S1 2HH"
          />
        </div>
        <div>
          <Label htmlFor="phase">Phase</Label>
          <select
            id="phase"
            name="phase"
            value={phase}
            onChange={(event) =>
              setPhase(event.target.value as "primary" | "secondary")
            }
            className="border-input h-9 w-full rounded-md border bg-transparent px-3 text-sm"
          >
            <option value="primary">Primary</option>
            <option value="secondary">Secondary</option>
          </select>
        </div>
        <Button type="submit" disabled={state.status === "loading"}>
          {state.status === "loading" ? "Checking..." : "Check"}
        </Button>
      </form>

      {state.status === "error" && (
        <Alert variant="destructive">
          <AlertTitle>Could not check this postcode</AlertTitle>
          <AlertDescription>{state.message}</AlertDescription>
        </Alert>
      )}

      {state.status === "success" && (
        <div className="flex flex-col gap-4">
          <Alert
            variant={
              STATUS_VARIANT[state.result.status] === "success"
                ? "success"
                : "default"
            }
          >
            <AlertTitle>
              <Badge variant={STATUS_VARIANT[state.result.status]}>
                {STATUS_LABEL[state.result.status]}
              </Badge>
            </AlertTitle>
            <AlertDescription>
              {state.result.localAuthorityName
                ? `${state.result.localAuthorityName}, ${state.result.academicYear} academic year.`
                : `${state.result.academicYear} academic year.`}
            </AlertDescription>
          </Alert>

          {state.result.nearBoundaryWarning && (
            <Alert variant="warning">
              <AlertTitle>Near the boundary</AlertTitle>
              <AlertDescription>
                {state.result.nearBoundaryWarning}
              </AlertDescription>
            </Alert>
          )}

          {state.result.matchedArea && (
            <div className="text-sm">
              <p className="font-medium">{state.result.matchedArea.areaName}</p>
              {state.result.servedSchools.length > 0 && (
                <ul className="mt-2 list-inside list-disc">
                  {state.result.servedSchools.map((school) => (
                    <li key={school.urn}>
                      <Link
                        href={`/schools/${school.urn}`}
                        className="text-primary underline underline-offset-2"
                      >
                        {school.schoolName}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <Alert>
            <AlertDescription>{state.result.disclaimer}</AlertDescription>
          </Alert>
        </div>
      )}
    </div>
  );
}
