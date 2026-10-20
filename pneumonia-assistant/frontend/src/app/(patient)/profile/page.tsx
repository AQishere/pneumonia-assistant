"use client";

import { HeartPulse, Stethoscope, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Avatar, PageHeader } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardIcon, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ListGroup, YesNo } from "@/components/yes-no";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { CONDITION_LABELS, CONDITIONS } from "@/lib/bands";
import type { Condition } from "@/lib/types";

export default function ProfilePage() {
  const { me, refresh } = useAuth();
  const profile = me!.profile!;
  const [conditions, setConditions] = useState(profile.history_flags);
  const [age, setAge] = useState(String(profile.age ?? ""));
  const [doctorEmail, setDoctorEmail] = useState("");
  const [busy, setBusy] = useState(false);

  const changed =
    CONDITIONS.some((c) => conditions[c] !== profile.history_flags[c]) || Number(age) !== profile.age;

  async function save() {
    setBusy(true);
    try {
      await api.updateProfile(profile.patient_id, {
        age: Number(age),
        ...(Object.fromEntries(CONDITIONS.map((c) => [c, conditions[c]])) as Record<Condition, 0 | 1>),
      });
      await refresh();
      toast.success("Profile updated.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  async function link() {
    setBusy(true);
    try {
      const r = await api.linkDoctor(profile.patient_id, doctorEmail.trim());
      await refresh();
      setDoctorEmail("");
      toast.success(`${r.linked.display_name ?? "Your doctor"} can now see your results.`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not link the doctor.");
    } finally {
      setBusy(false);
    }
  }

  async function unlink(uid: string) {
    setBusy(true);
    try {
      await api.unlinkDoctor(profile.patient_id, uid);
      await refresh();
      toast.success("Doctor removed.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not remove the doctor.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Profile" />
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] xl:grid-cols-[380px_minmax(0,1fr)]">
        <div className="space-y-8">
          <div
            className="flex animate-rise flex-col items-center rounded-2xl surface px-5 py-7 text-center"
          >
            <Avatar name={profile.display_name} className="size-20 text-2xl" />
            <h2 className="mt-3 text-xl font-semibold">{profile.display_name}</h2>
            <p className="text-[15px] text-muted-foreground">{me?.email}</p>
            <dl className="mt-5 grid w-full grid-cols-2 divide-x rounded-xl bg-muted py-3">
              <div>
                <dt className="text-[13px] text-muted-foreground">Age</dt>
                <dd className="text-lg font-semibold">{profile.age ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-[13px] text-muted-foreground">Sex</dt>
                <dd className="text-lg font-semibold capitalize">{profile.sex?.replaceAll("_", " ") ?? "—"}</dd>
              </div>
            </dl>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2.5">
                <CardIcon color="#4f46e5" icon={Stethoscope} />
                Your doctor
              </CardTitle>
              <CardDescription>
                A linked doctor can see your readings and results. They need an account in this app.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {profile.doctor_ids.length > 0 && (
                <ul className="divide-y rounded-xl bg-muted px-3">
                  {profile.doctor_ids.map((uid) => (
                    <li key={uid} className="flex items-center justify-between py-2 text-[15px]">
                      <span>Linked doctor</span>
                      <Button variant="ghost" size="sm" disabled={busy} onClick={() => unlink(uid)} className="text-destructive hover:bg-destructive/10">
                        <X className="size-4" /> Remove
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="space-y-1.5">
                <Label htmlFor="doctor-email">Doctor&apos;s email</Label>
                <div className="flex gap-2">
                  <Input
                    id="doctor-email"
                    type="email"
                    autoComplete="off"
                    value={doctorEmail}
                    onChange={(e) => setDoctorEmail(e.target.value)}
                  />
                  <Button disabled={!doctorEmail.includes("@") || busy} onClick={link}>
                    Link doctor
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="content-start self-start">
          <CardHeader>
            <CardTitle className="flex items-center gap-2.5">
              <CardIcon color="#e11d48" icon={HeartPulse} />
              Health details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between gap-3 border-b pb-3">
              <Label htmlFor="age" className="text-[15px] font-normal">Age</Label>
              <Input id="age" type="number" min={0} max={120} value={age} onChange={(e) => setAge(e.target.value)} className="w-24 text-right" />
            </div>
            <p className="text-[13px] font-semibold tracking-wide text-muted-foreground uppercase">Long-term conditions</p>
            <ListGroup>
              {CONDITIONS.map((c) => (
                <YesNo
                  key={c}
                  id={c}
                  label={CONDITION_LABELS[c]}
                  value={conditions[c]}
                  onChange={(v) => setConditions((s) => ({ ...s, [c]: v }))}
                />
              ))}
            </ListGroup>
            <Button className="w-full" size="lg" disabled={!changed || busy} onClick={save}>
              Save changes
            </Button>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
