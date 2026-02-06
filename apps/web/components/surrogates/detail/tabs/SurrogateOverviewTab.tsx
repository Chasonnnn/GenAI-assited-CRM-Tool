"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { TabsContent } from "@/components/ui/tabs"
import { InlineEditField } from "@/components/inline-edit-field"
import { InsuranceInfoCard } from "@/components/surrogates/InsuranceInfoCard"
import { MedicalInfoCard } from "@/components/surrogates/MedicalInfoCard"
import { ActivityTimeline } from "@/components/surrogates/ActivityTimeline"
import { PregnancyTrackerCard } from "@/components/surrogates/PregnancyTrackerCard"
import { SurrogateOverviewCard } from "@/components/surrogates/SurrogateOverviewCard"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import { useSurrogateActivity, useUpdateSurrogate } from "@/lib/hooks/use-surrogates"
import { useTasks } from "@/lib/hooks/use-tasks"
import { ClipboardCheckIcon, CopyIcon, InfoIcon, CheckIcon, UserIcon, XIcon } from "lucide-react"
import { computeBmi, formatDate } from "@/components/surrogates/detail/surrogate-detail-utils"
import { useSurrogateDetailContext } from "@/components/surrogates/detail/SurrogateDetailContext"
import { formatRace } from "@/lib/formatters"

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
    const readyToMatchStage = React.useMemo(
        () => stageOptions.find((stage) => stage.slug === "ready_to_match"),
        [stageOptions]
    )
    const heartbeatStage = React.useMemo(
        () => stageOptions.find((stage) => stage.slug === "heartbeat_confirmed"),
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

    if (!surrogateData) {
        return null
    }

    const currentStage = stageById.get(surrogateData.stage_id)
    const isReadyToMatchOrLater = !!(
        currentStage &&
        readyToMatchStage &&
        currentStage.order >= readyToMatchStage.order
    )
    const isHeartbeatConfirmedOrLater = !!(
        currentStage &&
        heartbeatStage &&
        currentStage.order >= heartbeatStage.order
    )

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
                                    <span className="text-sm">
                                        {surrogateData.height_ft
                                            ? `${surrogateData.height_ft} ft`
                                            : "-"}
                                    </span>
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

                    <InsuranceInfoCard
                        surrogateData={surrogateData}
                        onUpdate={async (data) => {
                            await updateSurrogateMutation.mutateAsync({
                                surrogateId: id,
                                data,
                            })
                        }}
                    />

                    {isReadyToMatchOrLater && (
                        <MedicalInfoCard
                            surrogateData={surrogateData}
                            onUpdate={async (data) => {
                                await updateSurrogateMutation.mutateAsync({
                                    surrogateId: id,
                                    data,
                                })
                            }}
                        />
                    )}
                </div>

                <div className="space-y-4">
                    {isHeartbeatConfirmedOrLater && (
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
                    />

                    <SurrogateOverviewCard title="Eligibility Checklist" icon={ClipboardCheckIcon}>
                        {[
                            { label: "Age Eligible (18-42)", value: surrogateData.is_age_eligible },
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
