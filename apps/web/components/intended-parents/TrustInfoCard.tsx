"use client"

import * as React from "react"
import {
    CheckIcon,
    FileTextIcon,
    HashIcon,
    LandmarkIcon,
    LinkIcon,
    Loader2Icon,
    MailIcon,
    MapPinIcon,
    PencilIcon,
    PhoneIcon,
    UserIcon,
    XIcon,
} from "lucide-react"

import { InlineEditField } from "@/components/inline-edit-field"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { getTrustFundingStatusLabel, getTrustFundingStatusOptions } from "@/lib/trust-funding-status"
import type { IntendedParent, IntendedParentUpdate } from "@/lib/types/intended-parent"

interface TrustInfoCardProps {
    intendedParent: IntendedParent
    onUpdate: (data: IntendedParentUpdate) => Promise<void>
}

type TrustAddressDraft = {
    trust_address_line1: string
    trust_address_line2: string
    trust_city: string
    trust_state: string
    trust_postal: string
}

function buildAddressDraft(intendedParent: IntendedParent): TrustAddressDraft {
    return {
        trust_address_line1: intendedParent.trust_address_line1 ?? "",
        trust_address_line2: intendedParent.trust_address_line2 ?? "",
        trust_city: intendedParent.trust_city ?? "",
        trust_state: intendedParent.trust_state ?? "",
        trust_postal: intendedParent.trust_postal ?? "",
    }
}

function formatTrustAddress(intendedParent: IntendedParent): string | null {
    const parts = [
        intendedParent.trust_address_line1,
        intendedParent.trust_address_line2,
        intendedParent.trust_city,
        intendedParent.trust_state,
        intendedParent.trust_postal,
    ].filter(Boolean)

    return parts.length > 0 ? parts.join(", ") : null
}

function SummaryField({
    icon,
    label,
    children,
    className,
}: {
    icon: React.ReactNode
    label: string
    children: React.ReactNode
    className?: string
}) {
    return (
        <div className={className ?? "flex items-start gap-3"}>
            <div className="mt-0.5 shrink-0 text-muted-foreground">{icon}</div>
            <div className="min-w-0 flex-1">
                <p className="text-sm text-muted-foreground">{label}</p>
                {children}
            </div>
        </div>
    )
}

function TrustAddressField({
    intendedParent,
    onUpdate,
}: {
    intendedParent: IntendedParent
    onUpdate: (data: IntendedParentUpdate) => Promise<void>
}) {
    const [isEditing, setIsEditing] = React.useState(false)
    const [draft, setDraft] = React.useState<TrustAddressDraft>(() => buildAddressDraft(intendedParent))
    const [isSaving, setIsSaving] = React.useState(false)
    const [error, setError] = React.useState<string | null>(null)
    const shouldFocusFirstInputRef = React.useRef(false)

    const addressSummary = formatTrustAddress(intendedParent)

    const setFirstInputRef = (element: HTMLInputElement | null) => {
        if (element && shouldFocusFirstInputRef.current) {
            shouldFocusFirstInputRef.current = false
            element.focus()
        }
    }

    const setField = (field: keyof TrustAddressDraft, value: string) => {
        setDraft((current) => ({ ...current, [field]: value }))
    }

    const openAddressEditor = () => {
        setDraft(buildAddressDraft(intendedParent))
        setError(null)
        shouldFocusFirstInputRef.current = true
        setIsEditing(true)
    }

    const handleCancel = () => {
        setDraft(buildAddressDraft(intendedParent))
        setError(null)
        setIsEditing(false)
    }

    const handleSave = async () => {
        const payload: IntendedParentUpdate = {
            trust_address_line1: draft.trust_address_line1.trim() || null,
            trust_address_line2: draft.trust_address_line2.trim() || null,
            trust_city: draft.trust_city.trim() || null,
            trust_state: draft.trust_state.trim().toUpperCase() || null,
            trust_postal: draft.trust_postal.trim() || null,
        }

        const unchanged =
            payload.trust_address_line1 === (intendedParent.trust_address_line1 ?? null)
            && payload.trust_address_line2 === (intendedParent.trust_address_line2 ?? null)
            && payload.trust_city === (intendedParent.trust_city ?? null)
            && payload.trust_state === (intendedParent.trust_state ?? null)
            && payload.trust_postal === (intendedParent.trust_postal ?? null)

        if (unchanged) {
            setError(null)
            setIsEditing(false)
            return
        }

        setIsSaving(true)
        const result = await onUpdate(payload).then(() => ({
            status: "success" as const,
        })).catch((err: unknown) => ({
            status: "error" as const,
            error: err instanceof Error ? err.message : "Failed to save address",
        }))

        if (result.status === "success") {
            setError(null)
            setIsEditing(false)
        } else {
            setError(result.error)
        }
        setIsSaving(false)
    }

    if (!isEditing) {
        return (
            <button
                type="button"
                className="group flex items-center gap-1 -mx-1 cursor-pointer appearance-none rounded border-0 bg-transparent px-1 text-left text-inherit transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                onClick={openAddressEditor}
                aria-label="Edit Trust address"
            >
                <span className={`text-sm ${addressSummary ? "font-medium" : "text-muted-foreground"}`}>
                    {addressSummary || "Not provided"}
                </span>
                <PencilIcon
                    className="size-3 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                    aria-hidden="true"
                />
            </button>
        )
    }

    return (
        <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
                <label htmlFor="trust-address-line-1" className="space-y-1 text-sm">
                    <span className="text-xs text-muted-foreground">Address line 1</span>
                    <Input
                        id="trust-address-line-1"
                        ref={setFirstInputRef}
                        value={draft.trust_address_line1}
                        onChange={(event) => setField("trust_address_line1", event.target.value)}
                        aria-label="Trust address line 1"
                        disabled={isSaving}
                    />
                </label>
                <label htmlFor="trust-address-line-2" className="space-y-1 text-sm">
                    <span className="text-xs text-muted-foreground">Address line 2</span>
                    <Input
                        id="trust-address-line-2"
                        value={draft.trust_address_line2}
                        onChange={(event) => setField("trust_address_line2", event.target.value)}
                        aria-label="Trust address line 2"
                        disabled={isSaving}
                    />
                </label>
                <label htmlFor="trust-city" className="space-y-1 text-sm">
                    <span className="text-xs text-muted-foreground">City</span>
                    <Input
                        id="trust-city"
                        value={draft.trust_city}
                        onChange={(event) => setField("trust_city", event.target.value)}
                        aria-label="Trust city"
                        disabled={isSaving}
                    />
                </label>
                <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                    <label htmlFor="trust-state" className="space-y-1 text-sm">
                        <span className="text-xs text-muted-foreground">State</span>
                        <Input
                            id="trust-state"
                            value={draft.trust_state}
                            onChange={(event) => setField("trust_state", event.target.value)}
                            aria-label="Trust state"
                            disabled={isSaving}
                            maxLength={2}
                        />
                    </label>
                    <label htmlFor="trust-zip" className="space-y-1 text-sm">
                        <span className="text-xs text-muted-foreground">ZIP</span>
                        <Input
                            id="trust-zip"
                            value={draft.trust_postal}
                            onChange={(event) => setField("trust_postal", event.target.value)}
                            aria-label="Trust ZIP"
                            disabled={isSaving}
                        />
                    </label>
                </div>
            </div>
            <div className="flex items-center gap-1">
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-6"
                    onClick={handleSave}
                    disabled={isSaving}
                    aria-label="Save Trust address"
                >
                    {isSaving ? (
                        <Loader2Icon className="size-3 animate-spin" aria-hidden="true" />
                    ) : (
                        <CheckIcon className="size-3 text-green-600" aria-hidden="true" />
                    )}
                </Button>
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-6"
                    onClick={handleCancel}
                    disabled={isSaving}
                    aria-label="Cancel Trust address"
                >
                    <XIcon className="size-3 text-destructive" aria-hidden="true" />
                </Button>
            </div>
            {error ? <p className="text-xs text-destructive">{error}</p> : null}
        </div>
    )
}

function TrustNotesField({
    value,
    onSave,
}: {
    value: string | null
    onSave: (value: string | null) => Promise<void>
}) {
    const [isEditing, setIsEditing] = React.useState(false)
    const [draft, setDraft] = React.useState(value ?? "")
    const [isSaving, setIsSaving] = React.useState(false)
    const [error, setError] = React.useState<string | null>(null)
    const shouldFocusTextareaRef = React.useRef(false)

    const setTextareaRef = (element: HTMLTextAreaElement | null) => {
        if (element && shouldFocusTextareaRef.current) {
            shouldFocusTextareaRef.current = false
            element.focus()
        }
    }

    const openNotesEditor = () => {
        setDraft(value ?? "")
        setError(null)
        shouldFocusTextareaRef.current = true
        setIsEditing(true)
    }

    const handleCancel = () => {
        setDraft(value ?? "")
        setError(null)
        setIsEditing(false)
    }

    const handleSave = async () => {
        const nextValue = draft.trim() || null
        if (nextValue === (value ?? null)) {
            setError(null)
            setIsEditing(false)
            return
        }

        setIsSaving(true)
        const result = await onSave(nextValue).then(() => ({
            status: "success" as const,
        })).catch((err: unknown) => ({
            status: "error" as const,
            error: err instanceof Error ? err.message : "Failed to save notes",
        }))

        if (result.status === "success") {
            setError(null)
            setIsEditing(false)
        } else {
            setError(result.error)
        }
        setIsSaving(false)
    }

    if (!isEditing) {
        return (
            <button
                type="button"
                className="group flex items-start gap-1 -mx-1 cursor-pointer appearance-none rounded border-0 bg-transparent px-1 text-left text-inherit transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                onClick={openNotesEditor}
                aria-label="Edit Trust notes"
            >
                <span className={`text-sm whitespace-pre-wrap ${value ? "font-medium" : "text-muted-foreground"}`}>
                    {value || "Not provided"}
                </span>
                <PencilIcon
                    className="mt-0.5 size-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                    aria-hidden="true"
                />
            </button>
        )
    }

    return (
        <div className="space-y-3">
            <Textarea
                ref={setTextareaRef}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                aria-label="Trust notes"
                disabled={isSaving}
                rows={4}
            />
            <div className="flex items-center gap-1">
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-6"
                    onClick={handleSave}
                    disabled={isSaving}
                    aria-label="Save Trust notes"
                >
                    {isSaving ? (
                        <Loader2Icon className="size-3 animate-spin" aria-hidden="true" />
                    ) : (
                        <CheckIcon className="size-3 text-green-600" aria-hidden="true" />
                    )}
                </Button>
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-6"
                    onClick={handleCancel}
                    disabled={isSaving}
                    aria-label="Cancel Trust notes"
                >
                    <XIcon className="size-3 text-destructive" aria-hidden="true" />
                </Button>
            </div>
            {error ? <p className="text-xs text-destructive">{error}</p> : null}
        </div>
    )
}

export function TrustInfoCard({ intendedParent, onUpdate }: TrustInfoCardProps) {
    const trustFundingOptions = getTrustFundingStatusOptions(intendedParent.trust_funding_status)

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <LandmarkIcon className="size-4" />
                    Trust Info
                </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
                <SummaryField icon={<LandmarkIcon className="size-5" />} label="Provider">
                    <InlineEditField
                        value={intendedParent.trust_provider_name}
                        onSave={async (value) => {
                            await onUpdate({ trust_provider_name: value.trim() || null })
                        }}
                        placeholder="Not provided"
                        label="Trust provider"
                        className="font-medium"
                    />
                </SummaryField>

                <SummaryField icon={<UserIcon className="size-5" />} label="Primary Contact">
                    <InlineEditField
                        value={intendedParent.trust_primary_contact_name}
                        onSave={async (value) => {
                            await onUpdate({ trust_primary_contact_name: value.trim() || null })
                        }}
                        placeholder="Not provided"
                        label="Trust primary contact"
                        className="font-medium"
                    />
                </SummaryField>

                <SummaryField icon={<MailIcon className="size-5" />} label="Email">
                    <InlineEditField
                        value={intendedParent.trust_email}
                        onSave={async (value) => {
                            await onUpdate({ trust_email: value.trim() || null })
                        }}
                        type="email"
                        placeholder="Not provided"
                        label="Trust email"
                        className="font-medium break-all"
                    />
                </SummaryField>

                <SummaryField icon={<PhoneIcon className="size-5" />} label="Phone">
                    <InlineEditField
                        value={intendedParent.trust_phone}
                        onSave={async (value) => {
                            await onUpdate({ trust_phone: value.trim() || null })
                        }}
                        type="tel"
                        placeholder="Not provided"
                        label="Trust phone"
                        className="font-medium"
                    />
                </SummaryField>

                <SummaryField icon={<HashIcon className="size-5" />} label="Reference ID">
                    <InlineEditField
                        value={intendedParent.trust_case_reference}
                        onSave={async (value) => {
                            await onUpdate({ trust_case_reference: value.trim() || null })
                        }}
                        placeholder="Not provided"
                        label="Trust reference ID"
                        className="font-medium"
                    />
                </SummaryField>

                <SummaryField icon={<LandmarkIcon className="size-5" />} label="Funding Status">
                    <Select
                        value={intendedParent.trust_funding_status ?? "__none__"}
                        onValueChange={async (value) => {
                            await onUpdate({
                                trust_funding_status: value === "__none__" ? null : value,
                            })
                        }}
                    >
                        <SelectTrigger aria-label="Trust funding status" className="w-full sm:w-[240px]">
                            <SelectValue placeholder="Not provided">
                                {(value: string | null) =>
                                    value === "__none__" ? "Not provided" : getTrustFundingStatusLabel(value)
                                }
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="__none__">Not provided</SelectItem>
                            {trustFundingOptions.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                    {option.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </SummaryField>

                <SummaryField icon={<LinkIcon className="size-5" />} label="Portal URL" className="sm:col-span-2 flex items-start gap-3">
                    <InlineEditField
                        value={intendedParent.trust_portal_url}
                        onSave={async (value) => {
                            await onUpdate({ trust_portal_url: value.trim() || null })
                        }}
                        type="url"
                        placeholder="Not provided"
                        label="Trust portal URL"
                        className="font-medium break-all"
                    />
                </SummaryField>

                <SummaryField icon={<MapPinIcon className="size-5" />} label="Address" className="sm:col-span-2 flex items-start gap-3">
                    <TrustAddressField intendedParent={intendedParent} onUpdate={onUpdate} />
                </SummaryField>

                <SummaryField icon={<FileTextIcon className="size-5" />} label="Notes" className="sm:col-span-2 flex items-start gap-3">
                    <TrustNotesField
                        value={intendedParent.trust_notes}
                        onSave={async (value) => {
                            await onUpdate({ trust_notes: value })
                        }}
                    />
                </SummaryField>
            </CardContent>
        </Card>
    )
}
