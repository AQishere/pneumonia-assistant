"use client";

import { Info } from "lucide-react";

import { cn } from "@/lib/utils";

/** A required yes/no question as a list row with a segmented control; value is null until answered.
 *  Put rows inside <ListGroup> to get the hairline separators. */
export function YesNo({
  id,
  label,
  hint,
  value,
  onChange,
}: {
  id: string;
  label: string;
  hint?: string;
  value: 0 | 1 | null;
  onChange: (v: 0 | 1) => void;
}) {
  return (
    <div className="flex min-h-11 flex-wrap items-center justify-between gap-x-3 gap-y-1.5 py-2">
      <span className="flex items-center gap-1.5 text-sm">
        <span id={`${id}-label`}>{label}</span>
        {hint && (
          <span title={hint} className="text-muted-foreground" aria-label={hint} role="img">
            <Info className="size-3.5" />
          </span>
        )}
      </span>
      <div role="radiogroup" aria-labelledby={`${id}-label`} className="flex rounded-lg border bg-muted p-0.5">
        {([1, 0] as const).map((v) => (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={value === v}
            onClick={() => onChange(v)}
            className={cn(
              "h-7 min-w-12 cursor-pointer rounded-md px-3 text-[13px] font-medium transition-colors",
              value === v ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {v ? "Yes" : "No"}
          </button>
        ))}
      </div>
    </div>
  );
}

/** A list of rows separated by hairlines. */
export function ListGroup({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("divide-y divide-border", className)}>{children}</div>;
}
