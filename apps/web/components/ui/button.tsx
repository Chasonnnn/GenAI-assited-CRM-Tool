import * as React from "react"
import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { useRender } from "@base-ui/react/use-render"

import { buttonVariants, type ButtonVariantProps } from "@/components/ui/button-variants"
import { cn } from "@/lib/utils"

type ButtonProps = Omit<ButtonPrimitive.Props, "className" | "render"> &
  ButtonVariantProps & {
    className?: string | undefined
    render?: React.ReactElement | undefined
    unstyled?: boolean | undefined
  }

/**
 * Button component with variants.
 *
 * For Base UI triggers, avoid nesting <Button>. Prefer passing a non-button wrapper
 * as children and apply `buttonVariants` to the trigger element.
 */
function RenderedButtonSurface({
  className,
  variant = "default",
  size = "default",
  render,
  unstyled = false,
  nativeButton: _nativeButton,
  focusableWhenDisabled: _focusableWhenDisabled,
  ...props
}: ButtonProps) {
  return useRender({
    defaultTagName: "button",
    render,
    props: {
      ...props,
      className: unstyled ? className : cn(buttonVariants({ variant, size, className })),
    },
    state: {
      slot: "button",
      variant,
      size,
    },
  })
}

function Button(props: ButtonProps) {
  if (props.render !== undefined) {
    return <RenderedButtonSurface {...props} />
  }

  const {
    className,
    variant = "default",
    size = "default",
    nativeButton,
    unstyled = false,
    ...buttonProps
  } = props

  return (
    <ButtonPrimitive
      data-slot="button"
      className={unstyled ? className : cn(buttonVariants({ variant, size, className }))}
      nativeButton={nativeButton}
      {...buttonProps}
    />
  )
}

export { Button }
