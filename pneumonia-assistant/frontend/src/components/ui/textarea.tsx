import * as React from "react"
import { cn } from "cn"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-16 w-full rounded-2xl px-4 py-3 border-2 border-input bg-background text-base transition-[border-color,box-shadow] outline-none placeholder:text-muted-foreground hover:border-input-hover focus-visible:border-3 focus-visible:border-primary focus-visible:ring-4 focus-visible:ring-primary/25 disabled:pointer-events-none disabled:cursor-not-allowed disabled:border-2 disabled:border-input disabled:bg-muted disabled:opacity-50 aria-invalid:border-3 aria-invalid:border-destructive aria-invalid:bg-[#fff5f5] aria-invalid:ring-4 aria-invalid:ring-destructive/20",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
