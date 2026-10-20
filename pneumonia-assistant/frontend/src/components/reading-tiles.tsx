import { Card, CardContent } from "@/components/ui/card";
import { VITAL_INFO, VITALS } from "@/lib/bands";
import type { PatientStatus } from "@/lib/types";

/** Latest device reading per vital, and which ones the device hasn't sent today. */
export function ReadingTiles({ status }: { status: PatientStatus }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {VITALS.map((v) => {
        const r = status.latest_readings[v];
        const info = VITAL_INFO[v];
        const missingToday = status.missing_for_stage1.includes(v);
        return (
          <Card key={v} className="py-0">
            <CardContent className="p-3">
              <p className="text-xs text-muted-foreground">{info.label}</p>
              <p className="mt-1 text-xl font-semibold tabular-nums">
                {r ? r.value.toFixed(info.digits) : "–"}
                <span className="ml-1 text-xs font-normal text-muted-foreground">{info.unit}</span>
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {missingToday
                  ? "No reading today: check your device"
                  : r
                    ? new Date(r.taken_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
                    : ""}
              </p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
