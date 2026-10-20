import { AlertTriangle, Clock } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { BAND_INFO } from "@/lib/bands";
import type { Alert as AlertT, AssessResult, Band } from "@/lib/types";
import { cn } from "@/lib/utils";

export function CriticalAlerts({ notice, alerts }: { notice: string | null; alerts: AlertT[] }) {
  if (!alerts.length) return null;
  return (
    <Alert variant="destructive" className="border-red-300 bg-red-50 dark:bg-red-950">
      <AlertTriangle />
      <AlertTitle>Needs attention now</AlertTitle>
      <AlertDescription>
        <p>{notice}</p>
        <ul className="mt-2 list-disc pl-5">
          {alerts.map((a) => (
            <li key={a.code}>{a.message}</li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
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
  return (
    <div className={cn("rounded-xl border p-5", info.tone)}>
      <div className="flex items-center gap-2">
        <span className={cn("size-3 rounded-full", info.dot)} aria-hidden />
        <h2 className="text-lg font-semibold">{info.label}</h2>
      </div>
      <p className="mt-1 text-sm opacity-90">{info.summary}</p>
      {result?.recommendation && <p className="mt-3 font-medium">{result.recommendation}</p>}
      {b === "Watch" && result?.persistence?.reassess_after && (
        <p className="mt-2 flex items-center gap-1.5 text-sm">
          <Clock className="size-4" aria-hidden /> Re-check after {when(result.persistence.reassess_after)}.
        </p>
      )}
      {!!result?.missing?.length && (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
          {result.missing.map((m) => (
            <li key={m.item}>{m.message}</li>
          ))}
        </ul>
      )}
      {(at || result?.assessed_at) && (
        <p className="mt-3 text-xs opacity-75">Checked {when(at ?? result?.assessed_at)}.</p>
      )}
    </div>
  );
}
