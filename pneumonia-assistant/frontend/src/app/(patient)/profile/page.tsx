"use client";

import { X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { YesNo } from "@/components/yes-no";
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
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-2xl font-semibold">Profile</h1>
      <Card>
        <CardHeader>
          <CardTitle>{profile.display_name}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="max-w-32 space-y-1.5">
            <Label htmlFor="age">Age</Label>
            <Input id="age" type="number" min={0} max={120} value={age} onChange={(e) => setAge(e.target.value)} />
          </div>
          {CONDITIONS.map((c) => (
            <YesNo
              key={c}
              id={c}
              label={CONDITION_LABELS[c]}
              value={conditions[c]}
              onChange={(v) => setConditions((s) => ({ ...s, [c]: v }))}
            />
          ))}
          <Button disabled={!changed || busy} onClick={save}>
            Save changes
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Your doctor</CardTitle>
          <CardDescription>
            A linked doctor can see your readings and results. They need an account in this app.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {profile.doctor_ids.length > 0 && (
            <ul className="space-y-2">
              {profile.doctor_ids.map((uid) => (
                <li key={uid} className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
                  <span>Linked doctor</span>
                  <Button variant="ghost" size="sm" disabled={busy} onClick={() => unlink(uid)}>
                    <X className="size-4" /> Remove
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex gap-2">
            <Input
              type="email"
              placeholder="Doctor's email"
              value={doctorEmail}
              onChange={(e) => setDoctorEmail(e.target.value)}
              aria-label="Doctor's email"
            />
            <Button disabled={!doctorEmail.includes("@") || busy} onClick={link}>
              Link
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
