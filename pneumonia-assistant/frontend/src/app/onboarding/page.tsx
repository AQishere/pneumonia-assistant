"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { PageSkeleton } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { YesNo } from "@/components/yes-no";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { CONDITION_LABELS, CONDITIONS } from "@/lib/bands";
import type { Condition } from "@/lib/types";

export default function OnboardingPage() {
  const { user, me, loading, refresh } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [sex, setSex] = useState("");
  const [conditions, setConditions] = useState<Record<Condition, 0 | 1 | null>>(
    () => Object.fromEntries(CONDITIONS.map((c) => [c, null])) as Record<Condition, 0 | 1 | null>,
  );
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    else if (me?.role) router.replace(me.role === "doctor" ? "/doctor" : "/dashboard");
  }, [loading, user, me, router]);

  if (loading || !user || me?.role) return <main className="mx-auto w-full max-w-xl px-4 py-10"><PageSkeleton /></main>;

  const ageNum = Number(age);
  const patientReady =
    name.trim() && age !== "" && ageNum >= 0 && ageNum <= 120 && sex && CONDITIONS.every((c) => conditions[c] !== null);

  async function savePatient() {
    if (!user || !patientReady) return;
    setBusy(true);
    try {
      await api.signup(user.uid, {
        display_name: name.trim(),
        age: ageNum,
        sex,
        ...(conditions as Record<Condition, 0 | 1>),
      });
      await refresh();
      router.replace("/dashboard");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save your profile.");
    } finally {
      setBusy(false);
    }
  }

  async function saveDoctor() {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await api.registerDoctor(name.trim());
      await refresh();
      router.replace("/doctor");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save your profile.");
    } finally {
      setBusy(false);
    }
  }

  const nameField = (
    <div className="space-y-1.5">
      <Label htmlFor="name">Your name</Label>
      <Input id="name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
    </div>
  );

  return (
    <main className="mx-auto w-full max-w-xl px-4 py-10">
      <Card>
        <CardHeader>
          <CardTitle>Set up your profile</CardTitle>
          <CardDescription>This is asked once. You can change it later in your profile.</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="patient">
            <TabsList className="mb-5 grid w-full grid-cols-2">
              <TabsTrigger value="patient">I&apos;m monitoring my health</TabsTrigger>
              <TabsTrigger value="doctor">I&apos;m a doctor</TabsTrigger>
            </TabsList>

            <TabsContent value="patient" className="space-y-5">
              {nameField}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="age">Age</Label>
                  <Input id="age" type="number" min={0} max={120} value={age} onChange={(e) => setAge(e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="sex">Sex</Label>
                  <Select value={sex} onValueChange={setSex}>
                    <SelectTrigger id="sex" className="w-full">
                      <SelectValue placeholder="Choose" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="female">Female</SelectItem>
                      <SelectItem value="male">Male</SelectItem>
                      <SelectItem value="other">Other</SelectItem>
                      <SelectItem value="prefer_not_to_say">Prefer not to say</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <p className="text-sm font-medium">Do you have any of these long-term conditions?</p>
                {CONDITIONS.map((c) => (
                  <YesNo
                    key={c}
                    id={c}
                    label={CONDITION_LABELS[c]}
                    value={conditions[c]}
                    onChange={(v) => setConditions((s) => ({ ...s, [c]: v }))}
                  />
                ))}
              </div>
              <Button className="w-full" disabled={!patientReady || busy} onClick={savePatient}>
                Save and continue
              </Button>
            </TabsContent>

            <TabsContent value="doctor" className="space-y-5">
              {nameField}
              <p className="text-sm text-muted-foreground">
                Patients can link you from their profile using your sign-in email. You&apos;ll then see their results.
              </p>
              <Button className="w-full" disabled={!name.trim() || busy} onClick={saveDoctor}>
                Continue as a doctor
              </Button>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </main>
  );
}
