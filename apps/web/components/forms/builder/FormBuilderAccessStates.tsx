"use client"

import type { ReactNode } from "react"
import { Loader2Icon } from "lucide-react"

import { PermissionDeniedState } from "@/components/error-state"
import { PageHeader } from "@/components/page-header"

/** Denied copy shared by the Form Builder list and editor; every /forms route requires manage_forms. */
export const FORM_BUILDER_DENIED = {
    title: "No access to Form Builder",
    description: "Ask an admin to update your role.",
} as const

/** Editor denied copy after a 403 on the form itself: the viewer can still open the list. */
export const FORM_BUILDER_EDITOR_DENIED = {
    ...FORM_BUILDER_DENIED,
    secondaryHref: "/automation/forms",
    secondaryLabel: "Back to forms",
} as const

/** Editor shell for states that replace the builder: the list's header plus one state below it. */
export function FormBuilderBlockedScreen({ children }: { children: ReactNode }) {
    return (
        <div className="flex min-h-screen flex-col bg-background">
            <PageHeader title="Form Builder" />
            {children}
        </div>
    )
}

export function FormBuilderLoadingState({ label }: { label: string }) {
    return (
        <div className="flex h-screen items-center justify-center bg-background" role="status">
            <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2Icon className="size-5 animate-spin" aria-hidden="true" />
                <span>{label}</span>
            </div>
        </div>
    )
}

/** Denied for lack of manage_forms, which the list requires too, so the way out is the dashboard. */
export function FormBuilderDeniedScreen() {
    return (
        <FormBuilderBlockedScreen>
            <PermissionDeniedState {...FORM_BUILDER_DENIED} secondaryHref="/dashboard" headingLevel={2} />
        </FormBuilderBlockedScreen>
    )
}
