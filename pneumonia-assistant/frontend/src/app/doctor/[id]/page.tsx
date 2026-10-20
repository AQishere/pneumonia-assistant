"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { PageSkeleton } from "@/components/app-shell";
import { PatientHistory } from "@/components/patient-history";
import { ReadingTiles } from "@/components/reading-tiles";
import { CriticalAlerts, StatusCard } from "@/components/status-card";
import { api } from "@/lib/api";
import { CONDITION_LABELS, CONDITIONS } from "@/lib/bands";
import type { AssessmentRow, PatientStatus } from "@/lib/types";

/** Read-only view of a linked patient. */
export default function DoctorPatientPage() {
  const { id } = useParams<{ id: string }>();
  const [status, setStatus] = useState<PatientStatus | null>(null);
  const [latest, setLatest] = useState<AssessmentRow | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.status(id), api.assessments(id, 1)])
      .then(([s, a]) => {
        setStatus(s);
        setLatest(a.assessments[0] ?? null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load this patient."));
  }, [id]);

  if (error) return <p className="text-destructive">{error}</p>;
  if (!status) return <PageSkeleton />;

  const conditions = CONDITIONS.filter((c) => status.history_flags[c] === 1).map((c) => CONDITION_LABELS[c]);

  return (
    <div className="space-y-6">
      <Link href="/doctor" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> All patients
      </Link>
      <div>
        <h1 className="text-2xl font-semibold">{status.display_name}</h1>
        <p className="text-sm text-muted-foreground">
          {[status.age && `${status.age} years`, status.sex?.replaceAll("_", " "), conditions.join(", ") || "No long-term conditions"]
            .filter(Boolean)
            .join(" · ")}
        </p>
      </div>
      <CriticalAlerts notice={status.critical_notice} alerts={status.alerts} />
      <StatusCard band={latest?.band} at={latest?.created_at} />
      <ReadingTiles status={status} />
      {status.labs && (
        <p className="text-sm text-muted-foreground">
          Latest labs ({new Date(status.labs.taken_at).toLocaleDateString()}): WBC {status.labs.wbc} ×10⁹/L, neutrophils{" "}
          {status.labs.neutrophils}%, lymphocytes {status.labs.lymphocytes}%, CRP {status.labs.crp} mg/L
        </p>
      )}
      <PatientHistory patientId={id} />
    </div>
  );
}
