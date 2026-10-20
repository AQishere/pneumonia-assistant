import { AlertTriangle, Clock } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { BAND_INFO } from "@/lib/bands";
import type { Alert as AlertT, AssessResult, Band } from "@/lib/types";
import { cn } from "@/lib/utils";

export function CriticalAlerts({ notice, alerts }: { notice: string | null; alerts: AlertT[] }) {
  if (!alerts.length) return null;
  return (
    <div role="alert" className="flex gap-3.5 rounded-2xl border border-red-200 bg-card p-4 shadow-sm">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-[#fee2e2] text-[#991b1b]">
        <AlertTriangle className="size-4.5" aria-hidden />
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <h2 className="font-semibold text-[#991b1b]">Needs attention now</h2>
        {notice && <p className="text-sm text-muted-foreground">{notice}</p>}
        <ul className="flex flex-wrap gap-1.5 pt-1">
          {alerts.map((a) => (
            <li key={a.code} className="rounded-full bg-[#fee2e2] px-2.5 py-1 text-xs font-medium text-[#991b1b]">
              {a.message}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function when(iso: string | undefined) {
  return iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";
}

/** The latest result in plain words, with the fixed advice from the server. */
export function StatusCard({ result, band, at }: { result?: AssessResult | null; band?: Band | null; at?: string }) {
  const b = result?.band ?? band ?? null;
  if (!b) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No result yet</CardTitle>
          <CardDescription>
            {result?.note ?? "Run a check below or ask the assistant to see how you're doing."}
          </CardDescription>
        </CardHeader>
        {!!result?.missing?.length && (
          <CardContent>
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {result.missing.map((m) => (
                <li key={m.item}>{m.message}</li>
              ))}
            </ul>
          </CardContent>
        )}
      </Card>
    );
  }
  const info = BAND_INFO[b];
  const checked = at ?? result?.assessed_at;
  return (
    <div className="flex gap-3.5 rounded-2xl border bg-card p-4 shadow-sm">
      <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-full", info.badge)}>
        <info.icon className="size-4.5" aria-hidden />
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
          <h2 className="font-semibold">{info.label}</h2>
          {checked && <span className="text-xs text-muted-foreground">{when(checked)}</span>}
        </div>
        <p className="text-sm text-muted-foreground">{info.summary}</p>
        {result?.recommendation && <p className="pt-1 text-sm font-medium">{result.recommendation}</p>}
        {b === "Watch" && result?.persistence?.reassess_after && (
          <p className="flex items-center gap-1.5 pt-1 text-sm">
            <Clock className="size-4" aria-hidden /> Re-check after {when(result.persistence.reassess_after)}.
          </p>
        )}
        {!!result?.missing?.length && (
          <ul className="list-disc space-y-0.5 pt-1 pl-5 text-sm">
            {result.missing.map((m) => (
              <li key={m.item}>{m.message}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
