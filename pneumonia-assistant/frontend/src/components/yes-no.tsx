"use client";

import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

/** A required yes/no question; value is null until answered. */
export function YesNo({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: 0 | 1 | null;
  onChange: (v: 0 | 1) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border px-3 py-2.5">
      <span className="text-sm">{label}</span>
      <RadioGroup
        className="flex gap-4"
        value={value === null ? "" : String(value)}
        onValueChange={(v) => onChange(v === "1" ? 1 : 0)}
        aria-label={label}
      >
        <div className="flex items-center gap-1.5">
          <RadioGroupItem id={`${id}-yes`} value="1" />
          <Label htmlFor={`${id}-yes`} className="font-normal">Yes</Label>
        </div>
        <div className="flex items-center gap-1.5">
          <RadioGroupItem id={`${id}-no`} value="0" />
          <Label htmlFor={`${id}-no`} className="font-normal">No</Label>
        </div>
      </RadioGroup>
    </div>
  );
}
