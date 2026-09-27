"use client"

/**
 * Appointment Settings - Availability configuration for staff
 * 
 * Features:
 * - Booking link management
 * - Weekly availability grid
 * - Date overrides
 * - Appointment types management
 * - Google Calendar connection warning
 */

import { useState } from "react"
import Link from "@/components/app-link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { Button } from "@/components/ui/button"
import { CopyField } from "@/components/ui/copy-field"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Checkbox } from "@/components/ui/checkbox"
import {
    Dialog,
    DialogBody,
    DialogClose,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { ValidatedField } from "@/components/ui/field"
import { EmptyState } from "@/components/empty-state"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import {
    LinkIcon,
    ClockIcon,
    PlusIcon,
    PowerOffIcon,
    VideoIcon,
    PhoneIcon,
    MapPinIcon,
    Loader2Icon,
    CalendarIcon,
    ExternalLinkIcon,
    EyeIcon,
} from "lucide-react"
import { toast } from "@/components/ui/toast"
import { useAuth } from "@/lib/auth-context"
import {
    useBookingLink,
    useAppointmentTypes,
    useCreateAppointmentType,
    useUpdateAppointmentType,
    useDeleteAppointmentType,
    useAvailabilityRules,
    useSetAvailabilityRules,
} from "@/lib/hooks/use-appointments"
import { useUserIntegrations } from "@/lib/hooks/use-user-integrations"
import type { AppointmentType, MeetingMode } from "@/lib/api/appointments"
import { createSelectLabelGetter, toSelectOptions } from "@/lib/select-labels"
import { useFormValidation } from "@/lib/forms/use-form-validation"
import { validateRequired } from "@/lib/forms/validators"
import { useTabSearchParam } from "@/lib/hooks/use-tab-search-param"

function openBookingPreview() {
    const baseUrl =
        typeof window !== "undefined" ? `${window.location.origin}/book/preview` : "/book/preview"
    window.open(baseUrl, "_blank")
}

// =============================================================================
// Google Calendar Connection Warning Banner
// =============================================================================

function GoogleCalendarWarningBanner() {
    const [dismissed, setDismissed] = useState(false)
    const { data: integrations, isLoading, isError } = useUserIntegrations()
    const calendarConnected = integrations?.some(
        (integration) =>
            integration.integration_type === "google_calendar" && integration.connected
    )

    if (dismissed || isLoading || isError || calendarConnected) return null

    return (
        <Alert className="mb-6 border-amber-500/50 bg-amber-50 dark:bg-amber-950/20">
            <CalendarIcon className="size-4 text-amber-600" />
            <AlertTitle className="text-amber-800 dark:text-amber-400">
                Google Calendar Integration Recommended
            </AlertTitle>
            <AlertDescription className="text-amber-700 dark:text-amber-300">
                <p className="mb-2">
                    Connect your Google Calendar to enable calendar sync and Google Meet links for appointments.
                </p>
                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        className="border-amber-500 text-amber-700 hover:bg-amber-100"
                        render={<Link href="/settings/integrations" />}
                    >
                        <ExternalLinkIcon className="size-3 mr-1" />
                        Connect Google Calendar
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setDismissed(true)}>
                        Dismiss
                    </Button>
                </div>
            </AlertDescription>
        </Alert>
    )
}

// Days of week (ISO 8601: Monday = 0)
const DAYS_OF_WEEK = [
    { value: 0, label: "Monday" },
    { value: 1, label: "Tuesday" },
    { value: 2, label: "Wednesday" },
    { value: 3, label: "Thursday" },
    { value: 4, label: "Friday" },
    { value: 5, label: "Saturday" },
    { value: 6, label: "Sunday" },
]

// Time options for dropdowns
const TIME_OPTIONS = Array.from({ length: 24 * 2 }, (_, i) => {
    const hour = Math.floor(i / 2)
    const minute = (i % 2) * 30
    const value = `${hour.toString().padStart(2, "0")}:${minute.toString().padStart(2, "0")}`
    const label = new Date(`2000-01-01T${value}`).toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
    })
    return { value, label }
})

// Meeting mode icons
const MEETING_MODE_OPTIONS: Array<{
    value: MeetingMode;
    label: string;
    icon: typeof VideoIcon;
}> = [
    { value: "zoom", label: "Zoom", icon: VideoIcon },
    { value: "google_meet", label: "Google Meet", icon: VideoIcon },
    { value: "phone", label: "Phone", icon: PhoneIcon },
    { value: "in_person", label: "In-Person", icon: MapPinIcon },
]

const MEETING_MODE_LABELS = MEETING_MODE_OPTIONS.reduce<Record<string, string>>((acc, option) => {
    acc[option.value] = option.label
    return acc
}, {})

type AvailabilityRuleDraft = {
    day_of_week: number
    start_time: string
    end_time: string
    enabled: boolean
}

type AvailabilityRulesState = {
    draft: AvailabilityRulesDraft | null
    hasChanges: boolean
    sourceFingerprintAtSave: string | null
}

type AvailabilityRulesDraft = {
    localRules: AvailabilityRuleDraft[]
    timezone: string
}

// The API returns "HH:MM:SS"; TIME_OPTIONS values are "HH:MM".
function toTimeOptionValue(value: string | null | undefined, fallback: string): string {
    return value ? value.slice(0, 5) : fallback
}

const getTimeOptionLabel = createSelectLabelGetter(TIME_OPTIONS, {
    emptyLabel: "Select time",
    unknownLabel: "Select time",
})

const TIMEZONE_LABELS = {
    "America/Los_Angeles": "Pacific Time",
    "America/New_York": "Eastern Time",
    "America/Chicago": "Central Time",
    "America/Denver": "Mountain Time",
    UTC: "UTC",
} as const

const getTimezoneLabel = createSelectLabelGetter(TIMEZONE_LABELS, {
    emptyLabel: "Select timezone",
    unknownLabel: "Unknown timezone",
})

function buildAvailabilityDraft(
    rules: Array<{ day_of_week: number; start_time: string; end_time: string; timezone: string }>,
    fallbackTimezone: string
): AvailabilityRulesDraft {
    const rulesByDay = new Map(rules.map((rule) => [rule.day_of_week, rule]))
    return {
        localRules: DAYS_OF_WEEK.map((day) => {
            const existing = rulesByDay.get(day.value)
            return {
                day_of_week: day.value,
                start_time: toTimeOptionValue(existing?.start_time, "09:00"),
                end_time: toTimeOptionValue(existing?.end_time, "17:00"),
                enabled: !!existing,
            }
        }),
        timezone: rules[0]?.timezone ?? fallbackTimezone,
    }
}

function getAvailabilityFingerprint(draft: AvailabilityRulesDraft): string {
    return JSON.stringify(draft)
}

function resolveAvailabilityDraft(
    state: AvailabilityRulesState,
    serverDraft: AvailabilityRulesDraft,
    serverFingerprint: string
): AvailabilityRulesDraft {
    if (
        state.draft &&
        (state.hasChanges || state.sourceFingerprintAtSave === serverFingerprint)
    ) {
        return state.draft
    }
    return serverDraft
}

type AppointmentTypeFormState = {
    name: string
    description: string
    duration_minutes: number
    buffer_after_minutes: number
    meeting_modes: MeetingMode[]
    meeting_location: string
    dial_in_number: string
    auto_approve: boolean
    reminder_hours_before: number
}

type AppointmentTypeFormUpdater = (
    updater: (current: AppointmentTypeFormState) => AppointmentTypeFormState,
) => void

function validateAppointmentTypeForm(values: AppointmentTypeFormState) {
    return {
        name: validateRequired(values.name, "Enter a name."),
        meeting_location: values.meeting_modes.includes("in_person")
            ? validateRequired(values.meeting_location, "Enter a location for in-person appointments.")
            : undefined,
        dial_in_number: values.meeting_modes.includes("phone")
            ? validateRequired(values.dial_in_number, "Enter a dial-in number for phone appointments.")
            : undefined,
    }
}

type AppointmentTypeValidation = ReturnType<typeof useFormValidation<AppointmentTypeFormState>>

// =============================================================================
// Booking Link Card
// =============================================================================

function BookingLinkCard() {
    const { data: link, isLoading } = useBookingLink()

    if (isLoading) {
        return (
            <Card>
                <CardContent className="py-8 flex items-center justify-center">
                    <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                </CardContent>
            </Card>
        )
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <LinkIcon className="size-5" />
                    Your Booking Link
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <CopyField
                    aria-label="Your booking link"
                    value={link?.full_url || `${typeof window !== 'undefined' ? window.location.origin : ''}/book/${link?.public_slug || ''}`}
                    copyLabel="Copy booking link"
                />
                <Button variant="outline" size="sm" onClick={openBookingPreview}>
                    <EyeIcon className="size-4 mr-2" />
                    Preview Booking Page
                </Button>
                <p className="text-xs text-muted-foreground">
                    This booking link stays the same, so previously shared links remain valid.
                </p>
            </CardContent>
        </Card>
    )
}

// =============================================================================
// Availability Rules Card
// =============================================================================

function AvailabilityRulesCard() {
    const { user } = useAuth()
    const { data: rules, isLoading } = useAvailabilityRules()
    const setRulesMutation = useSetAvailabilityRules()
    const [availabilityState, setAvailabilityState] = useState<AvailabilityRulesState>(() => ({
        draft: null,
        hasChanges: false,
        sourceFingerprintAtSave: null,
    }))
    const serverDraft = buildAvailabilityDraft(
        rules ?? [],
        user?.org_timezone || "America/Los_Angeles"
    )
    const serverFingerprint = getAvailabilityFingerprint(serverDraft)
    const { localRules, timezone } = resolveAvailabilityDraft(
        availabilityState,
        serverDraft,
        serverFingerprint
    )
    const { hasChanges } = availabilityState

    const toggleDay = (dayValue: number) => {
        setAvailabilityState((current) => {
            const currentDraft = resolveAvailabilityDraft(current, serverDraft, serverFingerprint)
            return {
                draft: {
                    ...currentDraft,
                    localRules: currentDraft.localRules.map((rule) =>
                        rule.day_of_week === dayValue ? { ...rule, enabled: !rule.enabled } : rule
                    ),
                },
                hasChanges: true,
                sourceFingerprintAtSave: null,
            }
        })
    }

    const updateTime = (dayValue: number, field: "start_time" | "end_time", value: string) => {
        setAvailabilityState((current) => {
            const currentDraft = resolveAvailabilityDraft(current, serverDraft, serverFingerprint)
            return {
                draft: {
                    ...currentDraft,
                    localRules: currentDraft.localRules.map((rule) =>
                        rule.day_of_week === dayValue ? { ...rule, [field]: value } : rule
                    ),
                },
                hasChanges: true,
                sourceFingerprintAtSave: null,
            }
        })
    }

    const saveRules = () => {
        const enabledRules: Array<{ day_of_week: number; start_time: string; end_time: string }> = []
        for (const rule of localRules) {
            if (!rule.enabled) continue
            const { day_of_week, start_time, end_time } = rule
            enabledRules.push({ day_of_week, start_time, end_time })
        }

        setRulesMutation.mutate({ rules: enabledRules, timezone }, {
            onSuccess: () => {
                setAvailabilityState((current) => ({
                    ...current,
                    hasChanges: false,
                    sourceFingerprintAtSave: serverFingerprint,
                }))
            },
        })
    }

    if (isLoading) {
        return (
            <Card>
                <CardContent className="py-8 flex items-center justify-center">
                    <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                </CardContent>
            </Card>
        )
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <ClockIcon className="size-5" />
                    Weekly Availability
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="space-y-3">
                    {DAYS_OF_WEEK.map((day) => {
                        const rule = localRules.find((r) => r.day_of_week === day.value)
                        return (
                            <div
                                key={day.value}
                                className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-lg border border-border p-3"
                            >
                                <div className="flex items-center gap-3 sm:w-36">
                                    <Switch
                                        checked={rule?.enabled || false}
                                        onCheckedChange={() => toggleDay(day.value)}
                                        aria-label={`Available on ${day.label}`}
                                    />
                                    <span className="font-medium">{day.label}</span>
                                </div>
                                {rule?.enabled ? (
                                    // Below sm the times take their own row so both selects stay fully visible.
                                    <div className="flex w-full items-center gap-2 sm:w-auto">
                                        <Select
                                            value={rule.start_time}
                                            onValueChange={(v) => v && updateTime(day.value, "start_time", v)}
                                        >
                                            <SelectTrigger
                                                className="min-w-0 flex-1 sm:w-32 sm:flex-none"
                                                aria-label={`${day.label} start time`}
                                            >
                                                <SelectValue>{getTimeOptionLabel}</SelectValue>
                                            </SelectTrigger>
                                            <SelectContent>
                                                {TIME_OPTIONS.map((opt) => (
                                                    <SelectItem key={opt.value} value={opt.value}>
                                                        {opt.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                        <span className="text-muted-foreground">to</span>
                                        <Select
                                            value={rule.end_time}
                                            onValueChange={(v) => v && updateTime(day.value, "end_time", v)}
                                        >
                                            <SelectTrigger
                                                className="min-w-0 flex-1 sm:w-32 sm:flex-none"
                                                aria-label={`${day.label} end time`}
                                            >
                                                <SelectValue>{getTimeOptionLabel}</SelectValue>
                                            </SelectTrigger>
                                            <SelectContent>
                                                {TIME_OPTIONS.map((opt) => (
                                                    <SelectItem key={opt.value} value={opt.value}>
                                                        {opt.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                ) : (
                                    <span className="ml-auto text-muted-foreground sm:ml-0">Unavailable</span>
                                )}
                            </div>
                        )
                    })}
                </div>

                <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                        <Label htmlFor="availability-timezone">Timezone</Label>
                        <Select
                            value={timezone}
                            onValueChange={(v) => {
                                if (!v) return
                                setAvailabilityState((current) => {
                                    const currentDraft = resolveAvailabilityDraft(
                                        current,
                                        serverDraft,
                                        serverFingerprint
                                    )
                                    return {
                                        draft: { ...currentDraft, timezone: v },
                                        hasChanges: true,
                                        sourceFingerprintAtSave: null,
                                    }
                                })
                            }}
                        >
                            <SelectTrigger id="availability-timezone" className="w-full sm:w-48">
                                <SelectValue>{getTimezoneLabel}</SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                {toSelectOptions(TIMEZONE_LABELS).map((option) => (
                                    <SelectItem key={option.value} value={option.value}>
                                        {option.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <Button
                        onClick={saveRules}
                        disabled={!hasChanges || setRulesMutation.isPending}
                        className="w-full sm:w-auto"
                    >
                        {setRulesMutation.isPending ? (
                            <Loader2Icon className="size-4 mr-2 animate-spin" />
                        ) : null}
                        Save availability
                    </Button>
                </div>
            </CardContent>
        </Card>
    )
}

// =============================================================================
// Appointment Types Card
// =============================================================================

function AppointmentTypesLoadingCard() {
    return (
        <Card>
            <CardContent className="py-8 flex items-center justify-center">
                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
            </CardContent>
        </Card>
    )
}

function AppointmentTypesHeader({
    dialogOpen,
    editingType,
    formData,
    isSaving,
    validation,
    onDialogOpenChange,
    onCreate,
    onFormDataChange,
    onToggleMeetingMode,
    onSubmit,
}: {
    dialogOpen: boolean
    editingType: AppointmentType | null
    formData: AppointmentTypeFormState
    isSaving: boolean
    validation: AppointmentTypeValidation
    onDialogOpenChange: (open: boolean) => void
    onCreate: () => void
    onFormDataChange: AppointmentTypeFormUpdater
    onToggleMeetingMode: (mode: MeetingMode, checked: boolean | "indeterminate") => void
    onSubmit: (event: React.MouseEvent) => void
}) {
    return (
        <CardHeader className="flex flex-row items-center justify-between">
            <div>
                <CardTitle>Appointment Types</CardTitle>
            </div>
            <Dialog open={dialogOpen} onOpenChange={onDialogOpenChange}>
                <Button onClick={onCreate}>
                    <PlusIcon className="size-4 mr-2" />
                    Add type
                </Button>
                <AppointmentTypeDialog
                    editingType={editingType}
                    formData={formData}
                    isSaving={isSaving}
                    validation={validation}
                    onFormDataChange={onFormDataChange}
                    onToggleMeetingMode={onToggleMeetingMode}
                    onSubmit={onSubmit}
                />
            </Dialog>
        </CardHeader>
    )
}

function AppointmentTypeDialog({
    editingType,
    formData,
    isSaving,
    validation,
    onFormDataChange,
    onToggleMeetingMode,
    onSubmit,
}: {
    editingType: AppointmentType | null
    formData: AppointmentTypeFormState
    isSaving: boolean
    validation: AppointmentTypeValidation
    onFormDataChange: AppointmentTypeFormUpdater
    onToggleMeetingMode: (mode: MeetingMode, checked: boolean | "indeterminate") => void
    onSubmit: (event: React.MouseEvent) => void
}) {
    return (
        <DialogContent layout="sectioned" size="lg">
            <DialogHeader>
                <DialogTitle>
                    {editingType ? "Edit Appointment Type" : "New Appointment Type"}
                </DialogTitle>
            </DialogHeader>
            <DialogBody className="gap-4">
                <ValidatedField label="Name" error={validation.errorFor("name")}>
                    {(control) => (
                        <Input
                            {...control}
                            value={formData.name}
                            onChange={(e) => onFormDataChange((current) => ({ ...current, name: e.target.value }))}
                            onBlur={() => validation.touch("name")}
                            placeholder="e.g., Initial Consultation"
                        />
                    )}
                </ValidatedField>
                <ValidatedField label="Description" error={validation.errorFor("description")}>
                    {(control) => (
                        <Textarea
                            {...control}
                            value={formData.description}
                            onChange={(e) => onFormDataChange((current) => ({ ...current, description: e.target.value }))}
                            placeholder="Brief description of this appointment type"
                        />
                    )}
                </ValidatedField>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                        <Label htmlFor="appointment-type-duration">Duration (minutes)</Label>
                        <Select
                            value={String(formData.duration_minutes)}
                            onValueChange={(v) =>
                                v && onFormDataChange((current) => ({ ...current, duration_minutes: parseInt(v) }))
                            }
                        >
                            <SelectTrigger id="appointment-type-duration" className="w-full">
                                <SelectValue>
                                    {(value: string | null) => {
                                        return value ? `${value} min` : "Select duration"
                                    }}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="15">15 min</SelectItem>
                                <SelectItem value="30">30 min</SelectItem>
                                <SelectItem value="45">45 min</SelectItem>
                                <SelectItem value="60">60 min</SelectItem>
                                <SelectItem value="90">90 min</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="appointment-type-buffer">Buffer After</Label>
                        <Select
                            value={String(formData.buffer_after_minutes)}
                            onValueChange={(v) =>
                                v && onFormDataChange((current) => ({ ...current, buffer_after_minutes: parseInt(v) }))
                            }
                        >
                            <SelectTrigger id="appointment-type-buffer" className="w-full">
                                <SelectValue>
                                    {(value: string | null) => {
                                        if (value === "0") return "No buffer"
                                        return value ? `${value} min` : "Select buffer"
                                    }}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="0">No buffer</SelectItem>
                                <SelectItem value="5">5 min</SelectItem>
                                <SelectItem value="10">10 min</SelectItem>
                                <SelectItem value="15">15 min</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>
                <AppointmentTypeMeetingModeFields
                    formData={formData}
                    onToggleMeetingMode={onToggleMeetingMode}
                />
                <AppointmentTypeConditionalFields
                    formData={formData}
                    validation={validation}
                    onFormDataChange={onFormDataChange}
                />
            </DialogBody>
            <DialogFooter>
                <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
                <Button onClick={onSubmit} disabled={isSaving}>
                    {isSaving ? (
                        <Loader2Icon className="size-4 mr-2 animate-spin" />
                    ) : null}
                    {editingType ? "Save changes" : "Create type"}
                </Button>
            </DialogFooter>
        </DialogContent>
    )
}

function AppointmentTypeMeetingModeFields({
    formData,
    onToggleMeetingMode,
}: {
    formData: AppointmentTypeFormState
    onToggleMeetingMode: (mode: MeetingMode, checked: boolean | "indeterminate") => void
}) {
    return (
        <div role="group" aria-labelledby="appointment-format-label" className="space-y-2">
            <p id="appointment-format-label" className="text-sm font-medium">Appointment Format</p>
            <div className="grid gap-2">
                {MEETING_MODE_OPTIONS.map((option) => {
                    const Icon = option.icon
                    const checked = formData.meeting_modes.includes(option.value)
                    const checkboxId = `appointment-format-${option.value}`
                    return (
                        <div
                            key={option.value}
                            className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm"
                        >
                            <Label htmlFor={checkboxId} className="flex items-center gap-2 cursor-pointer">
                                <Icon className="size-4 text-muted-foreground" />
                                <span>{option.label}</span>
                            </Label>
                            <Checkbox
                                id={checkboxId}
                                checked={checked}
                                onCheckedChange={(value) => onToggleMeetingMode(option.value, value)}
                            />
                        </div>
                    )
                })}
            </div>
        </div>
    )
}

function AppointmentTypeConditionalFields({
    formData,
    validation,
    onFormDataChange,
}: {
    formData: AppointmentTypeFormState
    validation: AppointmentTypeValidation
    onFormDataChange: AppointmentTypeFormUpdater
}) {
    return (
        <>
            {formData.meeting_modes.includes("in_person") && (
                <ValidatedField label="Location" error={validation.errorFor("meeting_location")}>
                    {(control) => (
                        <Input
                            {...control}
                            value={formData.meeting_location}
                            onChange={(e) => onFormDataChange((current) => ({ ...current, meeting_location: e.target.value }))}
                            onBlur={() => validation.touch("meeting_location")}
                            placeholder="e.g., 123 Main St, Suite 4B"
                        />
                    )}
                </ValidatedField>
            )}
            {formData.meeting_modes.includes("phone") && (
                <ValidatedField label="Dial-in Number" error={validation.errorFor("dial_in_number")}>
                    {(control) => (
                        <Input
                            {...control}
                            value={formData.dial_in_number}
                            onChange={(e) => onFormDataChange((current) => ({ ...current, dial_in_number: e.target.value }))}
                            onBlur={() => validation.touch("dial_in_number")}
                            placeholder="e.g., +1 (555) 123-4567"
                        />
                    )}
                </ValidatedField>
            )}
            <div className="flex items-start gap-3 rounded-lg border border-border p-3">
                <Switch
                    id="appointment-type-auto-approve"
                    checked={formData.auto_approve}
                    onCheckedChange={(checked) =>
                        onFormDataChange((current) => ({ ...current, auto_approve: checked }))
                    }
                />
                <div>
                    <Label htmlFor="appointment-type-auto-approve" className="text-sm">Auto-approve bookings</Label>
                    <p className="text-xs text-muted-foreground">
                        Clients will be instantly confirmed without manual approval.
                    </p>
                </div>
            </div>
        </>
    )
}

function AppointmentTypesEmptyState({ onCreate }: { onCreate: () => void }) {
    return (
        <EmptyState
            icon={CalendarIcon}
            title="No appointment types"
            action={
                <Button variant="outline" size="sm" onClick={onCreate}>
                    <PlusIcon className="size-4" aria-hidden="true" />
                    Add type
                </Button>
            }
        />
    )
}

function AppointmentTypesList({
    types,
    onEdit,
    onDelete,
}: {
    types: AppointmentType[]
    onEdit: (type: AppointmentType) => void
    onDelete: (typeId: string) => void
}) {
    return (
        <div className="space-y-3">
            {types.map((type) => (
                <AppointmentTypeListItem
                    key={type.id}
                    type={type}
                    onEdit={onEdit}
                    onDelete={onDelete}
                />
            ))}
        </div>
    )
}

function AppointmentTypeListItem({
    type,
    onEdit,
    onDelete,
}: {
    type: AppointmentType
    onEdit: (type: AppointmentType) => void
    onDelete: (typeId: string) => void
}) {
    const meetingModes =
        type.meeting_modes && type.meeting_modes.length > 0
            ? type.meeting_modes
            : [type.meeting_mode]
    const primaryMode = meetingModes[0]
    const ModeIcon = MEETING_MODE_OPTIONS.find((option) => option.value === primaryMode)?.icon || VideoIcon
    const formatLabel = meetingModes
        .map((mode) => MEETING_MODE_LABELS[mode] || mode)
        .join(" / ")

    return (
        <div className="flex items-center justify-between p-4 rounded-lg border border-border">
            <div className="flex items-center gap-4">
                <div className="p-2 rounded-lg bg-primary/10">
                    <ModeIcon className="size-5 text-primary" />
                </div>
                <div>
                    <h4 className="font-medium">{type.name}</h4>
                    <p className="text-sm text-muted-foreground">
                        {type.duration_minutes} min
                        {type.description && ` • ${type.description}`}
                        {formatLabel && ` • ${formatLabel}`}
                    </p>
                    {meetingModes.includes("in_person") && type.meeting_location && (
                        <p className="text-xs text-muted-foreground mt-1">
                            Location: {type.meeting_location}
                        </p>
                    )}
                    {meetingModes.includes("phone") && type.dial_in_number && (
                        <p className="text-xs text-muted-foreground mt-1">
                            Dial-in: {type.dial_in_number}
                        </p>
                    )}
                </div>
            </div>
            <div className="flex items-center gap-2">
                <Badge variant={type.is_active ? "default" : "secondary"}>
                    {type.is_active ? "Active" : "Inactive"}
                </Badge>
                {type.auto_approve && (
                    <Badge variant="outline">Auto-approve</Badge>
                )}
                <Button variant="ghost" size="sm" onClick={() => onEdit(type)}>
                    Edit
                </Button>
                <Button
                    variant="ghost"
                    size="icon-sm"
                    className="text-destructive"
                    onClick={() => onDelete(type.id)}
                    aria-label={`Deactivate ${type.name}`}
                    title="Deactivate"
                >
                    <PowerOffIcon className="size-4" aria-hidden="true" />
                </Button>
            </div>
        </div>
    )
}

function AppointmentTypesCard() {
    const { data: types, isLoading } = useAppointmentTypes()
    const createMutation = useCreateAppointmentType()
    const updateMutation = useUpdateAppointmentType()
    const deleteMutation = useDeleteAppointmentType()
    const [dialogOpen, setDialogOpen] = useState(false)
    const [editingType, setEditingType] = useState<AppointmentType | null>(null)
    const [pendingDeactivateId, setPendingDeactivateId] = useState<string | null>(null)
    const [formData, setFormData] = useState<AppointmentTypeFormState>({
        name: "",
        description: "",
        duration_minutes: 30,
        buffer_after_minutes: 5,
        meeting_modes: ["zoom"] as MeetingMode[],
        meeting_location: "",
        dial_in_number: "",
        auto_approve: false,
        reminder_hours_before: 24,
    })

    const validation = useFormValidation({ values: formData, validate: validateAppointmentTypeForm })

    const openCreate = () => {
        validation.reset()
        setEditingType(null)
        setFormData({
            name: "",
            description: "",
            duration_minutes: 30,
            buffer_after_minutes: 5,
            meeting_modes: ["zoom"],
            meeting_location: "",
            dial_in_number: "",
            auto_approve: false,
            reminder_hours_before: 24,
        })
        setDialogOpen(true)
    }

    const openEdit = (type: AppointmentType) => {
        validation.reset()
        setEditingType(type)
        const meetingModes =
            type.meeting_modes && type.meeting_modes.length > 0
                ? type.meeting_modes
                : [type.meeting_mode]
        setFormData({
            name: type.name,
            description: type.description || "",
            duration_minutes: type.duration_minutes,
            buffer_after_minutes: type.buffer_after_minutes,
            meeting_modes: meetingModes as MeetingMode[],
            meeting_location: type.meeting_location || "",
            dial_in_number: type.dial_in_number || "",
            auto_approve: type.auto_approve ?? false,
            reminder_hours_before: type.reminder_hours_before,
        })
        setDialogOpen(true)
    }

    const toggleMeetingMode = (mode: MeetingMode, checked: boolean | "indeterminate") => {
        const shouldSelect = checked === true
        setFormData((prev) => {
            const hasMode = prev.meeting_modes.includes(mode)
            const nextModes = shouldSelect
                ? hasMode
                    ? prev.meeting_modes
                    : [...prev.meeting_modes, mode]
                : prev.meeting_modes.filter((m) => m !== mode)
            if (nextModes.length === 0) {
                return prev
            }
            return { ...prev, meeting_modes: nextModes }
        })
    }

    const handleSubmit = validation.handleSubmit(async (values) => {
        // The format toggles never allow an empty selection, so a primary mode always exists.
        const orderedModes = MEETING_MODE_OPTIONS
            .map((option) => option.value)
            .filter((mode) => values.meeting_modes.includes(mode))
        const primaryMode = orderedModes[0]
        if (!primaryMode) return

        const payload = {
            ...values,
            name: values.name.trim(),
            meeting_modes: orderedModes,
            meeting_mode: primaryMode,
            meeting_location: values.meeting_location.trim() || null,
            dial_in_number: values.dial_in_number.trim() || null,
        }

        try {
            if (editingType) {
                await updateMutation.mutateAsync({ typeId: editingType.id, data: payload })
                toast.success("Appointment type updated")
            } else {
                await createMutation.mutateAsync(payload)
                toast.success("Appointment type created")
            }
            setDialogOpen(false)
        } catch (error) {
            const formError = validation.applyApiError(error, {
                fields: ["name", "description", "meeting_location", "dial_in_number"],
                fallback: "Couldn't save appointment type. Try again.",
            })
            if (formError) toast.error(formError)
        }
    })

    const pendingDeactivateType = types?.find((type) => type.id === pendingDeactivateId)

    // Runs from ConfirmDialog, which stays open while it runs and shows a failure inline.
    const handleDeactivate = async (typeId: string) => {
        await deleteMutation.mutateAsync(typeId)
        toast.success("Appointment type deactivated")
    }

    if (isLoading) {
        return <AppointmentTypesLoadingCard />
    }

    return (
        <Card>
            <AppointmentTypesHeader
                dialogOpen={dialogOpen}
                editingType={editingType}
                formData={formData}
                isSaving={createMutation.isPending || updateMutation.isPending}
                validation={validation}
                onDialogOpenChange={setDialogOpen}
                onCreate={openCreate}
                onFormDataChange={setFormData}
                onToggleMeetingMode={toggleMeetingMode}
                onSubmit={(event) => {
                    void handleSubmit(event)
                }}
            />
            <CardContent>
                {types?.length === 0 ? (
                    <AppointmentTypesEmptyState onCreate={openCreate} />
                ) : (
                    <AppointmentTypesList
                        types={types ?? []}
                        onEdit={openEdit}
                        onDelete={setPendingDeactivateId}
                    />
                )}
            </CardContent>
            <ConfirmDialog
                open={pendingDeactivateId !== null}
                onOpenChange={(open) => { if (!open) setPendingDeactivateId(null) }}
                title={`Deactivate ${pendingDeactivateType?.name ?? "this appointment type"}?`}
                description="It stops appearing on your booking page."
                confirmLabel="Deactivate"
                confirmIcon={<PowerOffIcon aria-hidden="true" />}
                errorFallback="Couldn't deactivate this appointment type. Try again."
                onConfirm={() => (pendingDeactivateId ? handleDeactivate(pendingDeactivateId) : undefined)}
            />
        </Card>
    )
}

// =============================================================================
// Main Export
// =============================================================================

const SETTINGS_TABS = ["availability", "types", "link"] as const

export function AppointmentSettings() {
    const [tab, setTab] = useTabSearchParam(SETTINGS_TABS, "availability")

    return (
        <div className="space-y-6">
            <GoogleCalendarWarningBanner />
            <Tabs value={tab} onValueChange={setTab} className="w-full">
                <TabsList>
                    <TabsTrigger value="availability">Availability</TabsTrigger>
                    <TabsTrigger value="types">Appointment Types</TabsTrigger>
                    <TabsTrigger value="link">Booking Link</TabsTrigger>
                </TabsList>

                <TabsContent value="availability" className="mt-6">
                    <AvailabilityRulesCard />
                </TabsContent>

                <TabsContent value="types" className="mt-6">
                    <AppointmentTypesCard />
                </TabsContent>

                <TabsContent value="link" className="mt-6">
                    <BookingLinkCard />
                </TabsContent>
            </Tabs>
        </div>
    )
}
