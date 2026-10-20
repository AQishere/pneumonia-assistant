"use client";

import { AlertTriangle, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { PageSkeleton } from "@/components/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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

  if (error) return <p className="text-destructive">{error}</p>;
  if (!rows) return <PageSkeleton />;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">My patients</h1>
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
        <ul className="space-y-2">
          {rows.map((r) => {
            const band = r.latest?.band;
            return (
              <li key={r.id}>
                <Link href={`/doctor/${r.id}`}>
                  <Card className="py-0 transition-colors hover:bg-muted/50">
                    <CardContent className="flex items-center gap-3 p-4">
                      <span className={cn("size-3 rounded-full", band ? BAND_INFO[band].dot : "bg-muted")} aria-hidden />
                      <div className="flex-1">
                        <p className="font-medium">{r.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {band ? BAND_INFO[band].label : "No checks yet"}
                          {r.latest && ` · ${new Date(r.latest.created_at).toLocaleDateString()}`}
                        </p>
                      </div>
                      {r.status.alerts.length > 0 && (
                        <span className="flex items-center gap-1 text-sm font-medium text-red-600">
                          <AlertTriangle className="size-4" /> Critical reading
                        </span>
                      )}
                      <ChevronRight className="size-4 text-muted-foreground" />
                    </CardContent>
                  </Card>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
