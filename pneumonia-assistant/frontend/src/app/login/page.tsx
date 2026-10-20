"use client";

import { FirebaseError } from "firebase/app";
import {
  browserLocalPersistence,
  browserSessionPersistence,
  createUserWithEmailAndPassword,
  sendPasswordResetEmail,
  setPersistence,
  signInWithEmailAndPassword,
} from "firebase/auth";
import { Activity, CircleCheck, Droplet, Eye, EyeOff, Heart, Mail, Stethoscope, Thermometer, Wind } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { BrandMark } from "@/components/brand-mark";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth-context";
import { firebaseAuth, firebaseConfigured } from "@/lib/firebase";
import { cn } from "@/lib/utils";

const FRIENDLY: Record<string, string> = {
  "auth/invalid-credential": "Email or password is incorrect.",
  "auth/email-already-in-use": "An account with this email already exists. Sign in instead.",
  "auth/weak-password": "Use a password of at least 6 characters.",
  "auth/invalid-email": "Enter a valid email address.",
  "auth/missing-email": "Enter your email address first.",
  "auth/too-many-requests": "Too many attempts. Please wait a moment and try again.",
};

const friendly = (e: unknown) =>
  e instanceof FirebaseError ? (FRIENDLY[e.code] ?? e.message) : "Something went wrong.";

export default function LoginPage() {
  const { user, me, loading, refresh } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && user && me)
      router.replace(me.role ? (me.role === "doctor" ? "/doctor" : "/dashboard") : "/onboarding");
  }, [loading, user, me, router]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const auth = firebaseAuth();
      // "Keep me signed in" off: the session ends when the browser closes.
      await setPersistence(auth, remember ? browserLocalPersistence : browserSessionPersistence);
      if (mode === "signin") await signInWithEmailAndPassword(auth, email, password);
      else await createUserWithEmailAndPassword(auth, email, password);
      await refresh();
      toast.success(mode === "signin" ? "Signed in." : "Account created. Let's set up your profile.");
      router.replace("/");
    } catch (e) {
      setError(friendly(e));
    } finally {
      setBusy(false);
    }
  }

  async function resetPassword() {
    setError(null);
    try {
      await sendPasswordResetEmail(firebaseAuth(), email);
      toast.success(`If an account exists for ${email}, a reset link is on its way.`);
    } catch (e) {
      setError(friendly(e));
    }
  }

  const signin = mode === "signin";

  return (
    <main className="relative grid flex-1 grid-cols-1 overflow-hidden bg-card lg:grid-cols-2">
      <Backdrop />
      <section className="relative hidden items-center justify-center p-10 lg:flex">
        <PhoneScene />
      </section>

      <section className="relative flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="mb-10 flex flex-col items-center text-center">
            <Link href="/" aria-label="Pneumonia Assistant home" className="rounded-xl">
              <BrandMark className="size-24" />
            </Link>
            <p className="mt-3 text-sm font-bold tracking-[0.2em] uppercase">Pneumonia Assistant</p>
            <p className="text-[12px] tracking-[0.15em] text-muted-foreground uppercase">Breathe easy</p>
          </div>

          <h1 className="text-[32px] font-bold tracking-tight">{signin ? "Sign In" : "Create account"}</h1>
          <p className="mt-1 text-[15px] text-muted-foreground">
            Welcome to <span className="font-semibold text-primary">Pneumonia Assistant</span>.{" "}
            {signin ? "Enter your details to sign in." : "Enter an email and a password to get started."}
          </p>

          {!firebaseConfigured && (
            <Alert variant="destructive" className="mt-4">
              <AlertDescription>
                Firebase is not configured. Fill in .env.local (see .env.local.example).
              </AlertDescription>
            </Alert>
          )}

          <form
            className="mt-8 space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
          >
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <div className="relative">
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="h-11 pr-11"
                />
                <Mail className="pointer-events-none absolute top-1/2 right-3.5 size-4 -translate-y-1/2 text-muted-foreground" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete={signin ? "current-password" : "new-password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="h-11 pr-11"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute top-1/2 right-1.5 flex size-8 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <Eye className="size-4" /> : <EyeOff className="size-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between pt-1">
              <label className="flex cursor-pointer items-center gap-2 text-sm font-medium">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  className="size-4 cursor-pointer rounded accent-primary"
                />
                Keep me signed in
              </label>
              {signin && (
                <button
                  type="button"
                  onClick={resetPassword}
                  className="text-sm font-semibold text-primary hover:underline"
                >
                  Forgot password?
                </button>
              )}
            </div>

            {error && (
              <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
                {error}
              </p>
            )}

            <Button type="submit" size="lg" className="mt-2 h-11 w-full" disabled={busy}>
              {busy ? "Please wait…" : signin ? "Sign In" : "Create my account"}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm font-medium">
            {signin ? "Don't have an account? " : "Already have an account? "}
            <button
              type="button"
              onClick={() => {
                setMode(signin ? "signup" : "signin");
                setError(null);
              }}
              className="font-semibold text-primary hover:underline"
            >
              {signin ? "Sign Up" : "Sign In"}
            </button>
          </p>
        </div>
      </section>
    </main>
  );
}

/** Faint plus shapes and soft arcs behind the page. */
function Backdrop() {
  return (
    <div className="pointer-events-none absolute inset-0" aria-hidden>
      <Plus className="top-[8%] left-[6%] hidden size-72 lg:block" />
      <Plus className="-bottom-[6%] -left-[10%] size-56 lg:left-[18%]" />
      <Plus className="top-[30%] left-[38%] hidden size-60 lg:block" />
      <div className="absolute -right-28 -bottom-28 size-80 rounded-full border-[36px] border-primary/10" />
      <svg viewBox="0 0 200 200" className="absolute top-10 right-[30%] hidden size-40 text-primary/15 lg:block">
        <path d="M20 180 C 60 40, 120 160, 180 20" fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
    </div>
  );
}

function Plus({ className }: { className: string }) {
  return (
    <svg viewBox="0 0 100 100" className={cn("absolute text-[#f2f2f7]", className)}>
      <path
        d="M35 5h30v30h30v30H65v30H35V65H5V35h30z"
        fill="none"
        stroke="currentColor"
        strokeWidth="6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const BUBBLES = [
  { icon: Heart, color: "#e11d48", pos: "top-[6%] left-[4%] size-24", delay: "0s" },
  { icon: Wind, color: "#0891b2", pos: "top-[24%] right-[2%] size-16", delay: "0.6s" },
  { icon: Thermometer, color: "#ea580c", pos: "bottom-[16%] left-[2%] size-20", delay: "1.2s" },
  { icon: Droplet, color: "#1d4ed8", pos: "bottom-[8%] right-[8%] size-18", delay: "1.8s" },
];

/** A phone showing a mini Summary screen, inside dashed orbit rings with floating health icons. */
function PhoneScene() {
  return (
    <div className="relative aspect-square w-full max-w-[560px]">
      <div className="absolute inset-[4%] rounded-full border-2 border-dashed border-primary/25" />
      <div className="absolute inset-[16%] rounded-full border-2 border-dashed border-primary/20" />
      <div className="absolute inset-[26%] rounded-full bg-primary/10 blur-2xl" />

      {BUBBLES.map(({ icon: Icon, color, pos, delay }) => (
        <div
          key={color}
          className={cn(
            "absolute flex animate-float items-center justify-center rounded-full bg-card shadow-lg ring-4 ring-card",
            pos,
          )}
          style={{ animationDelay: delay }}
        >
          <span
            className="flex size-[78%] items-center justify-center rounded-full"
            style={{ backgroundColor: `${color}1f` }}
          >
            <Icon className="size-[45%] fill-current" style={{ color }} />
          </span>
        </div>
      ))}

      <div className="absolute top-1/2 left-1/2 h-[82%] w-[42%] -translate-x-1/2 -translate-y-1/2 rounded-[2.6rem] bg-[#1c1c1e] p-2 shadow-2xl">
        <div className="relative h-full overflow-hidden rounded-[2.1rem] bg-background">
          <div className="absolute top-2 left-1/2 h-5 w-20 -translate-x-1/2 rounded-full bg-[#1c1c1e]" />
          <div className="flex items-center justify-between px-5 pt-2.5 text-[10px] font-semibold">
            <span>9:41</span>
            <span>●●●</span>
          </div>
          <div className="space-y-2 px-3 pt-6">
            <div className="flex items-center gap-1.5 pb-1">
              <BrandMark className="size-5" />
              <span className="text-[9px] font-bold tracking-[0.15em] uppercase">Pneumonia Assistant</span>
            </div>
            <p className="text-[8px] font-semibold text-muted-foreground uppercase">Monday, 19 October</p>
            <p className="text-base leading-none font-bold">Hello, Sara</p>
            <div
              className="rounded-xl bg-card p-2.5 shadow-sm"
              style={{ backgroundImage: "linear-gradient(135deg, #16a34a26, transparent 60%)" }}
            >
              <div className="flex items-center gap-2">
                <span className="flex size-7 items-center justify-center rounded-full bg-[#16a34a] text-white">
                  <CircleCheck className="size-4" />
                </span>
                <div className="leading-tight">
                  <p className="text-[10px] font-bold">No concern right now</p>
                  <p className="text-[7px] text-muted-foreground">Your latest check found no signs of concern.</p>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {[
                { icon: Heart, color: "#e11d48", label: "Heart rate", value: "72", unit: "bpm" },
                { icon: Droplet, color: "#1d4ed8", label: "Oxygen", value: "98", unit: "%" },
                { icon: Wind, color: "#0891b2", label: "Breathing", value: "15", unit: "/min" },
                { icon: Activity, color: "#dc2626", label: "Pressure", value: "124", unit: "mmHg" },
              ].map(({ icon: Icon, color, label, value, unit }) => (
                <div key={label} className="rounded-xl bg-card p-2 shadow-sm">
                  <p className="flex items-center gap-1 text-[8px] font-semibold" style={{ color }}>
                    <Icon className="size-2.5" /> {label}
                  </p>
                  <p className="mt-2 text-sm leading-none font-semibold">
                    {value}
                    <span className="ml-0.5 text-[7px] text-muted-foreground">{unit}</span>
                  </p>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-2 rounded-xl bg-card p-2 shadow-sm">
              <span className="flex size-6 items-center justify-center rounded-md bg-[#16a34a] text-white">
                <Stethoscope className="size-3.5" />
              </span>
              <p className="text-[9px] font-semibold">Run a check</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
