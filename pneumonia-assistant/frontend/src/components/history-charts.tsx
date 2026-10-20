"use client";

import { CalendarCheck } from "lucide-react";
import { Area, AreaChart, CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardIcon, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { BAND_INFO, BAND_ORDER, VITAL_INFO, VITALS } from "@/lib/bands";
import type { AssessmentRow, Band, Reading, Vital } from "@/lib/types";


const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

/** One point per day: the latest result that day. Alerts are marked with a ring. */
export function BandTimeline({ rows }: { rows: AssessmentRow[] }) {
  const byDay = new Map<string, AssessmentRow>();
  for (const r of [...rows].sort((a, b) => a.created_at.localeCompare(b.created_at))) {
    byDay.set(r.created_at.slice(0, 10), r);
  }
  const data = [...byDay.values()].map((r) => ({
    day: day(r.created_at),
    level: BAND_ORDER.indexOf(r.band),
    band: r.band,
    label: BAND_INFO[r.band].label,
    alert: r.alerts.length > 0,
  }));
  const config: ChartConfig = { level: { label: "Result", color: "var(--foreground)" } };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2.5">
          <CardIcon color="#1d4ed8" icon={CalendarCheck} />
          Your results by day
        </CardTitle>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <p className="text-sm text-muted-foreground">No checks yet.</p>
        ) : (
          <ChartContainer config={config} className="h-64 w-full">
            <LineChart data={data} margin={{ left: 8, right: 16, top: 12 }}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis dataKey="day" tickLine={false} axisLine={false} />
              <YAxis
                domain={[-0.3, BAND_ORDER.length - 0.7]}
                ticks={BAND_ORDER.map((_, i) => i)}
                tickFormatter={(i: number) => BAND_ORDER[i] ?? ""}
                width={80}
                tickLine={false}
                axisLine={false}
              />
              <ChartTooltip content={<ChartTooltipContent labelKey="day" nameKey="label" hideIndicator
                formatter={(_v, _n, item) => item.payload.label} />} />
              <Line
                type="stepAfter"
                dataKey="level"
                stroke="var(--muted-foreground)"
                strokeWidth={1.5}
                isAnimationActive={false}
                dot={({ cx, cy, payload, index }) => (
                  <g key={index}>
                    {payload.alert && <circle cx={cx} cy={cy} r={10} fill="none" stroke="#dc2626" strokeWidth={2} />}
                    <circle cx={cx} cy={cy} r={6} fill={BAND_INFO[payload.band as Band].color} />
                  </g>
                )}
              />
            </LineChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}

/** Seven days of device readings, one Health-style chart per vital: 2 per row, then 3 + 2 on wide screens. */
export function VitalCharts({ readings }: { readings: Reading[] }) {
  return (
    <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-6">
      {VITALS.map((v: Vital, i) => {
        const info = VITAL_INFO[v];
        const data = readings
          .filter((r) => r.vital === v)
          .map((r) => ({ t: new Date(r.taken_at).getTime(), value: r.value }))
          .sort((a, b) => a.t - b.t);
        const values = data.map((d) => d.value);
        const config: ChartConfig = { value: { label: info.label, color: info.color } };
        return (
          <Card
            key={v}
           
            className={i < 3 ? "xl:col-span-2" : "md:last:col-span-2 xl:col-span-3 xl:last:col-span-3"}
          >
            <CardHeader className="pb-0">
              <CardTitle className="flex items-center gap-2.5 text-[15px]">
                <CardIcon color={info.color} icon={info.icon} /> {info.label}
              </CardTitle>
              {values.length > 0 && (
                <CardDescription>
                  <span className="text-xs">Range, last 7 days</span>
                  <br />
                  <span className="text-[28px] font-semibold tracking-tight text-foreground tabular-nums">
                    {Math.min(...values).toFixed(info.digits)}–{Math.max(...values).toFixed(info.digits)}
                  </span>
                  <span className="ml-1 text-[15px] font-semibold">{info.unit}</span>
                </CardDescription>
              )}
            </CardHeader>
            <CardContent>
              {data.length === 0 ? (
                <p className="py-8 text-sm text-muted-foreground">No readings in the last 7 days.</p>
              ) : (
                <ChartContainer config={config} className="h-44 w-full">
                  <AreaChart data={data} margin={{ left: 0, right: 8, top: 8 }}>
                    <defs>
                      <linearGradient id={`fill-${v}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stopColor={info.color} stopOpacity={0.3} />
                        <stop offset="1" stopColor={info.color} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid vertical={false} strokeDasharray="3 3" />
                    <XAxis
                      dataKey="t"
                      type="number"
                      scale="time"
                      domain={["dataMin", "dataMax"]}
                      tickFormatter={(t: number) => day(new Date(t).toISOString())}
                      tickLine={false}
                      axisLine={false}
                      minTickGap={24}
                    />
                    <YAxis domain={["auto", "auto"]} width={36} tickLine={false} axisLine={false} />
                    <ChartTooltip
                      content={
                        <ChartTooltipContent
                          labelFormatter={(_l, p) =>
                            new Date(p?.[0]?.payload?.t).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
                          }
                        />
                      }
                    />
                    <Area
                      type="monotone"
                      dataKey="value"
                      stroke="var(--color-value)"
                      strokeWidth={2.5}
                      fill={`url(#fill-${v})`}
                      dot={false}
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ChartContainer>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
