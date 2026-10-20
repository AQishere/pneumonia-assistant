"use client";

import { LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { BrandMark } from "@/components/brand-mark";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

const PATIENT_NAV = [
  { href: "/dashboard", label: "Home" },
  { href: "/chat", label: "Assistant" },
  { href: "/history", label: "History" },
  { href: "/profile", label: "Profile" },
  { href: "/demo", label: "Demo Test" },
];
const DOCTOR_NAV = [{ href: "/doctor", label: "My patients" }];

/** Wraps signed-in pages: sends users to login or onboarding when needed. */
export function AppShell({ children, role }: { children: React.ReactNode; role: "patient" | "doctor" }) {
  const { user, me, loading, error, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    else if (me && !me.role) router.replace("/onboarding");
    else if (me?.role && me.role !== role) router.replace(me.role === "doctor" ? "/doctor" : "/dashboard");
  }, [loading, user, me, role, router]);

  const nav = role === "doctor" ? DOCTOR_NAV : PATIENT_NAV;
  const ready = !loading && user && me?.role === role;

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-30 border-b bg-background/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-2.5">
          <Link href={role === "doctor" ? "/doctor" : "/dashboard"} className="flex shrink-0 items-center gap-2 font-semibold">
            <BrandMark className="size-7" />
            <span>Pneumonia Risk Assistant</span>
          </Link>
          <nav className="flex flex-1 gap-1 overflow-x-auto [scrollbar-width:none]">
            {nav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex min-h-8 items-center rounded-full px-3 text-sm font-medium whitespace-nowrap text-muted-foreground transition-colors duration-200 hover:bg-[#fff5f5] hover:text-foreground",
                  pathname.startsWith(item.href) && "bg-primary/10 text-primary hover:bg-primary/10 hover:text-primary",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <Button variant="ghost" size="sm" onClick={() => logout()} aria-label="Sign out">
            <LogOut className="size-4" />
            <span className="hidden sm:inline">Sign out</span>
          </Button>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">
        {error && <p className="mb-4 text-sm text-destructive">Server problem: {error}</p>}
        {ready ? children : <PageSkeleton />}
      </main>
      <footer className="border-t px-4 py-4 text-center text-xs text-muted-foreground">
        Guidance only. This app cannot diagnose pneumonia or replace a doctor. In an emergency, call Rescue 1122.
      </footer>
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-48 w-full" />
    </div>
  );
}
