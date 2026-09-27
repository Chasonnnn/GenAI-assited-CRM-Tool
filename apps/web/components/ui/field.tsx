"use client"

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from '@/lib/utils'
import { Label } from '@/components/ui/label'

function FieldGroup({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="field-group"
      className={cn(
        "gap-7 data-[slot=checkbox-group]:gap-3 [&>[data-slot=field-group]]:gap-4 group/field-group @container/field-group flex w-full flex-col",
        className
      )}
      {...props}
    />
  )
}

const fieldVariants = cva("gap-3 group/field flex w-full", {
  variants: {
    orientation: {
      vertical:
        "flex-col [&>*]:w-full [&>.sr-only]:w-auto",
      horizontal:
        "flex-row items-center [&>[data-slot=field-label]]:flex-auto has-[>[data-slot=field-content]]:items-start has-[>[data-slot=field-content]]:[&>[role=checkbox],[role=radio]]:mt-px",
      responsive:
        "flex-col [&>*]:w-full [&>.sr-only]:w-auto @md/field-group:flex-row @md/field-group:items-center @md/field-group:[&>*]:w-auto @md/field-group:[&>[data-slot=field-label]]:flex-auto @md/field-group:has-[>[data-slot=field-content]]:items-start @md/field-group:has-[>[data-slot=field-content]]:[&>[role=checkbox],[role=radio]]:mt-px",
    },
  },
  defaultVariants: {
    orientation: "vertical",
  },
})

function Field({
  className,
  orientation = "vertical",
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof fieldVariants>) {
  return (
    <div
      role="group"
      data-slot="field"
      data-orientation={orientation}
      className={cn(fieldVariants({ orientation }), className)}
      {...props}
    />
  )
}

function FieldLabel({
  className,
  ...props
}: React.ComponentProps<typeof Label>) {
  return (
    <Label
      data-slot="field-label"
      className={cn(
        "has-data-checked:bg-primary/5 has-data-checked:border-primary/50 dark:has-data-checked:bg-primary/10 gap-2 group-data-[disabled=true]/field:opacity-50 group-data-[invalid=true]/field:text-destructive has-[>[data-slot=field]]:rounded-xl has-[>[data-slot=field]]:border [&>*]:data-[slot=field]:p-4 group/field-label peer/field-label flex w-fit leading-snug",
        "has-[>[data-slot=field]]:w-full has-[>[data-slot=field]]:flex-col",
        className
      )}
      {...props}
    />
  )
}

function FieldDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="field-description"
      className={cn(
        "text-muted-foreground text-left text-sm [[data-variant=legend]+&]:-mt-1.5 leading-normal font-normal group-has-[[data-orientation=horizontal]]/field:text-balance",
        "last:mt-0 nth-last-2:-mt-1",
        "[&>a:hover]:text-primary [&>a]:underline [&>a]:underline-offset-4",
        className
      )}
      {...props}
    />
  )
}

function FieldError({
  className,
  children,
  errors,
  ...props
}: React.ComponentProps<"div"> & {
  errors?: Array<{ message?: string } | undefined>
}) {
  const uniqueErrors = children ? [] : getUniqueErrors(errors)
  const content =
    children ??
    (uniqueErrors.length === 1 ? (
      uniqueErrors[0]?.message
    ) : uniqueErrors.length > 1 ? (
      <ul className="ml-4 flex list-disc flex-col gap-1">
        {uniqueErrors.map((error) => (
          <li key={error.message}>{error.message}</li>
        ))}
      </ul>
    ) : null)

  if (!content) {
    return null
  }

  return (
    <div
      role="alert"
      data-slot="field-error"
      className={cn("text-destructive text-sm font-normal", className)}
      {...props}
    >
      {content}
    </div>
  )
}

function getUniqueErrors(errors: Array<{ message?: string } | undefined> | undefined) {
  if (!errors?.length) return []
  const uniqueErrors = new Map<string, { message: string }>()
  for (const error of errors) {
    if (error?.message && !uniqueErrors.has(error.message)) {
      uniqueErrors.set(error.message, { message: error.message })
    }
  }
  return Array.from(uniqueErrors.values())
}

type FieldControlProps = {
  id: string
  "aria-invalid": true | undefined
  "aria-describedby": string | undefined
}

/**
 * Label, control and inline error with the accessibility wiring in one place.
 * Spread the render argument onto the control: `{(control) => <Input {...control} />}`.
 */
function ValidatedField({
  label,
  error,
  description,
  id,
  className,
  orientation,
  children,
}: {
  label: React.ReactNode
  /** Message shown under the control; the field is invalid while it is set. */
  error?: string | null | undefined
  /** Only for text that prevents an error, such as a required format. */
  description?: React.ReactNode
  id?: string | undefined
  className?: string | undefined
  orientation?: VariantProps<typeof fieldVariants>["orientation"]
  children: (control: FieldControlProps) => React.ReactNode
}) {
  const generatedId = React.useId()
  const controlId = id ?? generatedId
  const invalid = Boolean(error)
  const descriptionId = description ? `${controlId}-description` : undefined
  const errorId = invalid ? `${controlId}-error` : undefined
  const describedBy = [descriptionId, errorId].filter(Boolean).join(" ") || undefined

  return (
    <Field
      data-invalid={invalid ? true : undefined}
      orientation={orientation}
      className={className}
    >
      <FieldLabel htmlFor={controlId}>{label}</FieldLabel>
      {children({
        id: controlId,
        "aria-invalid": invalid ? true : undefined,
        "aria-describedby": describedBy,
      })}
      {description ? <FieldDescription id={descriptionId}>{description}</FieldDescription> : null}
      {invalid ? <FieldError id={errorId}>{error}</FieldError> : null}
    </Field>
  )
}

export {
  Field,
  FieldLabel,
  FieldDescription,
  FieldError,
  FieldGroup,
  ValidatedField,
}
export type { FieldControlProps }
