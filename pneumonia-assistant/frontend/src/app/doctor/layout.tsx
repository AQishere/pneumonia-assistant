import { Suspense } from "react";

import { AppShell, PageSkeleton } from "@/components/app-shell";

// The shell and patient pages read the URL, so they sit inside Suspense for prerendering.
export default function DoctorLayout({ children }: LayoutProps<"/doctor">) {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <AppShell role="doctor">{children}</AppShell>
    </Suspense>
  );
}
