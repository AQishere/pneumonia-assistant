"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { YesNo } from "@/components/yes-no";
import { api, type CheckAnswers } from "@/lib/api";
import type { AssessResult } from "@/lib/types";

const QUESTIONS: { key: keyof CheckAnswers; label: string }[] = [
  { key: "respiratory_distress", label: "Are you short of breath, even when resting?" },
  { key: "cough", label: "Do you have a cough?" },
  { key: "fever", label: "Do you feel feverish?" },
  { key: "weakness", label: "Do you feel unusually weak or tired?" },
];

/** Asks today's questions and runs the risk check on the stored readings and labs. */
export function QuickCheck({ patientId, onResult }: { patientId: string; onResult: (r: AssessResult) => void }) {
  const [answers, setAnswers] = useState<Record<keyof CheckAnswers, 0 | 1 | null>>({
    respiratory_distress: null,
    cough: null,
    fever: null,
    weakness: null,
  });
  const [busy, setBusy] = useState(false);
  const ready = QUESTIONS.every((q) => answers[q.key] !== null);

  async function run() {
    setBusy(true);
    try {
      onResult(await api.assess(patientId, answers as CheckAnswers));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "The check could not run.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Run a check</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {QUESTIONS.map((q) => (
          <YesNo
            key={q.key}
            id={`q-${q.key}`}
            label={q.label}
            value={answers[q.key]}
            onChange={(v) => setAnswers((s) => ({ ...s, [q.key]: v }))}
          />
        ))}
        <Button className="mt-2 w-full" disabled={!ready || busy} onClick={run}>
          {busy ? "Checking…" : "Check now"}
        </Button>
      </CardContent>
    </Card>
  );
}
