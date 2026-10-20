"use client";

import { Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import type { Labs } from "@/lib/types";

const FIELDS = [
  { key: "wbc", label: "White blood cells (WBC)", unit: "×10⁹/L" },
  { key: "neutrophils", label: "Neutrophils", unit: "%" },
  { key: "lymphocytes", label: "Lymphocytes", unit: "%" },
  { key: "crp", label: "C-reactive protein (CRP)", unit: "mg/L" },
] as const;
type Key = (typeof FIELDS)[number]["key"];

/** Parses a lab file: a CSV with a header row containing wbc, neutrophils, lymphocytes, crp (last row is used). */
function parseCsv(text: string): Partial<Record<Key, string>> {
  const rows = text.trim().split(/\r?\n/).map((r) => r.split(",").map((c) => c.trim()));
  if (rows.length < 2) throw new Error("The file needs a header row and at least one row of results.");
  const header = rows[0].map((h) => h.toLowerCase());
  const last = rows[rows.length - 1];
  const out: Partial<Record<Key, string>> = {};
  for (const f of FIELDS) {
    const i = header.indexOf(f.key);
    if (i === -1) throw new Error(`The file has no "${f.key}" column.`);
    out[f.key] = last[i];
  }
  return out;
}

export function LabsCard({ patientId, labs, onSaved }: { patientId: string; labs: Labs | null; onSaved: () => void }) {
  const [values, setValues] = useState<Record<Key, string>>({ wbc: "", neutrophils: "", lymphocytes: "", crp: "" });
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const ready = FIELDS.every((f) => values[f.key] !== "" && !Number.isNaN(Number(values[f.key])));

  async function onFile(file: File | undefined) {
    if (!file) return;
    try {
      const parsed = parseCsv(await file.text());
      setValues((v) => ({ ...v, ...parsed }));
      toast.success("Results read from the file. Check them, then save.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not read the file.");
    }
  }

  async function save() {
    setBusy(true);
    try {
      await api.uploadLabs(patientId, {
        wbc: Number(values.wbc),
        neutrophils: Number(values.neutrophils),
        lymphocytes: Number(values.lymphocytes),
        crp: Number(values.crp),
      });
      toast.success("Lab results saved.");
      setValues({ wbc: "", neutrophils: "", lymphocytes: "", crp: "" });
      onSaved();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save the results.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Lab results</CardTitle>
        <CardDescription>
          {labs
            ? `Latest from ${new Date(labs.taken_at).toLocaleDateString()}: WBC ${labs.wbc}, neutrophils ${labs.neutrophils}%, lymphocytes ${labs.lymphocytes}%, CRP ${labs.crp} mg/L.`
            : "No lab results from the last 7 days. The full check needs recent results."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          {FIELDS.map((f) => (
            <div key={f.key} className="space-y-1.5">
              <Label htmlFor={`lab-${f.key}`} className="text-xs">
                {f.label} <span className="text-muted-foreground">({f.unit})</span>
              </Label>
              <Input
                id={`lab-${f.key}`}
                inputMode="decimal"
                value={values[f.key]}
                onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
              />
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={!ready || busy} onClick={save}>
            Save results
          </Button>
          <Button variant="outline" onClick={() => fileRef.current?.click()}>
            <Upload className="size-4" /> Load from file (.csv)
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => onFile(e.target.files?.[0])}
          />
        </div>
      </CardContent>
    </Card>
  );
}
