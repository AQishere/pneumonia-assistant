"use client";

import { AlertTriangle, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Avatar, ErrorState, PageHeader, PageSkeleton } from "@/components/app-shell";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { BAND_INFO } from "@/lib/bands";
import type { AssessmentRow, PatientStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Row {
  id: string;
  name: string;
  status: PatientStatus;
  latest: AssessmentRow | null;
}

export default function DoctorHome() {
  const { me } = useAuth();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const { patients } = await api.patients();
        const loaded = await Promise.all(
          patients.map(async (p) => {
            const [status, a] = await Promise.all([api.status(p.patient_id), api.assessments(p.patient_id, 1)]);
            return { id: p.patient_id, name: p.display_name, status, latest: a.assessments[0] ?? null };
          }),
        );
        // Patients with critical readings first.
        loaded.sort((x, y) => Number(y.status.alerts.length > 0) - Number(x.status.alerts.length > 0));
        setRows(loaded);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load patients.");
      }
    })();
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!rows) return <PageSkeleton />;

  return (
    <>
      <PageHeader title="My patients" />
      {rows.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No linked patients yet</CardTitle>
            <CardDescription>
              Patients can link you from their profile using your sign-in email ({me?.email}).
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <ul className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {rows.map((r, i) => {
            const band = r.latest?.band;
            return (
              <li key={r.id} className="animate-rise" style={{ animationDelay: `${i * 40}ms` }}>
                <Link
                  href={`/doctor/${r.id}`}
                  className="flex items-center gap-4 rounded-2xl surface p-4 transition-colors duration-200 hover:border-ring/50"
                >
                  <Avatar name={r.name} className="size-12 text-base" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[15px] font-semibold">{r.name}</p>
                    <p className="mt-0.5 flex items-center gap-1.5 text-[15px] text-foreground/75">
                      <span className={cn("size-2.5 rounded-full", band ? BAND_INFO[band].dot : "bg-muted")} aria-hidden />
                      {band ? BAND_INFO[band].label : "No checks yet"}
                    </p>
                    {r.latest && (
                      <p className="text-[13px] text-foreground/70">{new Date(r.latest.created_at).toLocaleDateString()}</p>
                    )}
                  </div>
                  {r.status.alerts.length > 0 && (
                    <span className="flex items-center gap-1 rounded-full bg-destructive/10 px-2.5 py-1 text-[13px] font-semibold text-destructive">
                      <AlertTriangle className="size-3.5" /> Critical
                    </span>
                  )}
                  <ChevronRight className="size-5 text-muted-foreground" />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
