import { ChevronRight, FlaskConical, TriangleAlert } from "lucide-react";
import Link from "next/link";

import { LAB_COLOR, VITAL_INFO, VITALS } from "@/lib/bands";
import type { Labs, PatientStatus, Reading, Vital } from "@/lib/types";
import { cn } from "@/lib/utils";

const time = (iso: string) => {
  const d = new Date(iso);
  const today = new Date().toDateString() === d.toDateString();
  return today
    ? d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
    : d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
};

/** A small trend line of recent readings, drawn in the vital's colour. */
function Sparkline({ values, color }: { values: number[]; color: string }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values.map((v, i) => [(i / (values.length - 1)) * 100, 30 - ((v - min) / span) * 26 - 2]);
  const line = points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const id = `spark-${color.slice(1)}`;
  return (
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" className="h-10 w-full" aria-hidden>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.15" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,32 ${line} 100,32`} fill={`url(#${id})`} />
      <polyline
        points={line}
        fill="none"
        stroke={color}
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

/** Where a reading sits against the typical range: a small status label next to the value. */
function RangeStatus({ value, range }: { value: number; range: [number, number] }) {
  const [lo, hi] = range;
  const state = value < lo ? "Below range" : value > hi ? "Above range" : "Normal";
  return (
    <span
      className={cn(
        "rounded-md px-1.5 py-0.5 text-xs font-medium whitespace-nowrap",
        state === "Normal" ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-800",
      )}
    >
      {state}
    </span>
  );
}

/** One metric card: icon and name, range status, the value, the typical range and time, and a trend line. */
export function Widget({
  icon: Icon,
  color,
  label,
  at,
  value,
  unit,
  range,
  status,
  note,
  warn,
  trend,
  href,
  style,
}: {
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  color: string;
  label: string;
  at?: string;
  value: string;
  unit?: string;
  range?: [number, number];
  status?: React.ReactNode;
  note?: string;
  warn?: boolean;
  trend?: number[];
  href?: string;
  style?: React.CSSProperties;
}) {
  const footer = [range && `Typical ${range[0]}–${range[1]}`, at && time(at)].filter(Boolean).join(" · ");
  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2 text-sm font-medium text-muted-foreground">
          <Icon className="size-4 shrink-0" style={{ color }} />
          <span className="truncate" title={label}>
            {label}
          </span>
        </span>
        {status}
      </div>
      <div className="mt-3 flex items-end justify-between gap-3">
        <p className="shrink-0">
          <span className="text-3xl font-semibold tracking-tight tabular-nums">{value}</span>
          {unit && <span className="ml-1 text-sm text-muted-foreground">{unit}</span>}
        </p>
        {trend && (
          <div className="w-24 max-w-[45%]">
            <Sparkline values={trend} color={color} />
          </div>
        )}
      </div>
      <div className="mt-auto flex items-center justify-between gap-2 pt-3 text-xs text-muted-foreground">
        <span className="truncate">{footer}</span>
        {href && <ChevronRight className="size-4 shrink-0" />}
      </div>
      {note && (
        <p className={cn("mt-2 flex items-center gap-1 text-xs", warn ? "text-amber-800" : "text-muted-foreground")}>
          {warn && <TriangleAlert className="size-3.5" />}
          {note}
        </p>
      )}
    </>
  );
  const cls = "flex min-h-36 animate-rise flex-col rounded-2xl surface p-5 transition-colors hover:border-input";
  return href ? (
    <Link href={href} className={cls} style={style}>
      {body}
    </Link>
  ) : (
    <div className={cls} style={style}>
      {body}
    </div>
  );
}

/** Latest device reading per vital as widgets, plus the latest labs. */
export function ReadingTiles({
  status,
  readings,
  historyHref,
}: {
  status: PatientStatus;
  readings?: Reading[];
  historyHref?: string;
}) {
  const trend = (v: Vital) =>
    readings
      ?.filter((r) => r.vital === v)
      .sort((a, b) => a.taken_at.localeCompare(b.taken_at))
      .slice(-12)
      .map((r) => r.value);
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {VITALS.map((v, i) => {
        const r = status.latest_readings[v];
        const info = VITAL_INFO[v];
        const missingToday = status.missing_for_stage1.includes(v);
        return (
          <Widget
            key={v}
            icon={info.icon}
            color={info.color}
            label={info.label}
            at={r?.taken_at}
            value={r ? r.value.toFixed(info.digits) : "—"}
            unit={info.unit}
            range={info.range}
            status={r && <RangeStatus value={r.value} range={info.range} />}
            note={missingToday ? "No reading today: check your device" : undefined}
            warn={missingToday}
            trend={trend(v)}
            href={historyHref}
            style={{ animationDelay: `${i * 50}ms` }}
          />
        );
      })}
      <LabsWidget labs={status.labs} style={{ animationDelay: "250ms" }} />
    </div>
  );
}

function LabsWidget({ labs, style }: { labs: Labs | null; style?: React.CSSProperties }) {
  const items = labs
    ? [
        ["WBC", labs.wbc],
        ["Neut.", `${labs.neutrophils}%`],
        ["Lymph.", `${labs.lymphocytes}%`],
        ["CRP", labs.crp],
      ]
    : [];
  return (
    <div className="flex min-h-36 animate-rise flex-col rounded-2xl surface p-5" style={style}>
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <FlaskConical className="size-4" style={{ color: LAB_COLOR }} />
          Lab results
        </span>
        {labs && <span className="text-xs text-muted-foreground">{time(labs.taken_at)}</span>}
      </div>
      {labs ? (
        <dl className="mt-3 grid grid-cols-4 gap-2">
          {items.map(([k, v]) => (
            <div key={k}>
              <dt className="text-xs text-muted-foreground">{k}</dt>
              <dd className="text-lg font-semibold tabular-nums">{v}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">No recent results</p>
      )}
    </div>
  );
}
