"use client";

import { FlaskConical, Plus } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardIcon, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { LAB_COLOR } from "@/lib/bands";

const FIELDS = [
  { key: "wbc", label: "WBC", full: "White blood cells", unit: "×10⁹/L" },
  { key: "neutrophils", label: "Neutrophils", full: "", unit: "%" },
  { key: "lymphocytes", label: "Lymphocytes", full: "", unit: "%" },
  { key: "crp", label: "CRP", full: "C-reactive protein", unit: "mg/L" },
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

/** Enter or upload new lab results; the latest ones show in the Lab results widget. */
export function LabsCard({ patientId, onSaved }: { patientId: string; onSaved: () => void }) {
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
        <CardTitle className="flex items-center gap-2.5">
          <CardIcon color={LAB_COLOR} icon={FlaskConical} />
          Add Lab Results
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="divide-y divide-border">
          {FIELDS.map((f) => (
            <div key={f.key} className="flex items-center justify-between gap-3 py-2.5">
              <Label htmlFor={`lab-${f.key}`} className="min-w-0 flex-col items-start gap-0 text-[15px] font-normal">
                {f.label}
                {f.full && <span className="text-[13px] text-muted-foreground">{f.full}</span>}
              </Label>
              <div className="flex h-9 w-28 shrink-0 items-center rounded-md border border-input bg-card pr-2.5 shadow-xs transition-[border-color,box-shadow] focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/20">
                <Input
                  id={`lab-${f.key}`}
                  inputMode="decimal"
                  value={values[f.key]}
                  onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                  className="h-8 min-w-0 border-0 bg-transparent px-2.5 text-right tabular-nums shadow-none focus-visible:border-0 focus-visible:ring-0"
                />
                <span className="shrink-0 text-[13px] text-muted-foreground">{f.unit}</span>
              </div>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button disabled={!ready || busy} onClick={save}>
            Save Results
          </Button>
          <Button variant="outline" onClick={() => fileRef.current?.click()} title="Load results from a .csv file">
            <Plus className="size-4" /> Upload
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
