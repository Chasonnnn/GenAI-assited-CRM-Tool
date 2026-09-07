"use client"

import type { CSSProperties } from "react"
import Link from "@/components/app-link"
import { RecordDetailField } from "@/components/RecordDetailField"
import { IntendedParentFormFields } from "@/components/intended-parents/IntendedParentFormFields"
import type { IntendedParentFormValues } from "@/components/intended-parents/intended-parent-form-values"
import { InlineDateField } from "@/components/inline-date-field"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import type { IntendedParent } from "@/lib/types/intended-parent"
import {
    ArchiveIcon,
    ArchiveRestoreIcon,
    ArrowLeftIcon,
    CalendarIcon,
    HeartHandshakeIcon,
    Loader2Icon,
    MailIcon,
    MapPinIcon,
    MoreVerticalIcon,
    PhoneIcon,
    Trash2Icon,
    UserIcon,
} from "lucide-react"



type MaritalStatusOption = {
    value: string
    label: string
}

type IntendedParentFormFieldChange = <K extends keyof IntendedParentFormValues>(
    field: K,
    value: IntendedParentFormValues[K],
) => void

export function IntendedParentLoadingState() {
    return (
        <div className="flex min-h-screen items-center justify-center">
            <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
        </div>
    )
}

export function IntendedParentNotFoundState() {
    return (
        <div className="flex min-h-screen flex-col items-center justify-center">
            <h1 className="text-2xl font-semibold">Not Found</h1>
            <p className="text-muted-foreground">This intended parent doesn&apos;t exist.</p>
            <Link href="/intended-parents" className="mt-4 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90">
                Back to List
            </Link>
        </div>
    )
}

export function IntendedParentHeader({
    intendedParent,
    statusLabel,
    statusStyle,
    isStatusPending,
    onProposeMatch,
    onChangeStage,
    onEdit,
    onArchive,
    onRestore,
    onDelete,
}: {
    intendedParent: IntendedParent
    statusLabel: string
    statusStyle: CSSProperties
    isStatusPending: boolean
    onProposeMatch: () => void
    onChangeStage: () => void
    onEdit: () => void
    onArchive: () => void
    onRestore: () => void
    onDelete: () => void
}) {
    return (
        <div className="border-b border-border bg-background/95 backdrop-blur">
            <div className="flex min-h-16 min-w-0 flex-col gap-3 px-6 py-3 lg:flex-row lg:flex-wrap lg:items-center lg:justify-between">
                <div className="flex min-w-0 items-center gap-4 lg:flex-1">
                    <Link
                        href="/intended-parents"
                        aria-label="Back to intended parents"
                        className="inline-flex shrink-0 items-center justify-center rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground size-9"
                    >
                        <ArrowLeftIcon className="size-5" />
                        <span className="sr-only">Back to intended parents</span>
                    </Link>
                    <div className="min-w-0">
                        <h1 className="truncate text-2xl font-semibold">{intendedParent.full_name}</h1>
                        <p className="truncate text-sm text-muted-foreground">
                            {intendedParent.intended_parent_number ? `${intendedParent.intended_parent_number} • ` : ""}
                            {intendedParent.email}
                        </p>
                    </div>
                </div>
                <div className="flex w-full min-w-0 max-w-full flex-wrap items-center gap-2 lg:w-auto lg:justify-end">
                    <Button
                        variant="outline"
                        className="px-2 sm:px-4"
                        onClick={onProposeMatch}
                        disabled={intendedParent.is_archived}
                    >
                        <HeartHandshakeIcon className="hidden size-4 sm:block" />
                        Propose Match
                    </Button>
                    <Button
                        variant="outline"
                        className="px-2 sm:px-4"
                        onClick={onChangeStage}
                        disabled={isStatusPending || intendedParent.is_archived}
                    >
                        Change Stage
                    </Button>
                    <Badge className="min-w-0 max-w-full" variant="outline" style={statusStyle}>
                        <span className="truncate">{statusLabel}</span>
                    </Badge>
                    <DropdownMenu>
                        <DropdownMenuTrigger
                            aria-label={`Actions for ${intendedParent.full_name}`}
                            className="inline-flex size-9 shrink-0 items-center justify-center rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground"
                        >
                            <MoreVerticalIcon className="size-4" aria-hidden="true" />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={onEdit}>Edit</DropdownMenuItem>
                            <DropdownMenuSeparator />
                            {!intendedParent.is_archived ? (
                                <DropdownMenuItem onClick={onArchive}>
                                    <ArchiveIcon className="mr-2 size-4" /> Archive
                                </DropdownMenuItem>
                            ) : (
                                <>
                                    <DropdownMenuItem onClick={onRestore}>
                                        <ArchiveRestoreIcon className="mr-2 size-4" /> Restore
                                    </DropdownMenuItem>
                                    <DropdownMenuItem onClick={onDelete} className="text-destructive">
                                        <Trash2Icon className="mr-2 size-4" /> Delete Permanently
                                    </DropdownMenuItem>
                                </>
                            )}
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </div>
        </div>
    )
}

export function ContactInformationCard({
    intendedParent,
    onDateOfBirthChange,
}: {
    intendedParent: IntendedParent
    onDateOfBirthChange: (value: string | null) => Promise<void>
}) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Contact Information</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
                <RecordDetailField icon={MailIcon} label="Email" value={intendedParent.email} />
                <RecordDetailField icon={PhoneIcon} label="Phone" value={intendedParent.phone} />
                <RecordDetailField icon={UserIcon} label="Pronouns" value={intendedParent.pronouns} />
                <RecordDetailField icon={CalendarIcon} label="Date of Birth" value={
                    <InlineDateField
                        value={intendedParent.date_of_birth}
                        onSave={onDateOfBirthChange}
                        placeholder="Not provided"
                        label="Date of Birth"
                    />
                } />
                <RecordDetailField icon={MapPinIcon} label="Address" value={[
                    intendedParent.address_line1,
                    intendedParent.address_line2,
                    intendedParent.city,
                    intendedParent.state,
                    intendedParent.postal,
                ].filter(Boolean).join(", ")} />
            </CardContent>
        </Card>
    )
}

export function PartnerCard({
    intendedParent,
    onPartnerDateOfBirthChange,
}: {
    intendedParent: IntendedParent
    onPartnerDateOfBirthChange: (value: string | null) => Promise<void>
}) {
    if (!(
        intendedParent.partner_name ||
        intendedParent.partner_email ||
        intendedParent.partner_pronouns ||
        intendedParent.partner_date_of_birth
    )) {
        return null
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle>Partner</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
                <RecordDetailField icon={UserIcon} label="Name" value={intendedParent.partner_name} />
                <RecordDetailField icon={MailIcon} label="Email" value={intendedParent.partner_email} />
                {intendedParent.partner_pronouns && (
                    <RecordDetailField icon={UserIcon} label="Pronouns" value={intendedParent.partner_pronouns} />
                )}
                <RecordDetailField icon={CalendarIcon} label="Date of Birth" value={
                    <InlineDateField
                        value={intendedParent.partner_date_of_birth}
                        onSave={onPartnerDateOfBirthChange}
                        placeholder="Not provided"
                        label="Partner date of birth"
                    />
                } />
            </CardContent>
        </Card>
    )
}

export function MaritalStatusCard({
    value,
    options,
    disabled,
    onChange,
}: {
    value: string | null
    options: MaritalStatusOption[]
    disabled: boolean
    onChange: (value: string | null) => Promise<void>
}) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Marital Status</CardTitle>
            </CardHeader>
            <CardContent>
                <Select
                    value={value ?? "__none__"}
                    onValueChange={async (nextValue) => {
                        await onChange(nextValue === "__none__" ? null : nextValue)
                    }}
                    disabled={disabled}
                >
                    <SelectTrigger aria-label="Marital status" className="w-full max-w-[240px]">
                        <SelectValue placeholder="Not provided">
                            {(selectedValue: string | null) =>
                                options.find((option) => option.value === selectedValue)?.label ??
                                "Not provided"
                            }
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="__none__">Not provided</SelectItem>
                        {options.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                                {option.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </CardContent>
        </Card>
    )
}

export function EditIntendedParentDialog({
    open,
    values,
    isPending,
    onOpenChange,
    onChange,
    onSave,
}: {
    open: boolean
    values: IntendedParentFormValues
    isPending: boolean
    onOpenChange: (open: boolean) => void
    onChange: IntendedParentFormFieldChange
    onSave: () => void
}) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-lg">
                <DialogHeader>
                    <DialogTitle>Edit Intended Parent</DialogTitle>
                    <DialogDescription>Update the intended parent details</DialogDescription>
                </DialogHeader>
                <IntendedParentFormFields
                    values={values}
                    onChange={onChange}
                    idPrefix="edit_"
                    showClinicSection={false}
                    showInternalNotes={false}
                />
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button
                        onClick={onSave}
                        disabled={isPending}
                    >
                        {isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        Save Changes
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
