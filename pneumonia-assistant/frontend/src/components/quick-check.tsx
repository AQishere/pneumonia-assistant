"use client";

import { Stethoscope } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardIcon, CardTitle } from "@/components/ui/card";
import { ListGroup, YesNo } from "@/components/yes-no";
import { api, type CheckAnswers } from "@/lib/api";
import { BAND_INFO } from "@/lib/bands";
import type { AssessResult } from "@/lib/types";

const QUESTIONS: { key: keyof CheckAnswers; label: string; hint: string }[] = [
  { key: "respiratory_distress", label: "Short of breath?", hint: "Are you short of breath, even when resting?" },
  { key: "cough", label: "Coughing?", hint: "Do you have a cough?" },
  { key: "fever", label: "Feverish?", hint: "Do you feel feverish?" },
  { key: "weakness", label: "Tired?", hint: "Do you feel unusually weak or tired?" },
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
      const result = await api.assess(patientId, answers as CheckAnswers);
      onResult(result);
      if (result.band) toast.success(`Check complete: ${BAND_INFO[result.band].label.toLowerCase()}.`);
      else toast.info("The check needs a little more information. See below.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "The check could not run.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2.5">
          <CardIcon color="#16a34a" icon={Stethoscope} />
          Run a Daily Check
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <ListGroup>
          {QUESTIONS.map((q) => (
            <YesNo
              key={q.key}
              id={`q-${q.key}`}
              label={q.label}
              hint={q.hint}
              value={answers[q.key]}
              onChange={(v) => setAnswers((s) => ({ ...s, [q.key]: v }))}
            />
          ))}
        </ListGroup>
        <Button className="w-full" disabled={!ready || busy} onClick={run}>
          {busy ? "Checking…" : "Check now"}
        </Button>
      </CardContent>
    </Card>
  );
}
