"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Avatar, ErrorState, PageSkeleton, SectionTitle } from "@/components/app-shell";
import { PatientHistory } from "@/components/patient-history";
import { ReadingTiles } from "@/components/reading-tiles";
import { CriticalAlerts, StatusCard } from "@/components/status-card";
import { api } from "@/lib/api";
import { CONDITION_LABELS, CONDITIONS } from "@/lib/bands";
import type { AssessmentRow, PatientStatus, Reading } from "@/lib/types";

/** Read-only view of a linked patient. */
export default function DoctorPatientPage() {
  const { id } = useParams<{ id: string }>();
  const [status, setStatus] = useState<PatientStatus | null>(null);
  const [latest, setLatest] = useState<AssessmentRow | null>(null);
  const [readings, setReadings] = useState<Reading[] | undefined>();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.status(id), api.assessments(id, 1)])
      .then(([s, a]) => {
        setStatus(s);
        setLatest(a.assessments[0] ?? null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load this patient."));
    api.readings(id, 2).then((r) => setReadings(r.readings)).catch(() => {});
  }, [id]);

  if (error) return <ErrorState message={error} />;
  if (!status) return <PageSkeleton />;

  const conditions = CONDITIONS.filter((c) => status.history_flags[c] === 1).map((c) => CONDITION_LABELS[c]);

  return (
    <div className="space-y-6">
      <Link href="/doctor" className="flex items-center gap-1 text-[15px] text-primary hover:underline">
        <ArrowLeft className="size-4" /> All patients
      </Link>
      <div className="flex items-center gap-4">
        <Avatar name={status.display_name} className="size-16 text-xl" />
        <div>
        <h1 className="text-2xl font-semibold tracking-tight">{status.display_name}</h1>
        <p className="text-[15px] text-muted-foreground">
          {[status.age && `${status.age} years`, status.sex?.replaceAll("_", " "), conditions.join(", ") || "No long-term conditions"]
            .filter(Boolean)
            .join(" · ")}
        </p>
        </div>
      </div>
      <div className="space-y-4">
        <CriticalAlerts notice={status.critical_notice} alerts={status.alerts} />
        <StatusCard band={latest?.band} at={latest?.created_at} alertActive={status.alerts.length > 0} />
      </div>
      <section>
        <SectionTitle>Latest readings</SectionTitle>
        <ReadingTiles status={status} readings={readings} />
      </section>
      <section>
        <SectionTitle>History</SectionTitle>
        <PatientHistory patientId={id} />
      </section>
    </div>
  );
}
