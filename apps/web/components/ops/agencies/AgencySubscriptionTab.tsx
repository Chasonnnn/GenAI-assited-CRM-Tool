"use client"

import { AlertTriangle, CalendarPlus } from "lucide-react"
import { format } from "date-fns"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import type { OrganizationSubscription } from "@/lib/api/platform"
import { PLAN_BADGE_VARIANTS, STATUS_BADGE_VARIANTS } from "@/components/ops/agencies/agency-constants"

type AgencySubscriptionTabProps = {
    subscription: OrganizationSubscription | null
    notesDraft: string
    notesDirty: boolean
    notesSaving: boolean
    onNotesChange: (value: string) => void
    onSaveNotes: () => void
    onExtendSubscription: () => void
    onToggleAutoRenew: (value: boolean) => void
}

export function AgencySubscriptionTab({
    subscription,
    notesDraft,
    notesDirty,
    notesSaving,
    onNotesChange,
    onSaveNotes,
    onExtendSubscription,
    onToggleAutoRenew,
}: AgencySubscriptionTabProps) {
    return (
        <div className="space-y-6">
            <div className="rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/30 p-4">
                <div className="flex items-start gap-3">
                    <AlertTriangle className="size-5 text-amber-600 mt-0.5" />
                    <div>
                        <p className="font-medium text-amber-800 dark:text-amber-200">
                            Billing Not Enforced
                        </p>
                        <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
                            Billing is managed offline. No automated charges are processed.
                        </p>
                    </div>
                </div>
            </div>

            {subscription && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg">Subscription Details</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="grid gap-4 md:grid-cols-3">
                            <div>
                                <Label className="text-muted-foreground">Plan</Label>
                                <div className="mt-1">
                                    <Badge className={PLAN_BADGE_VARIANTS[subscription.plan_key]}>
                                        {subscription.plan_key}
                                    </Badge>
                                </div>
                            </div>
                            <div>
                                <Label className="text-muted-foreground">Status</Label>
                                <div className="mt-1">
                                    <Badge className={STATUS_BADGE_VARIANTS[subscription.status]}>
                                        {subscription.status}
                                    </Badge>
                                </div>
                            </div>
                            <div>
                                <Label className="text-muted-foreground">Auto-Renew</Label>
                                <div className="mt-1">
                                    <Switch
                                        checked={subscription.auto_renew}
                                        onCheckedChange={onToggleAutoRenew}
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="grid gap-4 md:grid-cols-2">
                            <div>
                                <Label className="text-muted-foreground">Current Period End</Label>
                                <p className="mt-1 font-medium">
                                    {format(
                                        new Date(subscription.current_period_end),
                                        "MMMM d, yyyy"
                                    )}
                                </p>
                            </div>
                            {subscription.trial_end && (
                                <div>
                                    <Label className="text-muted-foreground">Trial End</Label>
                                    <p className="mt-1 font-medium">
                                        {format(
                                            new Date(subscription.trial_end),
                                            "MMMM d, yyyy"
                                        )}
                                    </p>
                                </div>
                            )}
                        </div>

                        <div>
                            <Label className="text-muted-foreground">Notes</Label>
                            <Textarea
                                className="mt-1"
                                value={notesDraft}
                                onChange={(event) => onNotesChange(event.target.value)}
                                placeholder="Internal notes about this subscription..."
                            />
                        </div>

                        <div className="flex gap-3 pt-4 border-t">
                            <Button variant="outline" onClick={onExtendSubscription}>
                                <CalendarPlus className="mr-2 size-4" />
                                Extend 30 Days
                            </Button>
                            <Button onClick={onSaveNotes} disabled={!notesDirty || notesSaving}>
                                {notesSaving ? "Saving..." : "Save Notes"}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    )
}
