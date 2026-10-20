import type { Metadata } from "next";
import Link from "next/link";

import { BrandMark } from "@/components/brand-mark";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Page not found",
  description: "This page doesn't exist or has moved.",
};

/** Shown for any URL that doesn't match a page. "/" sends people to their summary or to sign in. */
export default function NotFound() {
  return (
    <main className="flex flex-1 items-center justify-center px-4 py-16">
      <div className="w-full max-w-md text-center">
        <Link href="/" aria-label="Pneumonia Assistant home" className="inline-block">
          <BrandMark className="size-14" />
        </Link>
        <p className="mt-6 text-sm font-medium text-primary">Error 404</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">Page not found</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you&apos;re looking for doesn&apos;t exist or has moved. Check the address, or go back to your
          summary.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Button asChild>
            <Link href="/">Go to my summary</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/chat">Ask the assistant</Link>
          </Button>
        </div>
      </div>
    </main>
  );
}
