"use client";

import {
  ChartLine,
  FlaskConical,
  House,
  LogOut,
  Menu,
  MessageCircle,
  RefreshCw,
  TriangleAlert,
  UserRound,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Dialog } from "radix-ui";
import { useEffect, useState } from "react";

import { BrandMark } from "@/components/brand-mark";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

type NavItem = { href: string; label: string; icon: LucideIcon };

const PATIENT_NAV: { title: string; items: NavItem[] }[] = [
  {
    title: "Overview",
    items: [
      { href: "/dashboard", label: "Summary", icon: House },
      { href: "/chat", label: "Assistant", icon: MessageCircle },
      { href: "/history", label: "History", icon: ChartLine },
    ],
  },
  {
    title: "Account",
    items: [
      { href: "/profile", label: "Profile", icon: UserRound },
      { href: "/demo", label: "Demo Test", icon: FlaskConical },
    ],
  },
];
const DOCTOR_NAV = [{ title: "Overview", items: [{ href: "/doctor", label: "My patients", icon: Users }] }];

/** Wraps signed-in pages: sends users to login or onboarding when needed.
 *  Desktop: a full-height sidebar. Phones: a top bar whose menu button opens the same sidebar as a drawer. */
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

  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPath, setMenuPath] = useState(pathname);
  // Following a link in the mobile menu closes it.
  if (menuPath !== pathname) {
    setMenuPath(pathname);
    setMenuOpen(false);
  }

  const groups = role === "doctor" ? DOCTOR_NAV : PATIENT_NAV;
  const home = role === "doctor" ? "/doctor" : "/dashboard";
  const ready = !loading && user && me?.role === role;
  const name = me?.profile?.display_name ?? user?.email ?? "";

  return (
    <div className="flex min-h-full flex-1">
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 border-r bg-card lg:block">
        <SidebarContent role={role} groups={groups} pathname={pathname} name={name} onSignOut={logout} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b bg-card/95 px-2 backdrop-blur lg:hidden">
          <Dialog.Root open={menuOpen} onOpenChange={setMenuOpen}>
            <Dialog.Trigger
              aria-label="Open menu"
              className="flex size-10 items-center justify-center rounded-md text-foreground hover:bg-muted"
            >
              <Menu className="size-5" />
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
              <Dialog.Content className="fixed inset-y-0 left-0 z-50 w-72 max-w-[85vw] border-r bg-card shadow-lg outline-none data-[state=closed]:animate-out data-[state=closed]:slide-out-to-left data-[state=open]:animate-in data-[state=open]:slide-in-from-left">
                <Dialog.Title className="sr-only">Menu</Dialog.Title>
                <Dialog.Description className="sr-only">Go to another page or sign out.</Dialog.Description>
                <Dialog.Close
                  aria-label="Close menu"
                  className="absolute top-3.5 right-3 flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  <X className="size-5" />
                </Dialog.Close>
                <SidebarContent role={role} groups={groups} pathname={pathname} name={name} onSignOut={logout} />
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
          <Link href={home} className="flex min-w-0 items-center gap-2" aria-label="Pneumonia Assistant home">
            <BrandMark className="size-7" />
            <span className="truncate text-[15px] font-semibold">Pneumonia Assistant</span>
          </Link>
        </header>
        <main className="mx-auto w-full max-w-[1400px] min-w-0 flex-1 px-4 pt-6 pb-10 sm:px-6 lg:px-8 lg:pt-8">
          {error && <ErrorState message={`The server isn't responding: ${error}`} />}
          {ready ? children : !error && <PageSkeleton />}
          <footer className="mt-10 flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t pt-4 text-xs text-muted-foreground">
            <p>
              Guidance only. This app cannot diagnose pneumonia or replace a doctor. In an emergency, call{" "}
              <a
                href="tel:1122"
                className="font-medium text-foreground underline underline-offset-2 hover:text-primary"
              >
                Rescue 1122
              </a>
              .
            </p>
            {role === "patient" && (
              <Link href="/chat" className="font-medium text-primary hover:underline">
                Questions? Ask the assistant
              </Link>
            )}
          </footer>
        </main>
      </div>
    </div>
  );
}

/** Logo, navigation and the signed-in user: the desktop sidebar, and the mobile menu drawer. */
function SidebarContent({
  role,
  groups,
  pathname,
  name,
  onSignOut,
}: {
  role: "patient" | "doctor";
  groups: { title: string; items: NavItem[] }[];
  pathname: string;
  name: string;
  onSignOut: () => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <Link
        href={role === "doctor" ? "/doctor" : "/dashboard"}
        className="flex h-16 shrink-0 items-center gap-2.5 border-b px-5"
        aria-label="Pneumonia Assistant home"
      >
        <BrandMark className="size-8" />
        <span className="leading-tight">
          <span className="block text-[15px] font-semibold">Pneumonia Assistant</span>
          <span className="block text-xs text-muted-foreground">
            {role === "doctor" ? "Clinician portal" : "Patient portal"}
          </span>
        </span>
      </Link>

      <nav className="flex flex-1 flex-col gap-8 overflow-y-auto px-3 py-6" aria-label="Main">
        {groups.map((group) => (
          <div key={group.title}>
            <p className="mb-2 px-3 text-xs font-medium text-muted-foreground">{group.title}</p>
            <div className="flex flex-col gap-1.5">
              {group.items.map((item) => {
                const active = pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex h-11 items-center gap-3 rounded-lg px-3 text-sm transition-colors lg:h-10",
                      active
                        ? "bg-accent font-medium text-accent-foreground"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}
                  >
                    <item.icon className={cn("size-4 shrink-0", active && "text-primary")} />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="shrink-0 border-t p-3">
        <div className="flex items-center gap-2.5 rounded-lg px-2 py-1.5">
          <Avatar name={name} className="size-8" />
          <div className="min-w-0 flex-1 leading-tight">
            <p className="truncate text-sm font-medium">{name}</p>
            <p className="text-xs text-muted-foreground capitalize">{role}</p>
          </div>
          <button
            onClick={onSignOut}
            aria-label="Sign out"
            title="Sign out"
            className="flex size-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

/** A friendly error with a way to try again (reloads the page). */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="mb-6 flex flex-col items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-5 sm:flex-row sm:items-center"
    >
      <TriangleAlert className="size-5 shrink-0 text-red-600" aria-hidden />
      <div className="min-w-0 flex-1 text-sm">
        <p className="font-semibold text-red-800">Something went wrong</p>
        <p className="text-red-900/80">{message}</p>
      </div>
      <Button variant="outline" size="sm" onClick={onRetry ?? (() => window.location.reload())}>
        <RefreshCw className="size-3.5" /> Try again
      </Button>
    </div>
  );
}

/** Initials in a circle, like a contact photo placeholder. */
export function Avatar({ name, className }: { name: string; className?: string }) {
  const initials = name
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");
  return (
    <span
      className={cn(
        "flex size-8 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground",
        className,
      )}
      aria-hidden
    >
      {initials || "?"}
    </span>
  );
}

/** Page title with an optional small line above it and an action on the right. */
export function PageHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4 lg:mb-8">
      <div>
        {eyebrow && <p className="text-sm text-muted-foreground">{eyebrow}</p>}
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      </div>
      {children}
    </div>
  );
}

/** A section title inside a page. */
export function SectionTitle({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-baseline justify-between">
      <h2 className="text-base font-semibold">{children}</h2>
      {action}
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-56 rounded-xl" />
      <Skeleton className="h-36 w-full rounded-2xl" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-36 rounded-2xl" />
        ))}
      </div>
    </div>
  );
}
