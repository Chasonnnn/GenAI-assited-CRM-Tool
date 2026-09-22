"use client"

import { EmailComposeDialog } from "@/components/email/EmailComposeDialog"
import { ProposeMatchDialog } from "@/components/matches/ProposeMatchDialog"
import { LogContactAttemptDialog } from "@/components/surrogates/LogContactAttemptDialog"
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
import { InterviewAppointmentManager } from "@/components/surrogates/InterviewAppointmentManager"
import { stageMatchesKey } from "@/lib/surrogate-stage-context"

export function Dialogs() {
    const { user } = useAuth()
    const {
        surrogate,
        visibleStageOptions,
        statusLabel,
    } = useSurrogateDetailData()
    const { activeDialog, closeDialog } = useSurrogateDetailDialogs()
    const {
        changeStatus,
        isChangeStatusPending,
    } = useSurrogateDetailActions()

    if (!surrogate) return null

    return (
        <>
            <EditDialog />
            <ReleaseQueueDialog />
            <ZoomMeetingDialog />

            <EmailComposeDialog
                open={activeDialog.type === "email"}
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
                open={activeDialog.type === "propose_match"}
                onOpenChange={(open) => !open && closeDialog()}
                surrogateId={surrogate.id}
                surrogateName={surrogate.full_name}
            />

            <LogContactAttemptDialog
                open={activeDialog.type === "log_contact"}
                onOpenChange={(open) => !open && closeDialog()}
                surrogateId={surrogate.id}
                surrogateName={surrogate.full_name}
            />

            <ChangeStageModal
                open={activeDialog.type === "change_stage"}
                surrogateId={surrogate.id}
                onOpenChange={(open) => !open && closeDialog()}
                stages={visibleStageOptions}
                currentStageId={surrogate.stage_id}
                comparisonStageId={surrogate.paused_from_stage_id ?? surrogate.stage_id}
                currentStageLabel={statusLabel}
                canSelfApproveRegression={["admin", "developer"].includes(user?.role ?? "")}
                appointmentManager={
                    (stageMatchesKey(surrogate, "interview_scheduled") || stageMatchesKey(surrogate, "reschedule_needed"))
                        ? <InterviewAppointmentManager surrogateId={surrogate.id} stageId={surrogate.stage_id} compact />
                        : undefined
                }
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
