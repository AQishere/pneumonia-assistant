"use client";

import { MessageCircle } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { PageSkeleton } from "@/components/app-shell";
import { LabsCard } from "@/components/labs-card";
import { QuickCheck } from "@/components/quick-check";
import { ReadingTiles } from "@/components/reading-tiles";
import { CriticalAlerts, StatusCard } from "@/components/status-card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { AssessResult, AssessmentRow, PatientStatus } from "@/lib/types";

export default function DashboardPage() {
  const { me } = useAuth();
  const id = me!.uid!;
  const [status, setStatus] = useState<PatientStatus | null>(null);
  const [latest, setLatest] = useState<AssessmentRow | null>(null);
  const [result, setResult] = useState<AssessResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloads, setReloads] = useState(0);        // bump to refetch after a check or lab upload
  const load = () => setReloads((n) => n + 1);

  useEffect(() => {
    Promise.all([api.status(id), api.assessments(id, 1)])
      .then(([s, a]) => {
        setStatus(s);
        setLatest(a.assessments[0] ?? null);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load your data."));
  }, [id, reloads]);

  if (error) return <p className="text-destructive">{error}</p>;
  if (!status) return <PageSkeleton />;

  // Alerts come from the live readings, so they show even before any check is run.
  const alerts = result?.alerts ?? status.alerts;
  const notice = result?.critical_notice ?? status.critical_notice;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Hello, {status.display_name.split(" ")[0]}</h1>
          <p className="text-sm text-muted-foreground">Here is how your readings look right now.</p>
        </div>
        <Button asChild variant="outline">
          <Link href="/chat">
            <MessageCircle className="size-4" /> Ask the assistant
          </Link>
        </Button>
      </div>

      <CriticalAlerts notice={notice} alerts={alerts} />
      <StatusCard result={result} band={latest?.band} at={result ? undefined : latest?.created_at} />

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted-foreground">Latest device readings</h2>
        <ReadingTiles status={status} />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <QuickCheck
          patientId={id}
          onResult={(r) => {
            setResult(r);
            load();
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
        />
        <LabsCard patientId={id} labs={status.labs} onSaved={load} />
      </div>
    </div>
  );
}
