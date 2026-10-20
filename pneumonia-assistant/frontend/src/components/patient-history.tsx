"use client";

import { useEffect, useState } from "react";

import { PageSkeleton } from "@/components/app-shell";
import { BandTimeline, VitalCharts } from "@/components/history-charts";
import { api } from "@/lib/api";
import type { AssessmentRow, Reading } from "@/lib/types";

export function PatientHistory({ patientId }: { patientId: string }) {
  const [rows, setRows] = useState<AssessmentRow[] | null>(null);
  const [readings, setReadings] = useState<Reading[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.assessments(patientId, 60), api.readings(patientId, 7)])
      .then(([a, r]) => {
        setRows(a.assessments);
        setReadings(r.readings);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load history."));
  }, [patientId]);

  if (error) return <p className="text-destructive">{error}</p>;
  if (!rows || !readings) return <PageSkeleton />;
  return (
    <div className="space-y-4">
      <BandTimeline rows={rows} />
      <VitalCharts readings={readings} />
    </div>
  );
}
