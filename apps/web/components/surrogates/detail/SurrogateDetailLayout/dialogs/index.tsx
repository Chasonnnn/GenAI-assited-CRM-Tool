"use client"

import { EmailComposeDialog } from "@/components/email/EmailComposeDialog"
import { ProposeMatchDialog } from "@/components/matches/ProposeMatchDialog"
import { LogContactAttemptDialog } from "@/components/surrogates/LogContactAttemptDialog"
import { LogInterviewOutcomeDialog } from "@/components/surrogates/LogInterviewOutcomeDialog"
import { ChangeStageModal } from "@/components/surrogates/ChangeStageModal"
import { useAuth } from "@/lib/auth-context"
import {
    useSurrogateDetailActions,
    useSurrogateDetailData,
    useSurrogateDetailDialogs,
} from "../context"
import { EditDialog } from "./EditDialog"
import { ReleaseQueueDialog } from "./ReleaseQueueDialog"
import { ZoomMeetingDialog } from "./ZoomMeetingDialog"

export function Dialogs() {
    const { user } = useAuth()
    const {
        surrogate,
        visibleStageOptions,
        statusLabel,
        canEditSurrogate,
        canManageQueue,
        canChangeStage,
        effectivePermissions,
    } = useSurrogateDetailData()
    const { activeDialog, closeDialog } = useSurrogateDetailDialogs()
    const {
        changeStatus,
        isChangeStatusPending,
    } = useSurrogateDetailActions()

    if (!surrogate) return null
    const isV2 = effectivePermissions?.policy_version === 2
    const canSendEmail = !isV2 || effectivePermissions.permissions.includes("send_email")
    const canProposeMatch = !isV2 || ["view_matches", "propose_matches", "view_intended_parents"].every((permission) => effectivePermissions.permissions.includes(permission))

    return (
        <>
            {canEditSurrogate && <EditDialog />}
            {(!isV2 || canManageQueue) && <ReleaseQueueDialog />}
            {(!isV2 || effectivePermissions.permissions.includes("manage_appointments")) && <ZoomMeetingDialog />}

            <EmailComposeDialog
                open={activeDialog.type === "email" && canSendEmail}
                onOpenChange={(open) => !open && closeDialog()}
                surrogateData={{
                    id: surrogate.id,
                    email: surrogate.email,
                    full_name: surrogate.full_name,
                    surrogate_number: surrogate.surrogate_number,
                    status: surrogate.status_label,
                    ...(surrogate.state ? { state: surrogate.state } : {}),
                    ...(surrogate.phone ? { phone: surrogate.phone } : {}),
                    ...(surrogate.owner_name ? { owner_name: surrogate.owner_name } : {}),
                }}
            />

            <ProposeMatchDialog
                open={activeDialog.type === "propose_match" && canProposeMatch}
                onOpenChange={(open) => !open && closeDialog()}
                surrogateId={surrogate.id}
                surrogateName={surrogate.full_name}
            />

            <LogContactAttemptDialog
                open={activeDialog.type === "log_contact" && canEditSurrogate}
                onOpenChange={(open) => !open && closeDialog()}
                surrogateId={surrogate.id}
                surrogateName={surrogate.full_name}
            />

            {activeDialog.type === "log_interview_outcome" && canEditSurrogate && (
                <LogInterviewOutcomeDialog
                    open
                    onOpenChange={(open) => !open && closeDialog()}
                    surrogateId={surrogate.id}
                    surrogateName={surrogate.full_name}
                />
            )}

            <ChangeStageModal
                open={activeDialog.type === "change_stage" && (!isV2 || canChangeStage)}
                onOpenChange={(open) => !open && closeDialog()}
                stages={visibleStageOptions}
                currentStageId={surrogate.stage_id}
                comparisonStageId={surrogate.paused_from_stage_id ?? surrogate.stage_id}
                currentStageLabel={statusLabel}
                canSelfApproveRegression={["admin", "developer"].includes(user?.role ?? "")}
                onSubmit={changeStatus}
                isPending={isChangeStatusPending}
                deliveryFieldsEnabled
                initialDeliveryBabyGender={surrogate.delivery_baby_gender}
                initialDeliveryBabyWeight={surrogate.delivery_baby_weight}
                onHoldFollowUpAssigneeLabel={
                    surrogate.owner_type === "user"
                        ? surrogate.owner_name ?? "the current owner"
                        : "you"
                }
            />
        </>
    )
}

export { EditDialog } from "./EditDialog"
export { ReleaseQueueDialog } from "./ReleaseQueueDialog"
export { ZoomMeetingDialog } from "./ZoomMeetingDialog"
