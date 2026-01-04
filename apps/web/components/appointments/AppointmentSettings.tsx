"use client"

/**
 * Appointment Settings - Availability configuration for staff
 * 
 * Features:
 * - Booking link management
 * - Weekly availability grid
 * - Date overrides
 * - Appointment types management
 * - Gmail connection warning
 */

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
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
    CopyIcon,
    ClockIcon,
    PlusIcon,
    TrashIcon,
    RefreshCwIcon,
    CheckIcon,
    AlertCircleIcon,
    VideoIcon,
    PhoneIcon,
    MapPinIcon,
    LoaderIcon,
    MailIcon,
    ExternalLinkIcon,
    EyeIcon,
} from "lucide-react"
import { toast } from "sonner"
import { useAuth } from "@/lib/auth-context"
import { getErrorMessage } from "@/lib/errors"
import {
    useBookingLink,
    useRegenerateBookingLink,
    useAppointmentTypes,
    useCreateAppointmentType,
    useUpdateAppointmentType,
    useDeleteAppointmentType,
    useAvailabilityRules,
    useSetAvailabilityRules,
} from "@/lib/hooks/use-appointments"
import { useUserIntegrations } from "@/lib/hooks/use-user-integrations"
import type { AppointmentType } from "@/lib/api/appointments"

// =============================================================================
// Gmail Connection Warning Banner
// =============================================================================

function GmailWarningBanner() {
    const [dismissed, setDismissed] = useState(false)
    const { data: integrations, isLoading, isError } = useUserIntegrations()
    const gmailConnected = integrations?.some(
        (integration) =>
            integration.integration_type === "gmail" && integration.connected
    )

    if (dismissed || isLoading || isError || gmailConnected) return null

    return (
        <Alert className="mb-6 border-amber-500/50 bg-amber-50 dark:bg-amber-950/20">
            <MailIcon className="size-4 text-amber-600" />
            <AlertTitle className="text-amber-800 dark:text-amber-400">
                Gmail Integration Recommended
            </AlertTitle>
            <AlertDescription className="text-amber-700 dark:text-amber-300">
                <p className="mb-2">
                    Connect your Gmail account to enable calendar sync, automated email confirmations,
                    and appointment reminders for your clients.
                </p>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" className="border-amber-500 text-amber-700 hover:bg-amber-100">
                        <a href="/settings/integrations" className="flex items-center">
                            <ExternalLinkIcon className="size-3 mr-1" />
                            Connect Gmail
                        </a>
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
const MEETING_MODE_ICONS = {
    zoom: VideoIcon,
    phone: PhoneIcon,
    in_person: MapPinIcon,
}

// =============================================================================
// Booking Link Card
// =============================================================================

function BookingLinkCard() {
    const { data: link, isLoading } = useBookingLink()
    const regenerateMutation = useRegenerateBookingLink()
    const [copied, setCopied] = useState(false)

    const copyLink = () => {
        if (link?.full_url) {
            navigator.clipboard.writeText(link.full_url)
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        }
    }

    const openPreview = () => {
        const baseUrl =
            typeof window !== "undefined" ? `${window.location.origin}/book/preview` : "/book/preview"
        window.open(baseUrl, "_blank")
    }

    if (isLoading) {
        return (
            <Card>
                <CardContent className="py-8 flex items-center justify-center">
                    <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
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
                <CardDescription>
                    Share this link to let clients book appointments with you
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="flex gap-2">
                    <Input
                        readOnly
                        value={link?.full_url || `${typeof window !== 'undefined' ? window.location.origin : ''}/book/${link?.public_slug || ''}`}
                        className="font-mono text-sm"
                    />
                    <Button variant="outline" onClick={copyLink}>
                        {copied ? <CheckIcon className="size-4" /> : <CopyIcon className="size-4" />}
                    </Button>
                </div>
                <Button variant="outline" size="sm" onClick={openPreview}>
                    <EyeIcon className="size-4 mr-2" />
                    Preview Booking Page
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => regenerateMutation.mutate()}
                    disabled={regenerateMutation.isPending}
                >
                    <RefreshCwIcon className={`size-4 mr-2 ${regenerateMutation.isPending ? "animate-spin" : ""}`} />
                    Regenerate Link
                </Button>
                <p className="text-xs text-muted-foreground">
                    Regenerating will invalidate the current link. Any bookmarked links will stop working.
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
    const [localRules, setLocalRules] = useState<Array<{
        day_of_week: number
        start_time: string
        end_time: string
        enabled: boolean
    }>>([])
    const [timezone, setTimezone] = useState(user?.org_timezone || "America/Los_Angeles")
    const [hasChanges, setHasChanges] = useState(false)

    // Initialize local rules from API data
    useEffect(() => {
        if (rules && localRules.length === 0) {
            const initialRules = DAYS_OF_WEEK.map((day) => {
                const existing = rules.find((r) => r.day_of_week === day.value)
                return {
                    day_of_week: day.value,
                    start_time: existing?.start_time || "09:00",
                    end_time: existing?.end_time || "17:00",
                    enabled: !!existing,
                }
            })
            setLocalRules(initialRules)
            if (rules.length > 0) {
                setTimezone(rules[0].timezone)
            } else if (user?.org_timezone) {
                setTimezone(user.org_timezone)
            }
        }
    }, [rules, localRules.length, user?.org_timezone])

    const toggleDay = (dayValue: number) => {
        setLocalRules((prev) =>
            prev.map((r) =>
                r.day_of_week === dayValue ? { ...r, enabled: !r.enabled } : r
            )
        )
        setHasChanges(true)
    }

    const updateTime = (dayValue: number, field: "start_time" | "end_time", value: string) => {
        setLocalRules((prev) =>
            prev.map((r) =>
                r.day_of_week === dayValue ? { ...r, [field]: value } : r
            )
        )
        setHasChanges(true)
    }

    const saveRules = () => {
        const enabledRules = localRules
            .filter((r) => r.enabled)
            .map(({ day_of_week, start_time, end_time }) => ({
                day_of_week,
                start_time,
                end_time,
            }))
        setRulesMutation.mutate({ rules: enabledRules, timezone }, {
            onSuccess: () => setHasChanges(false),
        })
    }

    if (isLoading) {
        return (
            <Card>
                <CardContent className="py-8 flex items-center justify-center">
                    <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
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
                <CardDescription>
                    Set your regular working hours for each day of the week
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="space-y-3">
                    {DAYS_OF_WEEK.map((day) => {
                        const rule = localRules.find((r) => r.day_of_week === day.value)
                        return (
                            <div
                                key={day.value}
                                className="flex items-center gap-4 p-3 rounded-lg border border-border"
                            >
                                <Switch
                                    checked={rule?.enabled || false}
                                    onCheckedChange={() => toggleDay(day.value)}
                                />
                                <span className="w-24 font-medium">{day.label}</span>
                                {rule?.enabled ? (
                                    <>
                                        <Select
                                            value={rule.start_time}
                                            onValueChange={(v) => v && updateTime(day.value, "start_time", v)}
                                        >
                                            <SelectTrigger className="w-28">
                                                <SelectValue />
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
                                            <SelectTrigger className="w-28">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {TIME_OPTIONS.map((opt) => (
                                                    <SelectItem key={opt.value} value={opt.value}>
                                                        {opt.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </>
                                ) : (
                                    <span className="text-muted-foreground">Unavailable</span>
                                )}
                            </div>
                        )
                    })}
                </div>

                <div className="flex items-center justify-between pt-4 border-t border-border">
                    <div className="flex items-center gap-2">
                        <Label>Timezone:</Label>
                        <Select value={timezone} onValueChange={(v) => { if (v) { setTimezone(v); setHasChanges(true) } }}>
                            <SelectTrigger className="w-48">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="America/Los_Angeles">Pacific Time</SelectItem>
                                <SelectItem value="America/New_York">Eastern Time</SelectItem>
                                <SelectItem value="America/Chicago">Central Time</SelectItem>
                                <SelectItem value="America/Denver">Mountain Time</SelectItem>
                                <SelectItem value="UTC">UTC</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <Button
                        onClick={saveRules}
                        disabled={!hasChanges || setRulesMutation.isPending}
                    >
                        {setRulesMutation.isPending ? (
                            <LoaderIcon className="size-4 mr-2 animate-spin" />
                        ) : null}
                        Save Availability
                    </Button>
                </div>
            </CardContent>
        </Card>
    )
}

// =============================================================================
// Appointment Types Card
// =============================================================================

function AppointmentTypesCard() {
    const { data: types, isLoading } = useAppointmentTypes()
    const createMutation = useCreateAppointmentType()
    const updateMutation = useUpdateAppointmentType()
    const deleteMutation = useDeleteAppointmentType()
    const [dialogOpen, setDialogOpen] = useState(false)
    const [editingType, setEditingType] = useState<AppointmentType | null>(null)
    const [formData, setFormData] = useState({
        name: "",
        description: "",
        duration_minutes: 30,
        buffer_after_minutes: 5,
        meeting_mode: "zoom" as "zoom" | "phone" | "in_person",
        reminder_hours_before: 24,
    })

    const openCreate = () => {
        setEditingType(null)
        setFormData({
            name: "",
            description: "",
            duration_minutes: 30,
            buffer_after_minutes: 5,
            meeting_mode: "zoom",
            reminder_hours_before: 24,
        })
        setDialogOpen(true)
    }

    const openEdit = (type: AppointmentType) => {
        setEditingType(type)
        setFormData({
            name: type.name,
            description: type.description || "",
            duration_minutes: type.duration_minutes,
            buffer_after_minutes: type.buffer_after_minutes,
            meeting_mode: type.meeting_mode,
            reminder_hours_before: type.reminder_hours_before,
        })
        setDialogOpen(true)
    }

    const handleSubmit = async () => {
        if (!formData.name.trim()) {
            toast.error("Appointment type name is required")
            return
        }

        try {
            if (editingType) {
                await updateMutation.mutateAsync({ typeId: editingType.id, data: formData })
                toast.success("Appointment type updated")
            } else {
                await createMutation.mutateAsync(formData)
                toast.success("Appointment type created")
            }
            setDialogOpen(false)
        } catch (error) {
            toast.error(getErrorMessage(error, "Failed to save appointment type"))
        }
    }

    const handleDelete = (typeId: string) => {
        if (confirm("Are you sure you want to deactivate this appointment type?")) {
            deleteMutation.mutate(typeId, {
                onSuccess: () => toast.success("Appointment type deactivated"),
                onError: (error) => toast.error(getErrorMessage(error, "Failed to deactivate appointment type")),
            })
        }
    }

    if (isLoading) {
        return (
            <Card>
                <CardContent className="py-8 flex items-center justify-center">
                    <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
                </CardContent>
            </Card>
        )
    }

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between">
                <div>
                    <CardTitle>Appointment Types</CardTitle>
                    <CardDescription>
                        Different appointment types clients can book
                    </CardDescription>
                </div>
                <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                    <Button onClick={openCreate}>
                        <PlusIcon className="size-4 mr-2" />
                        Add Type
                    </Button>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>
                                {editingType ? "Edit Appointment Type" : "New Appointment Type"}
                            </DialogTitle>
                            <DialogDescription>
                                Configure the details for this appointment type
                            </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                            <div className="space-y-2">
                                <Label>Name</Label>
                                <Input
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    placeholder="e.g., Initial Consultation"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Description</Label>
                                <Textarea
                                    value={formData.description}
                                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                    placeholder="Brief description of this appointment type"
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>Duration (minutes)</Label>
                                    <Select
                                        value={String(formData.duration_minutes)}
                                        onValueChange={(v) =>
                                            v && setFormData({ ...formData, duration_minutes: parseInt(v) })
                                        }
                                    >
                                        <SelectTrigger>
                                            <SelectValue />
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
                                    <Label>Buffer After</Label>
                                    <Select
                                        value={String(formData.buffer_after_minutes)}
                                        onValueChange={(v) =>
                                            v && setFormData({ ...formData, buffer_after_minutes: parseInt(v) })
                                        }
                                    >
                                        <SelectTrigger>
                                            <SelectValue />
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
                            <div className="space-y-2">
                                <Label>Appointment Format</Label>
                                <Select
                                    value={formData.meeting_mode}
                                    onValueChange={(v) =>
                                        v && setFormData({ ...formData, meeting_mode: v as "zoom" | "phone" | "in_person" })
                                    }
                                >
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="zoom">
                                            <div className="flex items-center gap-2">
                                                <VideoIcon className="size-4" /> Zoom
                                            </div>
                                        </SelectItem>
                                        <SelectItem value="phone">
                                            <div className="flex items-center gap-2">
                                                <PhoneIcon className="size-4" /> Phone
                                            </div>
                                        </SelectItem>
                                        <SelectItem value="in_person">
                                            <div className="flex items-center gap-2">
                                                <MapPinIcon className="size-4" /> In-Person
                                            </div>
                                        </SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                        <div className="flex justify-end gap-2">
                            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
                            <Button
                                onClick={handleSubmit}
                                disabled={!formData.name || createMutation.isPending || updateMutation.isPending}
                            >
                                {(createMutation.isPending || updateMutation.isPending) ? (
                                    <LoaderIcon className="size-4 mr-2 animate-spin" />
                                ) : null}
                                {editingType ? "Save Changes" : "Create Type"}
                            </Button>
                        </div>
                    </DialogContent>
                </Dialog>
            </CardHeader>
            <CardContent>
                {types?.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                        <AlertCircleIcon className="size-8 mx-auto mb-2 opacity-50" />
                        <p>No appointment types yet</p>
                        <p className="text-sm">Create your first appointment type to start accepting bookings</p>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {types?.map((type) => {
                            const ModeIcon = MEETING_MODE_ICONS[type.meeting_mode]
                            return (
                                <div
                                    key={type.id}
                                    className="flex items-center justify-between p-4 rounded-lg border border-border"
                                >
                                    <div className="flex items-center gap-4">
                                        <div className="p-2 rounded-lg bg-primary/10">
                                            <ModeIcon className="size-5 text-primary" />
                                        </div>
                                        <div>
                                            <h4 className="font-medium">{type.name}</h4>
                                            <p className="text-sm text-muted-foreground">
                                                {type.duration_minutes} min
                                                {type.description && ` • ${type.description}`}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Badge variant={type.is_active ? "default" : "secondary"}>
                                            {type.is_active ? "Active" : "Inactive"}
                                        </Badge>
                                        <Button variant="ghost" size="sm" onClick={() => openEdit(type)}>
                                            Edit
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="text-destructive"
                                            onClick={() => handleDelete(type.id)}
                                        >
                                            <TrashIcon className="size-4" />
                                        </Button>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

// =============================================================================
// Main Export
// =============================================================================

export function AppointmentSettings() {
    return (
        <div className="space-y-6">
            <GmailWarningBanner />
            <Tabs defaultValue="availability" className="w-full">
                <TabsList className="w-full justify-start">
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
