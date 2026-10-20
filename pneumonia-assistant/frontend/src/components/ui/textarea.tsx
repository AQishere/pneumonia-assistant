import * as React from "react"
import { cn } from "cn"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-16 w-full rounded-xl px-3 py-2 border border-input bg-background text-sm transition-[border-color,box-shadow] outline-none placeholder:text-muted-foreground hover:border-input-hover focus-visible:border-primary focus-visible:ring-3 focus-visible:ring-primary/15 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-50 aria-invalid:border-destructive aria-invalid:bg-[#fff5f5] aria-invalid:ring-3 aria-invalid:ring-destructive/15",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
