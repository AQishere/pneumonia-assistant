"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { PageSkeleton } from "@/components/app-shell";
import { BrandMark } from "@/components/brand-mark";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ListGroup, YesNo } from "@/components/yes-no";
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

  if (loading || !user || me?.role) return <main className="mx-auto w-full max-w-4xl px-4 py-10"><PageSkeleton /></main>;

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
      toast.success("Profile saved. Welcome!");
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
      toast.success("Your clinician account is ready.");
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
    <main className="mx-auto w-full max-w-4xl px-4 py-10">
      <div className="mb-8 flex flex-col items-center text-center">
        <Link href="/" aria-label="Pneumonia Assistant home" className="rounded-xl">
          <BrandMark className="size-16" />
        </Link>
        <h1 className="mt-4 text-2xl font-semibold tracking-tight">Set up your profile</h1>
        <p className="mt-1 text-[15px] text-muted-foreground">This is asked once. You can change it later in your profile.</p>
      </div>
      <Card>
        <CardContent>
          <Tabs defaultValue="patient">
            <TabsList className="mx-auto mb-6 grid w-full max-w-md grid-cols-2">
              <TabsTrigger value="patient">I&apos;m monitoring my health</TabsTrigger>
              <TabsTrigger value="doctor">I&apos;m a doctor</TabsTrigger>
            </TabsList>

            <TabsContent value="patient" className="space-y-6">
              <div className="grid gap-8 md:grid-cols-2">
              <div className="space-y-4">
              <p className="text-[13px] font-semibold tracking-wide text-muted-foreground uppercase">About you</p>
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
              </div>
              <div className="space-y-1">
                <p className="text-[13px] font-semibold tracking-wide text-muted-foreground uppercase">
                  Do you have any of these long-term conditions?
                </p>
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
              </div>
              </div>
              <Button className="w-full" size="lg" disabled={!patientReady || busy} onClick={savePatient}>
                Save and continue
              </Button>
            </TabsContent>

            <TabsContent value="doctor" className="mx-auto max-w-md space-y-5">
              {nameField}
              <p className="text-sm text-muted-foreground">
                Patients can link you from their profile using your sign-in email. You&apos;ll then see their results.
              </p>
              <Button className="w-full" size="lg" disabled={!name.trim() || busy} onClick={saveDoctor}>
                Continue as a doctor
              </Button>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </main>
  );
}
