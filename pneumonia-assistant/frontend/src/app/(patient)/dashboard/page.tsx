"use client";

import { MessageCircle } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ErrorState, PageHeader, PageSkeleton, SectionTitle } from "@/components/app-shell";
import { LabsCard } from "@/components/labs-card";
import { QuickCheck } from "@/components/quick-check";
import { ReadingTiles } from "@/components/reading-tiles";
import { CriticalAlerts, StatusCard } from "@/components/status-card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { AssessResult, AssessmentRow, PatientStatus, Reading } from "@/lib/types";

const today = () => new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });

export default function DashboardPage() {
  const { me } = useAuth();
  const id = me!.uid!;
  const [status, setStatus] = useState<PatientStatus | null>(null);
  const [readings, setReadings] = useState<Reading[] | undefined>();
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
    // Trend lines are a nice-to-have: the widgets still show without them.
    api.readings(id, 2).then((r) => setReadings(r.readings)).catch(() => {});
  }, [id, reloads]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!status) return <PageSkeleton />;

  // Alerts come from the live readings, so they show even before any check is run.
  const alerts = result?.alerts ?? status.alerts;
  const notice = result?.critical_notice ?? status.critical_notice;

  return (
    <>
      <PageHeader eyebrow={today()} title={`Hello, ${status.display_name.split(" ")[0]}`}>
        <Button asChild variant="outline">
          <Link href="/chat">
            <MessageCircle className="size-4" /> Ask the assistant
          </Link>
        </Button>
      </PageHeader>

      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_340px] 2xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 space-y-8">
          <section>
            <SectionTitle
              action={
                <Link href="/history" className="text-[15px] text-primary hover:underline">
                  Show all
                </Link>
              }
            >
              Latest Readings
            </SectionTitle>
            <ReadingTiles status={status} readings={readings} historyHref="/history" />
          </section>
          <div id="result" className="space-y-5">
            <CriticalAlerts notice={notice} alerts={alerts} />
            <StatusCard
              result={result}
              band={latest?.band}
              at={result ? undefined : latest?.created_at}
              alertActive={alerts.length > 0}
            />
          </div>
        </div>

        <div id="check" className="grid scroll-mt-8 content-start gap-8 md:grid-cols-2 xl:grid-cols-1">
          <QuickCheck
            patientId={id}
            onResult={(r) => {
              setResult(r);
              load();
              document.getElementById("result")?.scrollIntoView({ behavior: "smooth", block: "center" });
            }}
          />
          <LabsCard patientId={id} onSaved={load} />
        </div>
      </div>
    </>
  );
}
