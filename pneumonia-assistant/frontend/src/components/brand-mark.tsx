import { Plus } from "lucide-react";

import { cn } from "@/lib/utils";

/** The app's logo: a white cross on a coral circle (matches src/app/icon.svg). */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground",
        className,
      )}
      aria-hidden
    >
      <Plus className="size-[60%]" strokeWidth={3} />
    </span>
  );
}
