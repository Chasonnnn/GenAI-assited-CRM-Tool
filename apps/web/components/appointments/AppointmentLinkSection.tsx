"use client"

import { useState } from "react"
import { LinkIcon, Loader2Icon, XIcon } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { Appointment } from "@/lib/api/appointments"
import { useAuth } from "@/lib/auth-context"
import { useUpdateAppointmentLink } from "@/lib/hooks/use-appointments"
import { useIntendedParents } from "@/lib/hooks/use-intended-parents"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { useSurrogates } from "@/lib/hooks/use-surrogates"
import type { IntendedParentListItem } from "@/lib/types/intended-parent"
import type { SurrogateListItem } from "@/lib/types/surrogate"

type LinkableAppointment = Pick<
    Appointment,
    "id" | "surrogate_id" | "surrogate_number" | "intended_parent_id" | "intended_parent_name"
    | "donor_id" | "donor_name" | "match_id" | "attempt_id"
>

function getSurrogateSelectLabel(value: string | null, surrogates: SurrogateListItem[]) {
    if (!value || value === "none") return "None"
    const surrogate = surrogates.find((candidate) => candidate.id === value)
    return surrogate ? `#${surrogate.surrogate_number} - ${surrogate.full_name}` : "Selected surrogate"
}

function getIntendedParentSelectLabel(value: string | null, intendedParents: IntendedParentListItem[]) {
    if (!value || value === "none") return "None"
    const intendedParent = intendedParents.find((candidate) => candidate.id === value)
    if (!intendedParent) return "Selected intended parent"
    return intendedParent.intended_parent_number
        ? `#${intendedParent.intended_parent_number} - ${intendedParent.full_name}`
        : intendedParent.full_name
}

/** "Linked to" section of the appointment detail dialog: linked records, unlink, and an inline editor. */
export function AppointmentLinkSection({ appointment }: { appointment: LinkableAppointment }) {
    const [showEditor, setShowEditor] = useState(false)
    const [selectedSurrogateId, setSelectedSurrogateId] = useState<string | null>(appointment.surrogate_id)
    const [selectedIpId, setSelectedIpId] = useState<string | null>(appointment.intended_parent_id)

    const updateLinkMutation = useUpdateAppointmentLink()
    const { user } = useAuth()
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    const permissions = permissionsQuery.data?.permissions ?? []
    const permissionsLoaded = !permissionsQuery.isLoading
    const canViewIntendedParents = permissions.includes("view_intended_parents")

    // Record lists load only while the editor is open.
    const { data: surrogatesData } = useSurrogates({ per_page: 100 }, { enabled: showEditor })
    const { data: ipsData } = useIntendedParents(
        { per_page: 100 },
        { enabled: showEditor && canViewIntendedParents }
    )
    const surrogates = surrogatesData?.items || []
    const intendedParents = ipsData?.items || []

    const hasLink = Boolean(
        appointment.surrogate_id || appointment.intended_parent_id || appointment.donor_id
        || appointment.match_id || appointment.attempt_id
    )
    const surrogateLabel = appointment.surrogate_number ? `#${appointment.surrogate_number}` : "Linked surrogate"
    const intendedParentLabel = appointment.intended_parent_name || "Linked intended parent"
    const isSaving = updateLinkMutation.isPending

    const openEditor = () => {
        setSelectedSurrogateId(appointment.surrogate_id)
        setSelectedIpId(appointment.intended_parent_id)
        setShowEditor(true)
    }

    const handleSave = () => {
        updateLinkMutation.mutate(
            {
                appointmentId: appointment.id,
                data: { surrogate_id: selectedSurrogateId, intended_parent_id: selectedIpId },
            },
            { onSuccess: () => setShowEditor(false) }
        )
    }

    return (
        <section aria-labelledby={`appointment-links-${appointment.id}`} className="space-y-2 border-t border-border pt-4">
            <div className="flex items-center justify-between gap-2">
                <h3 id={`appointment-links-${appointment.id}`} className="flex items-center gap-2 text-sm font-medium">
                    <LinkIcon className="size-4 text-muted-foreground" aria-hidden="true" />
                    Linked to
                </h3>
                {!showEditor && (
                    <Button variant="ghost" size="sm" onClick={openEditor}>
                        {hasLink ? "Edit" : "Link"}
                    </Button>
                )}
            </div>

            {!showEditor ? (
                <div className="space-y-2">
                    {appointment.surrogate_id ? (
                        <div className="flex items-center justify-between rounded-md bg-muted/50 p-2">
                            <span className="text-sm">
                                <Badge variant="outline" className="mr-2">Surrogate</Badge>
                                {surrogateLabel}
                            </span>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => updateLinkMutation.mutate({ appointmentId: appointment.id, data: { surrogate_id: null } })}
                                disabled={isSaving}
                                aria-label={appointment.surrogate_number ? `Unlink surrogate ${appointment.surrogate_number}` : "Unlink surrogate"}
                            >
                                <XIcon className="size-4" aria-hidden="true" />
                            </Button>
                        </div>
                    ) : null}
                    {appointment.intended_parent_id ? (
                        <div className="flex items-center justify-between rounded-md bg-muted/50 p-2">
                            <span className="text-sm">
                                <Badge variant="outline" className="mr-2">IP</Badge>
                                {intendedParentLabel}
                            </span>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => updateLinkMutation.mutate({ appointmentId: appointment.id, data: { intended_parent_id: null } })}
                                disabled={isSaving}
                                aria-label={appointment.intended_parent_name ? `Unlink intended parent ${appointment.intended_parent_name}` : "Unlink intended parent"}
                            >
                                <XIcon className="size-4" aria-hidden="true" />
                            </Button>
                        </div>
                    ) : null}
                    {appointment.donor_id ? (
                        <div className="rounded-md bg-muted/50 p-2 text-sm">
                            <Badge variant="outline" className="mr-2">Donor</Badge>
                            {appointment.donor_name || "Linked donor"}
                        </div>
                    ) : null}
                    {appointment.match_id ? (
                        <div className="rounded-md bg-muted/50 p-2 text-sm">
                            <Badge variant="outline">Match case</Badge>
                        </div>
                    ) : null}
                    {appointment.attempt_id ? (
                        <div className="rounded-md bg-muted/50 p-2 text-sm">
                            <Badge variant="outline">Match attempt</Badge>
                        </div>
                    ) : null}
                    {!hasLink && <p className="text-sm text-muted-foreground">Not linked</p>}
                </div>
            ) : (
                <div className="space-y-3">
                    <div className="grid gap-1.5">
                        <Label htmlFor={`appointment-link-surrogate-${appointment.id}`}>Surrogate</Label>
                        <Select
                            value={selectedSurrogateId || "none"}
                            onValueChange={(value) => setSelectedSurrogateId(!value || value === "none" ? null : value)}
                        >
                            <SelectTrigger id={`appointment-link-surrogate-${appointment.id}`} className="w-full">
                                <SelectValue placeholder="None">
                                    {(value: string | null) => getSurrogateSelectLabel(value, surrogates)}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="none">None</SelectItem>
                                {surrogates.map((surrogate) => (
                                    <SelectItem key={surrogate.id} value={surrogate.id}>
                                        #{surrogate.surrogate_number} - {surrogate.full_name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="grid gap-1.5">
                        <Label htmlFor={`appointment-link-ip-${appointment.id}`}>Intended parent</Label>
                        {!canViewIntendedParents && permissionsLoaded ? (
                            <Alert>
                                <AlertDescription>
                                    Your role cannot view intended parents. Ask an admin to change your permissions.
                                </AlertDescription>
                            </Alert>
                        ) : (
                            <Select
                                value={selectedIpId || "none"}
                                onValueChange={(value) => setSelectedIpId(!value || value === "none" ? null : value)}
                            >
                                <SelectTrigger id={`appointment-link-ip-${appointment.id}`} className="w-full">
                                    <SelectValue placeholder="None">
                                        {(value: string | null) => getIntendedParentSelectLabel(value, intendedParents)}
                                    </SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="none">None</SelectItem>
                                    {intendedParents.map((intendedParent) => (
                                        <SelectItem key={intendedParent.id} value={intendedParent.id}>
                                            {intendedParent.intended_parent_number ? `#${intendedParent.intended_parent_number} - ` : ""}
                                            {intendedParent.full_name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}
                    </div>

                    <div className="flex items-center gap-2">
                        <Button size="sm" onClick={handleSave} disabled={isSaving}>
                            {isSaving ? <Loader2Icon className="mr-2 size-4 animate-spin" aria-hidden="true" /> : null}
                            Save links
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setShowEditor(false)} disabled={isSaving}>
                            Cancel
                        </Button>
                    </div>
                </div>
            )}
        </section>
    )
}
