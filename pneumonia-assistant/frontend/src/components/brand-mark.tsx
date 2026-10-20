import Image from "next/image";

import { cn } from "@/lib/utils";

/** The app's logo: blue lungs crossed by a teal-to-coral breathing line, background removed (public/logo-lungs.png). */
export function BrandMark({ className }: { className?: string }) {
  return (
    <Image
      src="/logo-lungs.png"
      alt=""
      aria-hidden
      width={128}
      height={128}
      className={cn("inline-block size-7 shrink-0 object-contain", className)}
    />
  );
}
