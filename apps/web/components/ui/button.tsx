import * as React from "react"
import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"

import { buttonVariants, type ButtonVariantProps } from "@/components/ui/button-variants"
import { cn } from "@/lib/utils"

interface ButtonProps
  extends useRender.ComponentProps<"button">,
  React.ComponentProps<"button">,
  ButtonVariantProps {}

/**
 * Button component with variants.
 *
 * For Base UI triggers, avoid nesting <Button>. Prefer passing a non-button wrapper
 * as children and apply `buttonVariants` to the trigger element.
 */
function Button({
  className,
  variant = "default",
  size = "default",
  render,
  ...props
}: ButtonProps) {
  const renderProp = render === undefined ? {} : { render }
  return useRender({
    defaultTagName: "button",
    props: mergeProps<"button">(
      {
        className: cn(buttonVariants({ variant, size, className })),
      },
      props
    ),
    state: {
      slot: "button",
      variant,
      size,
    },
    ...renderProp,
  })
}

export { Button }
