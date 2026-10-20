"use client";

import { FlaskConical } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { CriticalAlerts, StatusCard } from "@/components/status-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { YesNo } from "@/components/yes-no";
import { api } from "@/lib/api";
import { BAND_INFO, CONDITION_LABELS, CONDITIONS, VITAL_INFO, VITALS } from "@/lib/bands";
import type { Condition, DemoInput, DemoResult, Sex, Vital } from "@/lib/types";
import { cn } from "@/lib/utils";

type Answer = "respiratory_distress" | "hypoxemia" | "cough" | "fever" | "weakness";
type LabKey = "wbc" | "neutrophils" | "lymphocytes" | "crp";

const ANSWERS: { key: Answer; label: string }[] = [
  { key: "respiratory_distress", label: "Short of breath, even when resting?" },
  { key: "hypoxemia", label: "Known low blood oxygen in the past week?" },
  { key: "cough", label: "Cough? (recorded, not used by the model)" },
  { key: "fever", label: "Feels feverish? (recorded, not used by the model)" },
  { key: "weakness", label: "Unusually weak or tired?" },
];

const LABS: { key: LabKey; label: string; unit: string }[] = [
  { key: "wbc", label: "WBC", unit: "×10⁹/L" },
  { key: "neutrophils", label: "Neutrophils", unit: "%" },
  { key: "lymphocytes", label: "Lymphocytes", unit: "%" },
  { key: "crp", label: "CRP", unit: "mg/L" },
];

interface Form {
  age: string;
  sex: Sex;
  conditions: Record<Condition, 0 | 1>;
  answers: Record<Answer, 0 | 1>;
  vitals: Record<Vital, string>;
  labs: Record<LabKey, string>;
}

const NO_CONDITIONS = Object.fromEntries(CONDITIONS.map((c) => [c, 0])) as Record<Condition, 0 | 1>;

// Example patients, the same ones the backend tests use.
const PRESETS: Record<string, Form> = {
  Healthy: {
    age: "45",
    sex: "female",
    conditions: NO_CONDITIONS,
    answers: { respiratory_distress: 0, hypoxemia: 0, cough: 0, fever: 0, weakness: 0 },
    vitals: {
      heart_rate: "72, 78, 75, 80",
      respiratory_rate: "14, 16, 15, 17",
      sbp: "125, 130, 122, 128",
      spo2: "98, 97, 99, 98",
      temperature: "98.2, 98.6, 98.4, 98.5",
    },
    labs: { wbc: "7", neutrophils: "60", lymphocytes: "30", crp: "3" },
  },
  "Pneumonia-like": {
    age: "72",
    sex: "male",
    conditions: { ...NO_CONDITIONS, copd: 1 },
    answers: { respiratory_distress: 1, hypoxemia: 1, cough: 1, fever: 1, weakness: 1 },
    vitals: {
      heart_rate: "105, 118, 124, 112",
      respiratory_rate: "26, 32, 35, 30",
      sbp: "100, 92, 88, 95",
      spo2: "91, 87, 85, 89",
      temperature: "100.2, 101.8, 102.4, 101.0",
    },
    labs: { wbc: "15.2", neutrophils: "86", lymphocytes: "7", crp: "140" },
  },
};

function parseValues(text: string): number[] | null {
  const parts = text.split(/[,\s]+/).filter(Boolean);
  const nums = parts.map(Number);
  return nums.some((n) => Number.isNaN(n)) ? null : nums;
}

function Score({ label, p, threshold }: { label: string; p: number | null; threshold: number }) {
  const flagged = p !== null && p >= threshold;
  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      {p === null ? (
        <p className="mt-1 text-sm">Did not run</p>
      ) : (
        <>
          <p className={cn("mt-1 text-2xl font-semibold", flagged ? "text-red-600" : "text-emerald-600")}>
            {p.toFixed(3)}
          </p>
          <p className="text-xs text-muted-foreground">
            threshold {threshold} · {flagged ? "flagged" : "not flagged"}
          </p>
        </>
      )}
    </div>
  );
}

/** Demo page only: a Low band next to a critical alert. The shared StatusCard's "no concern" wording would
 *  contradict the alert, so this card replaces it here; the patient dashboard is unchanged. */
function LowWithAlertCard({ disclaimer }: { disclaimer: string }) {
  return (
    <div className={cn("rounded-xl border p-5", BAND_INFO.Low.tone)}>
      <div className="flex items-center gap-2">
        <span className={cn("size-3 rounded-full", BAND_INFO.Low.dot)} aria-hidden />
        <h2 className="text-lg font-semibold">Low pneumonia probability — see critical vital sign alert above.</h2>
      </div>
      <p className="mt-3 text-xs opacity-75">{disclaimer}</p>
    </div>
  );
}

const ZONES = {
  green: { label: "Green: low risk", text: "Pneumonia unlikely on these numbers.", tone: "border-emerald-300 bg-emerald-50 dark:bg-emerald-950" },
  amber: {
    label: "Amber: uncertain",
    text: "Too close to call from vitals and labs. A chest X-ray would decide.",
    tone: "border-amber-300 bg-amber-50 dark:bg-amber-950",
  },
  red: { label: "Red: high risk", text: "Pneumonia likely on these numbers.", tone: "border-red-300 bg-red-50 dark:bg-red-950" },
};

const BAR_FILL = { green: "bg-emerald-500", amber: "bg-amber-500", red: "bg-red-600" };

/** The Stage 2 risk score as a filled bar, coloured by its zone, with the amber zone marked on the track. */
function RiskBar({ demo }: { demo: DemoResult["demo"] }) {
  const { pneumonia_percentage: pct, risk_zone: zone, amber_zone: amber } = demo;
  if (pct === null || zone === null) {
    return (
      <p className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
        No Stage 2 percentage: Stage 2 inputs are missing (it needs labs and at least two readings per vital).
      </p>
    );
  }
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium">Stage 2 risk score</span>
        <span className="font-mono font-semibold">{pct}%</span>
      </div>
      {demo.stage2_shadow && (
        <p className="text-xs text-muted-foreground">
          For reference only: Stage 1 cleared this patient, so in the app Stage 2 would not run and this score does
          not change the result above.
        </p>
      )}
      <div
        className="relative h-3 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Stage 2 risk score ${pct}%, ${zone} zone`}
      >
        <div
          className="absolute inset-y-0 border-x border-amber-500/60 bg-amber-500/15"
          style={{ left: `${amber[0] * 100}%`, width: `${(amber[1] - amber[0]) * 100}%` }}
          aria-hidden
        />
        <div className={cn("relative h-full rounded-full transition-all", BAR_FILL[zone])} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-xs text-muted-foreground">
        A model score, not a calibrated probability. Shaded band: amber zone ({Math.round(amber[0] * 100)}–{Math.round(amber[1] * 100)}%).
      </p>
    </div>
  );
}

/** Green / amber / red for the Stage 2 score, as decided by the server. */
function Zone({ zone, amber }: { zone: DemoResult["demo"]["risk_zone"]; amber: [number, number] }) {
  if (zone === null) return null;
  const z = ZONES[zone];
  return (
    <div className={cn("rounded-lg border p-3", z.tone)}>
      <p className="text-sm font-semibold">{z.label}</p>
      <p className="text-sm">{z.text}</p>
      <p className="mt-1 text-xs text-muted-foreground">
        Green below {amber[0]} · amber {amber[0]} to {amber[1]} · red above {amber[1]}
      </p>
    </div>
  );
}

function FeatureTable({ title, features }: { title: string; features: Record<string, number> | null }) {
  if (!features) return null;
  return (
    <details className="rounded-lg border p-3">
      <summary className="cursor-pointer text-sm font-medium">
        {title} ({Object.keys(features).length} features)
      </summary>
      <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 text-xs sm:grid-cols-2">
        {Object.entries(features).map(([k, v]) => (
          <div key={k} className="flex justify-between gap-2 border-b py-0.5">
            <dt className="text-muted-foreground">{k}</dt>
            <dd className="font-mono">{Number.isInteger(v) ? v : v.toFixed(2)}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

/** Enter a made-up patient by hand and run the live models on it. Nothing is saved. */
export default function DemoPage() {
  const [form, setForm] = useState<Form>(PRESETS.Healthy);
  const [result, setResult] = useState<DemoResult | null>(null);
  const [busy, setBusy] = useState(false);

  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm((f) => ({ ...f, [key]: value }));
  const labsBlank = LABS.every((l) => form.labs[l.key].trim() === "");

  async function run() {
    const readings: DemoInput["readings"] = {};
    for (const v of VITALS) {
      if (form.vitals[v].trim() === "") continue;
      const values = parseValues(form.vitals[v]);
      if (!values) return toast.error(`${VITAL_INFO[v].label}: enter numbers separated by commas.`);
      readings[v] = values;
    }
    const labs = labsBlank ? null : Object.fromEntries(LABS.map((l) => [l.key, Number(form.labs[l.key])]));
    if (labs && Object.values(labs).some((n) => Number.isNaN(n))) {
      return toast.error("Lab results must be numbers (or leave all four empty).");
    }
    setBusy(true);
    try {
      setResult(
        await api.demoRun({
          readings,
          age: Number(form.age),
          sex: form.sex,
          ...form.conditions,
          ...form.answers,
          labs: labs as DemoInput["labs"],
        }),
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "The demo could not run.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          <FlaskConical className="size-6" aria-hidden /> Demo Test
        </h1>
      </div>

      <div className="flex flex-wrap gap-2">
        <span className="self-center text-sm text-muted-foreground">Fill with:</span>
        {Object.keys(PRESETS).map((name) => (
          <Button key={name} variant="outline" size="sm" onClick={() => setForm(PRESETS[name])}>
            {name}
          </Button>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Vital signs</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {VITALS.map((v) => (
                <div key={v} className="space-y-1.5">
                  <Label htmlFor={`v-${v}`} className="text-xs">
                    {VITAL_INFO[v].label} <span className="text-muted-foreground">({VITAL_INFO[v].unit})</span>
                  </Label>
                  <Input
                    id={`v-${v}`}
                    value={form.vitals[v]}
                    onChange={(e) => set("vitals", { ...form.vitals, [v]: e.target.value })}
                  />
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Lab results</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              {LABS.map((l) => (
                <div key={l.key} className="space-y-1.5">
                  <Label htmlFor={`l-${l.key}`} className="text-xs">
                    {l.label} <span className="text-muted-foreground">({l.unit})</span>
                  </Label>
                  <Input
                    id={`l-${l.key}`}
                    inputMode="decimal"
                    value={form.labs[l.key]}
                    onChange={(e) => set("labs", { ...form.labs, [l.key]: e.target.value })}
                  />
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Patient</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="age">Age</Label>
                  <Input id="age" inputMode="numeric" value={form.age} onChange={(e) => set("age", e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="sex">Sex</Label>
                  <Select value={form.sex} onValueChange={(v) => set("sex", v as Sex)}>
                    <SelectTrigger id="sex" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="female">Female</SelectItem>
                      <SelectItem value="male">Male</SelectItem>
                      <SelectItem value="other">Other</SelectItem>
                      <SelectItem value="prefer_not_to_say">Prefer not to say</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              {CONDITIONS.map((c) => (
                <YesNo
                  key={c}
                  id={`c-${c}`}
                  label={CONDITION_LABELS[c]}
                  value={form.conditions[c]}
                  onChange={(v) => set("conditions", { ...form.conditions, [c]: v })}
                />
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Today&apos;s answers</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {ANSWERS.map((q) => (
                <YesNo
                  key={q.key}
                  id={`a-${q.key}`}
                  label={q.label}
                  value={form.answers[q.key]}
                  onChange={(v) => set("answers", { ...form.answers, [q.key]: v })}
                />
              ))}
            </CardContent>
          </Card>
        </div>
      </div>

      <Button className="w-full" size="lg" disabled={busy} onClick={run}>
        {busy ? "Running…" : "Run the models"}
      </Button>

      {result && (
        <div className="space-y-4">
          <CriticalAlerts notice={result.critical_notice} alerts={result.alerts} />
          {result.band === "Low" && result.alerts.length > 0 ? (
            <LowWithAlertCard disclaimer={result.disclaimer} />
          ) : (
            <StatusCard result={result} />
          )}
          <Card>
            <CardHeader>
              <CardTitle>Model details</CardTitle>
              <CardDescription>
                Raw risk scores (not probabilities). Stage 2 only runs when Stage 1 flags the patient. A first positive
                Stage 2 result below 0.70 shows as &quot;re-checking&quot; until a repeat confirms it.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <Score label="Stage 1 (nurse)" p={result.demo.p_stage1} threshold={result.demo.threshold_stage1} />
                <Score
                  label={result.demo.stage2_shadow ? "Stage 2 (doctor), reference only" : "Stage 2 (doctor)"}
                  p={result.demo.p_stage2}
                  threshold={result.demo.threshold_stage2}
                />
              </div>
              <RiskBar demo={result.demo} />
              <Zone zone={result.demo.risk_zone} amber={result.demo.amber_zone} />
              <FeatureTable title="Stage 1 inputs" features={result.demo.features_stage1} />
              <FeatureTable title="Stage 2 inputs" features={result.demo.features_stage2} />
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
