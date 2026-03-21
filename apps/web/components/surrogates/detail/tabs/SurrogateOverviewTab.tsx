"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { TabsContent } from "@/components/ui/tabs"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { InlineEditField } from "@/components/inline-edit-field"
import { CombinedMedicalInsuranceCard } from "@/components/surrogates/CombinedMedicalInsuranceCard"
import { ActivityTimeline } from "@/components/surrogates/ActivityTimeline"
import { PregnancyTrackerCard } from "@/components/surrogates/PregnancyTrackerCard"
import { SurrogateOverviewCard } from "@/components/surrogates/SurrogateOverviewCard"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import { useSurrogateActivity, useUpdateSurrogate } from "@/lib/hooks/use-surrogates"
import { useTasks } from "@/lib/hooks/use-tasks"
import {
    AlertTriangleIcon,
    ClipboardCheckIcon,
    CopyIcon,
    InfoIcon,
    CheckIcon,
    UserIcon,
    XIcon,
} from "lucide-react"
import { computeBmi, formatDate, formatHeight } from "@/components/surrogates/detail/surrogate-detail-utils"
import { useSurrogateDetailContext } from "@/components/surrogates/detail/SurrogateDetailContext"
import { formatRace } from "@/lib/formatters"
import { getSurrogateStageContext, stageHasCapability } from "@/lib/surrogate-stage-context"
import type { SurrogateLeadIntakeWarning } from "@/lib/types/surrogate"

const LEAD_WARNING_FIELD_LABELS = {
    email: "Email",
    phone: "Phone",
    height_ft: "Height",
    weight_lb: "Weight",
} as const

const LEAD_WARNING_REASON_LABELS = {
    invalid_value: "Invalid structured value",
    missing_value: "Missing structured value",
} as const

const LEAD_WARNING_REASON_COPY = {
    invalid_value: "This value could not be structured, so the field needs review.",
    missing_value: "This value could not be structured, so the field needs review.",
} as const

function LeadWarningIndicator({
    warning,
    fieldLabel,
}: {
    warning: SurrogateLeadIntakeWarning
    fieldLabel: string
}) {
    return (
        <Tooltip>
            <TooltipTrigger
                type="button"
                aria-label={`${fieldLabel} lead intake warning`}
                className="inline-flex size-5 shrink-0 items-center justify-center rounded-full border border-red-300/80 bg-[radial-gradient(circle_at_28%_28%,rgba(255,255,255,0.96),rgba(255,255,255,0.42)_34%,rgba(252,165,165,0.3)_38%,rgba(248,113,113,0.26)_62%,rgba(220,38,38,0.18)_100%)] text-red-600 shadow-[0_6px_16px_-10px_rgba(220,38,38,0.95),inset_0_1px_0_rgba(255,255,255,0.95)] transition-transform duration-150 hover:-translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-300/70 focus-visible:ring-offset-2"
            >
                <AlertTriangleIcon className="size-3.5" aria-hidden="true" />
            </TooltipTrigger>
            <TooltipContent className="max-w-64 px-3 py-2">
                <div className="space-y-1.5">
                    <div className="text-sm font-medium">{fieldLabel}</div>
                    <div className="text-[10px] uppercase tracking-[0.16em] text-background/70">
                        {LEAD_WARNING_REASON_LABELS[warning.issue]}
                    </div>
                    <p className="text-xs leading-relaxed text-background/88">
                        {LEAD_WARNING_REASON_COPY[warning.issue]}
                    </p>
                    <div className="border-t border-background/15 pt-1.5">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-background/70">
                            Raw lead value
                        </div>
                        <div className="mt-1 break-words text-xs font-medium">
                            {warning.raw_value}
                        </div>
                    </div>
                </div>
            </TooltipContent>
        </Tooltip>
    )
}

export function SurrogateOverviewTab() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const detailContext = useSurrogateDetailContext()
    const surrogateData = detailContext?.surrogate
    const { data: defaultPipeline } = useDefaultPipeline()
    const stageOptions = React.useMemo(() => defaultPipeline?.stages || [], [defaultPipeline])
    const stageById = React.useMemo(
        () => new Map(stageOptions.map((stage) => [stage.id, stage])),
        [stageOptions]
    )
    const { data: activityData } = useSurrogateActivity(id)
    const { data: tasksData } = useTasks({ surrogate_id: id, exclude_approvals: true })
    const updateSurrogateMutation = useUpdateSurrogate()
    const [copiedEmail, setCopiedEmail] = React.useState(false)

    const bmiValue = React.useMemo(() => {
        if (!surrogateData) return null
        if (typeof surrogateData.bmi === "number") return surrogateData.bmi
        return computeBmi(surrogateData.height_ft, surrogateData.weight_lb)
    }, [surrogateData])
    const stageContext = React.useMemo(
        () => getSurrogateStageContext(surrogateData ?? null, stageById),
        [surrogateData, stageById]
    )
    const leadIntakeWarnings = React.useMemo(
        () => surrogateData?.lead_intake_warnings ?? [],
        [surrogateData]
    )
    const leadWarningMap = React.useMemo(
        () => new Map(leadIntakeWarnings.map((warning) => [warning.field_key, warning])),
        [leadIntakeWarnings]
    )

    if (!surrogateData) {
        return null
    }

    const effectiveStage = stageContext.effectiveStage
    const isHeartbeatConfirmedOrLater = stageHasCapability(
        effectiveStage ?? { stage_key: surrogateData.stage_key, stage_slug: surrogateData.stage_slug },
        "shows_pregnancy_tracking"
    )
    const isTerminalIntakeOutcome =
        stageContext.effectiveStageKey === "lost" || stageContext.effectiveStageKey === "disqualified"
    const emailLeadWarning = leadWarningMap.get("email")
    const phoneLeadWarning = leadWarningMap.get("phone")
    const heightLeadWarning = leadWarningMap.get("height_ft")
    const weightLeadWarning = leadWarningMap.get("weight_lb")
    const hasMeasurementData =
        surrogateData.height_ft != null || surrogateData.weight_lb != null || bmiValue !== null
    const shouldShowHeightRow = hasMeasurementData || Boolean(heightLeadWarning)
    const shouldShowWeightRow = hasMeasurementData || Boolean(weightLeadWarning)

    const copyEmail = () => {
        navigator.clipboard.writeText(surrogateData.email)
        setCopiedEmail(true)
        setTimeout(() => setCopiedEmail(false), 2000)
    }

    return (
        <TabsContent value="overview" className="space-y-4">
            <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
                <div className="space-y-4">
                    <SurrogateOverviewCard title="Contact Information" icon={UserIcon}>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Name:</span>
                            <InlineEditField
                                value={surrogateData.full_name}
                                onSave={async (value) => {
                                    await updateSurrogateMutation.mutateAsync({
                                        surrogateId: id,
                                        data: { full_name: value },
                                    })
                                }}
                                placeholder="Enter name"
                                className="text-base font-medium"
                                label="Full name"
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Email:</span>
                            <div className="flex min-w-0 items-center gap-1.5">
                                <InlineEditField
                                    value={surrogateData.email}
                                    onSave={async (value) => {
                                        await updateSurrogateMutation.mutateAsync({
                                            surrogateId: id,
                                            data: { email: value },
                                        })
                                    }}
                                    type="email"
                                    placeholder="Enter email"
                                    validate={(value) => (!value.includes("@") ? "Invalid email" : null)}
                                    label="Email"
                                />
                                {emailLeadWarning && (
                                    <LeadWarningIndicator
                                        warning={emailLeadWarning}
                                        fieldLabel={LEAD_WARNING_FIELD_LABELS.email}
                                    />
                                )}
                            </div>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6"
                                onClick={copyEmail}
                                aria-label="Copy email"
                            >
                                {copiedEmail ? (
                                    <CheckIcon className="h-3 w-3" />
                                ) : (
                                    <CopyIcon className="h-3 w-3" />
                                )}
                            </Button>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Phone:</span>
                            <div className="flex min-w-0 items-center gap-1.5">
                                <InlineEditField
                                    value={surrogateData.phone ?? undefined}
                                    onSave={async (value) => {
                                        await updateSurrogateMutation.mutateAsync({
                                            surrogateId: id,
                                            data: { phone: value || null },
                                        })
                                    }}
                                    type="tel"
                                    placeholder="-"
                                    label="Phone"
                                />
                                {phoneLeadWarning && (
                                    <LeadWarningIndicator
                                        warning={phoneLeadWarning}
                                        fieldLabel={LEAD_WARNING_FIELD_LABELS.phone}
                                    />
                                )}
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">State:</span>
                            <InlineEditField
                                value={surrogateData.state ?? undefined}
                                onSave={async (value) => {
                                    await updateSurrogateMutation.mutateAsync({
                                        surrogateId: id,
                                        data: { state: value || null },
                                    })
                                }}
                                placeholder="-"
                                validate={(value) =>
                                    value && value.length !== 2
                                        ? "Use 2-letter code (e.g., CA, TX)"
                                        : null
                                }
                                label="State"
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Source:</span>
                            <Badge variant="secondary" className="capitalize">
                                {surrogateData.source}
                            </Badge>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Created:</span>
                            <span className="text-sm">{formatDate(surrogateData.created_at)}</span>
                        </div>
                    </SurrogateOverviewCard>

                    <SurrogateOverviewCard title="Demographics" icon={InfoIcon}>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Date of Birth:</span>
                            <span className="text-sm">
                                {surrogateData.date_of_birth
                                    ? formatDate(surrogateData.date_of_birth)
                                    : "-"}
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Race:</span>
                            <span className="text-sm">{formatRace(surrogateData.race) || "-"}</span>
                        </div>
                        {(shouldShowHeightRow ||
                            shouldShowWeightRow ||
                            bmiValue !== null) && (
                            <>
                                {shouldShowHeightRow && (
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm text-muted-foreground">Height:</span>
                                        <span className="text-sm">
                                            {surrogateData.height_ft != null
                                                ? formatHeight(surrogateData.height_ft)
                                                : "-"}
                                        </span>
                                        {heightLeadWarning && (
                                            <LeadWarningIndicator
                                                warning={heightLeadWarning}
                                                fieldLabel={LEAD_WARNING_FIELD_LABELS.height_ft}
                                            />
                                        )}
                                    </div>
                                )}
                                {shouldShowWeightRow && (
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm text-muted-foreground">Weight:</span>
                                        <span className="text-sm">
                                            {surrogateData.weight_lb != null
                                                ? `${surrogateData.weight_lb} lb`
                                                : "-"}
                                        </span>
                                        {weightLeadWarning && (
                                            <LeadWarningIndicator
                                                warning={weightLeadWarning}
                                                fieldLabel={LEAD_WARNING_FIELD_LABELS.weight_lb}
                                            />
                                        )}
                                    </div>
                                )}
                                <div className="flex items-center gap-2">
                                    <span className="text-sm text-muted-foreground">BMI:</span>
                                    <span className="text-sm">{bmiValue ?? "-"}</span>
                                </div>
                            </>
                        )}
                    </SurrogateOverviewCard>

                    <CombinedMedicalInsuranceCard
                        surrogateData={surrogateData}
                        onUpdate={async (data) => {
                            await updateSurrogateMutation.mutateAsync({
                                surrogateId: id,
                                data,
                            })
                        }}
                    />
                </div>

                <div className="space-y-4">
                    {isHeartbeatConfirmedOrLater && !isTerminalIntakeOutcome && (
                        <PregnancyTrackerCard
                            surrogateData={surrogateData}
                            onUpdate={async (data) => {
                                await updateSurrogateMutation.mutateAsync({
                                    surrogateId: id,
                                    data,
                                })
                            }}
                        />
                    )}

                    <ActivityTimeline
                        surrogateId={id}
                        currentStageId={surrogateData.stage_id}
                        stages={stageOptions}
                        activities={activityData?.items ?? []}
                        tasks={tasksData?.items ?? []}
                        {...(effectiveStage?.id ? { effectiveStageId: effectiveStage.id } : {})}
                    />

                    <SurrogateOverviewCard title="Eligibility Checklist" icon={ClipboardCheckIcon}>
                        {[
                            { label: "Age Eligible (21-36)", value: surrogateData.is_age_eligible },
                            { label: "US Citizen or PR", value: surrogateData.is_citizen_or_pr },
                            { label: "Has Child", value: surrogateData.has_child },
                            { label: "Non-Smoker", value: surrogateData.is_non_smoker },
                            {
                                label: "Prior Surrogate Experience",
                                value: surrogateData.has_surrogate_experience,
                            },
                        ].map(({ label, value }) => (
                            <div key={label} className="flex items-center gap-2">
                                {value === true && <CheckIcon className="h-4 w-4 text-green-500" />}
                                {value === false && <XIcon className="h-4 w-4 text-red-500" />}
                                {value === null && (
                                    <span className="h-4 w-4 text-center text-muted-foreground">
                                        -
                                    </span>
                                )}
                                <span className="text-sm">{label}</span>
                            </div>
                        ))}
                        {(surrogateData.num_deliveries !== null ||
                            surrogateData.num_csections !== null) && (
                            <div className="border-t pt-3 space-y-2">
                                {surrogateData.num_deliveries !== null && (
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm text-muted-foreground">
                                            Deliveries:
                                        </span>
                                        <span className="text-sm">
                                            {surrogateData.num_deliveries}
                                        </span>
                                    </div>
                                )}
                                {surrogateData.num_csections !== null && (
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm text-muted-foreground">
                                            C-Sections:
                                        </span>
                                        <span className="text-sm">
                                            {surrogateData.num_csections}
                                        </span>
                                    </div>
                                )}
                            </div>
                        )}
                    </SurrogateOverviewCard>
                </div>
            </div>
        </TabsContent>
    )
}
