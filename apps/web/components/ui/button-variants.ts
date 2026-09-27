import { cva, type VariantProps } from "class-variance-authority"
import { extendTailwindMerge } from "tailwind-merge"

const buttonVariantClasses = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 data-disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive",
  {
    variants: {
      variant: {
        default:
          "bg-[linear-gradient(135deg,var(--primary-gradient-from),var(--primary-gradient-to))] text-primary-foreground hover:opacity-90",
        destructive:
          "bg-destructive text-white hover:bg-destructive/90 focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40 dark:bg-destructive/60",
        "destructive-outline":
          "border border-destructive/40 bg-background text-destructive shadow-xs hover:bg-destructive/10 hover:text-destructive focus-visible:border-destructive focus-visible:ring-destructive/20 dark:border-destructive/50 dark:bg-input/30 dark:hover:bg-destructive/20 dark:focus-visible:ring-destructive/40",
        "destructive-ghost":
          "text-destructive hover:bg-destructive/10 hover:text-destructive focus-visible:ring-destructive/20 dark:hover:bg-destructive/20 dark:focus-visible:ring-destructive/40",
        success:
          "bg-success text-success-foreground hover:bg-success/90 focus-visible:ring-success/30 dark:bg-success/60 dark:focus-visible:ring-success/40",
        outline:
          "border bg-background shadow-xs hover:bg-accent hover:text-accent-foreground dark:bg-input/30 dark:border-input dark:hover:bg-input/50",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost:
          "hover:bg-accent hover:text-accent-foreground dark:hover:bg-accent/50",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2 has-[>svg]:px-3",
        sm: "h-8 rounded-md gap-1.5 px-3 has-[>svg]:px-2.5",
        lg: "h-10 rounded-md px-6 has-[>svg]:px-4",
        icon: "size-9",
        "icon-sm": "size-8",
        "icon-lg": "size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

// The default variant paints a gradient with background-image, which covers any background-color.
// On buttons only, a later bg color class (for example a className "bg-destructive") also removes
// the gradient, so the color the caller asked for shows. New code picks a variant instead.
const mergeButtonClasses = extendTailwindMerge({
  extend: {
    conflictingClassGroups: {
      "bg-color": ["bg-image"],
    },
  },
})

type ButtonVariantProps = VariantProps<typeof buttonVariantClasses>

function buttonVariants(props?: Parameters<typeof buttonVariantClasses>[0]): string {
  return mergeButtonClasses(buttonVariantClasses(props))
}

export { buttonVariants, type ButtonVariantProps }
