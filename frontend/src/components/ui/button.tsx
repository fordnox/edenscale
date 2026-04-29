import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "@radix-ui/react-slot"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2 whitespace-nowrap",
    "font-sans font-medium tracking-tight select-none",
    "transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
    "outline-none focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
    "disabled:cursor-not-allowed disabled:opacity-60",
    "[&_svg]:size-4 [&_svg]:stroke-[1.5] [&_svg]:shrink-0",
  ].join(" "),
  {
    variants: {
      variant: {
        primary:
          "bg-conifer-700 text-parchment-50 hover:bg-conifer-800 active:bg-conifer-900 rounded-xs",
        secondary:
          "bg-transparent text-ink-900 border border-[var(--border-default)] hover:bg-parchment-200 rounded-xs",
        ghost:
          "bg-transparent text-ink-900 hover:bg-parchment-200 rounded-xs",
        link:
          "bg-transparent text-ink-900 px-0 py-0 rounded-none border-b border-brass-500 pb-0.5 hover:text-conifer-700",
        inverse:
          "bg-parchment-50 text-ink-900 hover:bg-parchment-200 rounded-xs",
      },
      size: {
        sm: "px-4 py-2 text-[13px]",
        md: "px-5 py-3 text-[14px]",
        lg: "px-6 py-3.5 text-[15px]",
        icon: "p-2",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
    compoundVariants: [
      { variant: "link", size: "sm", className: "px-0 py-0" },
      { variant: "link", size: "md", className: "px-0 py-0" },
      { variant: "link", size: "lg", className: "px-0 py-0" },
    ],
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export function Button({
  className,
  variant,
  size,
  asChild,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : "button"
  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  )
}
