import { Suspense } from "react";

import { AppShell, PageSkeleton } from "@/components/app-shell";

// The shell reads the URL (usePathname), so it sits inside Suspense for prerendering.
export default function PatientLayout({ children }: LayoutProps<"/">) {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <AppShell role="patient">{children}</AppShell>
    </Suspense>
  );
}
