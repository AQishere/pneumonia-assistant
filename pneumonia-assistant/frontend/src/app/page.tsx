"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { PageSkeleton } from "@/components/app-shell";
import { useAuth } from "@/lib/auth-context";

export default function Home() {
  const { user, me, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    else if (!me?.role) router.replace("/onboarding");
    else router.replace(me.role === "doctor" ? "/doctor" : "/dashboard");
  }, [loading, user, me, router]);

  return (
    <main className="w-full px-4 py-8 sm:px-6 lg:px-10">
      <PageSkeleton />
    </main>
  );
}
