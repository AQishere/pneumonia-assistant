import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 cursor-pointer items-center justify-center rounded-full border-transparent bg-clip-padding font-semibold whitespace-nowrap transition-all duration-200 outline-none select-none focus-visible:ring-4 focus-visible:ring-ring/25 active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none aria-invalid:ring-4 aria-invalid:ring-destructive/20 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-5",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow-coral hover:bg-primary-hover",
        outline:
          "border-3 border-primary bg-transparent text-primary hover:bg-primary/15 aria-expanded:bg-primary/15",
        secondary:
          "bg-secondary text-secondary-foreground shadow-teal hover:bg-secondary-hover aria-expanded:bg-secondary-hover",
        ghost: "text-primary hover:bg-primary/15 aria-expanded:bg-primary/15",
        destructive: "bg-destructive text-white hover:bg-[#dc2626] focus-visible:ring-destructive/25",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-12 gap-2 px-7 text-base",
        xs: "h-10 gap-1.5 px-4 text-sm [&_svg:not([class*='size-'])]:size-4",
        sm: "h-10 gap-1.5 px-5 text-sm [&_svg:not([class*='size-'])]:size-4",
        lg: "h-14 gap-2 px-9 text-lg [&_svg:not([class*='size-'])]:size-6",
        icon: "size-12",
        "icon-xs": "size-10 [&_svg:not([class*='size-'])]:size-4",
        "icon-sm": "size-11",
        "icon-lg": "size-14 [&_svg:not([class*='size-'])]:size-6",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
