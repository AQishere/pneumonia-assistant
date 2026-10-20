"use client";

import { FirebaseError } from "firebase/app";
import { createUserWithEmailAndPassword, signInWithEmailAndPassword } from "firebase/auth";
import { HeartPulse } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/lib/auth-context";
import { firebaseAuth, firebaseConfigured } from "@/lib/firebase";

const FRIENDLY: Record<string, string> = {
  "auth/invalid-credential": "Email or password is incorrect.",
  "auth/email-already-in-use": "An account with this email already exists. Sign in instead.",
  "auth/weak-password": "Use a password of at least 6 characters.",
  "auth/invalid-email": "Enter a valid email address.",
  "auth/too-many-requests": "Too many attempts. Please wait a moment and try again.",
};

export default function LoginPage() {
  const { user, me, loading, refresh } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && user && me) router.replace(me.role ? (me.role === "doctor" ? "/doctor" : "/dashboard") : "/onboarding");
  }, [loading, user, me, router]);

  async function submit(mode: "signin" | "signup") {
    setBusy(true);
    setError(null);
    try {
      if (mode === "signin") await signInWithEmailAndPassword(firebaseAuth(), email, password);
      else await createUserWithEmailAndPassword(firebaseAuth(), email, password);
      await refresh();
      router.replace("/");
    } catch (e) {
      setError(e instanceof FirebaseError ? (FRIENDLY[e.code] ?? e.message) : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const fields = (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="email">Email</Label>
        <Input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
    </div>
  );

  return (
    <main className="flex flex-1 items-center justify-center px-4 py-10">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <div className="mb-2 flex items-center gap-2">
            <HeartPulse className="size-6 text-red-600" aria-hidden />
            <CardTitle>Pneumonia Risk Assistant</CardTitle>
          </div>
          <CardDescription>Keep an eye on your chest health with your devices and lab results.</CardDescription>
        </CardHeader>
        <CardContent>
          {!firebaseConfigured && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>Firebase is not configured. Fill in .env.local (see .env.local.example).</AlertDescription>
            </Alert>
          )}
          <Tabs defaultValue="signin">
            <TabsList className="mb-4 grid w-full grid-cols-2">
              <TabsTrigger value="signin">Sign in</TabsTrigger>
              <TabsTrigger value="signup">Create account</TabsTrigger>
            </TabsList>
            <TabsContent value="signin" className="space-y-4">
              {fields}
              <Button className="w-full" disabled={busy} onClick={() => submit("signin")}>
                Sign in
              </Button>
            </TabsContent>
            <TabsContent value="signup" className="space-y-4">
              {fields}
              <Button className="w-full" disabled={busy} onClick={() => submit("signup")}>
                Create my account
              </Button>
            </TabsContent>
          </Tabs>
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>
    </main>
  );
}
