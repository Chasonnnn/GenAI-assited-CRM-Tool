"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { TabsContent } from "@/components/ui/tabs"
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

const LEAD_WARNING_FIELD_LABELS = {
    email: "Email",
    phone: "Phone",
    height_ft: "Height",
    weight_lb: "Weight",
} as const

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

                    {leadIntakeWarnings.length > 0 && (
                        <Card
                            data-testid="lead-intake-review-card"
                            className="relative overflow-hidden border-amber-200/80 bg-[linear-gradient(145deg,rgba(255,251,235,0.96),rgba(255,255,255,0.9)_42%,rgba(254,243,199,0.72))] shadow-[0_20px_60px_-36px_rgba(217,119,6,0.55)]"
                        >
                            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(251,191,36,0.22),transparent_38%),radial-gradient(circle_at_80%_18%,rgba(255,255,255,0.85),transparent_24%)]" />
                            <div className="pointer-events-none absolute -right-10 top-3 h-24 w-24 rounded-full bg-amber-200/55 blur-3xl" />
                            <CardContent className="relative space-y-4 p-4">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="space-y-1">
                                        <div className="flex items-center gap-2 text-amber-900">
                                            <AlertTriangleIcon className="size-4" />
                                            <h3 className="text-sm font-semibold tracking-[0.01em]">
                                                Lead Intake Review
                                            </h3>
                                        </div>
                                        <p className="max-w-2xl text-sm text-amber-900/80">
                                            These fields did not land as valid structured data. Review the
                                            original lead values before outreach or qualification.
                                        </p>
                                    </div>
                                    <Badge
                                        variant="outline"
                                        className="border-amber-300 bg-white/70 text-amber-800 backdrop-blur-sm"
                                    >
                                        Needs review
                                    </Badge>
                                </div>

                                <div className="grid gap-3 md:grid-cols-2">
                                    {leadIntakeWarnings.map((warning) => (
                                        <div
                                            key={`${warning.field_key}-${warning.raw_value}`}
                                            className="rounded-2xl border border-amber-200/80 bg-white/72 px-3 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)] backdrop-blur-sm"
                                        >
                                            <div className="flex items-center justify-between gap-3">
                                                <span className="text-sm font-medium text-slate-900">
                                                    {
                                                        LEAD_WARNING_FIELD_LABELS[
                                                            warning.field_key as keyof typeof LEAD_WARNING_FIELD_LABELS
                                                        ]
                                                    }
                                                </span>
                                                <span className="text-[11px] font-medium uppercase tracking-[0.18em] text-amber-700">
                                                    {warning.issue === "invalid_value"
                                                        ? "Invalid"
                                                        : "Missing"}
                                                </span>
                                            </div>
                                            <div className="mt-2 text-xs text-slate-500">Raw lead value</div>
                                            <div className="mt-1 break-words text-sm font-medium text-slate-900">
                                                {warning.raw_value}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    )}

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
                        {(surrogateData.height_ft ||
                            surrogateData.weight_lb ||
                            bmiValue !== null) && (
                            <>
                                <div className="flex items-center gap-2">
                                    <span className="text-sm text-muted-foreground">Height:</span>
                                    <span className="text-sm">{formatHeight(surrogateData.height_ft)}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-sm text-muted-foreground">Weight:</span>
                                    <span className="text-sm">
                                        {surrogateData.weight_lb
                                            ? `${surrogateData.weight_lb} lb`
                                            : "-"}
                                    </span>
                                </div>
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
