import { AlertTriangle, Clock, Sparkles } from "lucide-react";

import { BAND_INFO } from "@/lib/bands";
import type { Alert as AlertT, AssessResult, Band } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Icon, a title with an optional time on the right, and the body underneath. Alerts are a red banner; results
 *  are a white card with a coloured edge for the risk level. Compact: for narrow columns (the chat's side panel). */
function Panel({
  color,
  icon: Icon,
  title,
  time,
  role,
  compact,
  children,
}: {
  color: string;
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  title: React.ReactNode;
  time?: string;
  role?: string;
  compact?: boolean;
  children?: React.ReactNode;
}) {
  const alert = role === "alert";
  return (
    <div
      role={role}
      className={cn(
        "flex animate-rise gap-3 rounded-2xl",
        alert ? "border border-red-200 bg-red-50" : "surface border-l-4",
        compact ? "p-4" : "p-5",
      )}
      style={alert ? undefined : { borderLeftColor: color }}
    >
      <Icon className="mt-0.5 size-5 shrink-0" style={{ color }} aria-hidden />
      <div className={cn("min-w-0 flex-1 space-y-1 text-sm", compact && "[&_li]:text-[13px] [&_p]:text-[13px]")}>
        <div
          className={cn("flex gap-x-4 gap-y-0.5", compact ? "flex-col" : "flex-wrap items-baseline justify-between")}
        >
          <h2 className="text-[15px] leading-snug font-semibold">{title}</h2>
          {time && <span className="text-xs text-muted-foreground">{time}</span>}
        </div>
        {children}
      </div>
    </div>
  );
}

export function CriticalAlerts({
  notice,
  alerts,
  compact,
}: {
  notice: string | null;
  alerts: AlertT[];
  compact?: boolean;
}) {
  if (!alerts.length) return null;
  return (
    <Panel
      role="alert"
      color="#dc2626"
      icon={AlertTriangle}
      title={<span className="text-red-800">Action required</span>}
      compact={compact}
    >
      {notice && <p className="max-w-3xl leading-relaxed text-red-900/80">{notice}</p>}
      <ul className="space-y-0.5 pt-0.5">
        {alerts.map((a) => (
          <li key={a.code} className="leading-snug font-medium text-red-800">
            {a.message}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function when(iso: string | undefined) {
  return iso
    ? new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
    : "";
}

/** The latest result in plain words, with the fixed advice from the server. */
export function StatusCard({
  result,
  band,
  at,
  alertActive,
  compact,
}: {
  result?: AssessResult | null;
  band?: Band | null;
  at?: string;
  compact?: boolean;
  /** A critical reading is shown above: a Low result must not read as "no concern". */
  alertActive?: boolean;
}) {
  const b = result?.band ?? band ?? null;
  if (!b) {
    return (
      <Panel color="#1d4ed8" icon={Sparkles} title="No result yet" compact={compact}>
        <p className="text-muted-foreground">
          {result?.note ?? "Run a check or ask the assistant to see how you're doing."}
        </p>
        {!!result?.missing?.length && (
          <ul className="list-disc space-y-0.5 pl-5 text-sm">
            {result.missing.map((m) => (
              <li key={m.item}>{m.message}</li>
            ))}
          </ul>
        )}
      </Panel>
    );
  }
  const info = BAND_INFO[b];
  const lowWithAlert = b === "Low" && alertActive;
  return (
    <Panel
      color={info.color}
      icon={info.icon}
      title={lowWithAlert ? "Low pneumonia risk" : info.label}
      time={when(at ?? result?.assessed_at)}
      compact={compact}
    >
      <p className="text-muted-foreground">
        {lowWithAlert ? "No signs of pneumonia, but a reading above needs attention." : info.summary}
      </p>
      {result?.recommendation && <p className="pt-1 font-medium">{result.recommendation}</p>}
      {b === "Watch" && result?.persistence?.reassess_after && (
        <p className="flex items-center gap-1.5">
          <Clock className="size-4 text-muted-foreground" aria-hidden /> Re-check after{" "}
          {when(result.persistence.reassess_after)}.
        </p>
      )}
      {!!result?.missing?.length && (
        <ul className="list-disc space-y-0.5 pl-5 text-sm">
          {result.missing.map((m) => (
            <li key={m.item}>{m.message}</li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
