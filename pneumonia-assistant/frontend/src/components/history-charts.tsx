"use client";

import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { BAND_INFO, BAND_ORDER, VITAL_INFO, VITALS } from "@/lib/bands";
import type { AssessmentRow, Band, Reading, Vital } from "@/lib/types";

const BAND_COLOR: Record<Band, string> = {
  Low: "#10b981",
  Pending: "#94a3b8",
  Moderate: "#f59e0b",
  Watch: "#f97316",
  High: "#dc2626",
};

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
        <CardTitle>Your results by day</CardTitle>
        <CardDescription>The latest check of each day. A ringed dot means a critical reading that day.</CardDescription>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <p className="text-sm text-muted-foreground">No checks yet.</p>
        ) : (
          <ChartContainer config={config} className="h-56 w-full">
            <LineChart data={data} margin={{ left: 8, right: 16, top: 12 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="day" tickLine={false} axisLine={false} />
              <YAxis
                domain={[-0.3, BAND_ORDER.length - 0.7]}
                ticks={BAND_ORDER.map((_, i) => i)}
                tickFormatter={(i: number) => BAND_ORDER[i] ?? ""}
                width={72}
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
                    <circle cx={cx} cy={cy} r={6} fill={BAND_COLOR[payload.band as Band]} />
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

/** Seven days of device readings, one small chart per vital. */
export function VitalCharts({ readings }: { readings: Reading[] }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {VITALS.map((v: Vital) => {
        const info = VITAL_INFO[v];
        const data = readings
          .filter((r) => r.vital === v)
          .map((r) => ({ t: new Date(r.taken_at).getTime(), value: r.value }));
        const config: ChartConfig = { value: { label: info.label, color: "var(--chart-1)" } };
        return (
          <Card key={v}>
            <CardHeader className="pb-0">
              <CardTitle className="text-base">
                {info.label} <span className="text-sm font-normal text-muted-foreground">({info.unit})</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.length === 0 ? (
                <p className="py-8 text-sm text-muted-foreground">No readings in the last 7 days.</p>
              ) : (
                <ChartContainer config={config} className="h-40 w-full">
                  <LineChart data={data} margin={{ left: 0, right: 8, top: 8 }}>
                    <CartesianGrid vertical={false} />
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
                    <Line type="monotone" dataKey="value" stroke="var(--color-value)" strokeWidth={2} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ChartContainer>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
