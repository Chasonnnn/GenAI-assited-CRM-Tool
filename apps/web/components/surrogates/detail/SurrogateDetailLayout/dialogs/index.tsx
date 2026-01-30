"use client"

import { EmailComposeDialog } from "@/components/email/EmailComposeDialog"
import { ProposeMatchDialog } from "@/components/matches/ProposeMatchDialog"
import { LogContactAttemptDialog } from "@/components/surrogates/LogContactAttemptDialog"
import { ChangeStageModal } from "@/components/surrogates/ChangeStageModal"
import { useSurrogateDetailLayout } from "../context"
import { EditDialog } from "./EditDialog"
import { ReleaseQueueDialog } from "./ReleaseQueueDialog"
import { ZoomMeetingDialog } from "./ZoomMeetingDialog"

export function Dialogs() {
    const {
        surrogate,
        activeDialog,
        closeDialog,
        visibleStageOptions,
        statusLabel,
        changeStatus,
        isChangeStatusPending,
    } = useSurrogateDetailLayout()

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
                onOpenChange={(open) => !open && closeDialog()}
                stages={visibleStageOptions}
                currentStageId={surrogate.stage_id}
                currentStageLabel={statusLabel}
                onSubmit={changeStatus}
                isPending={isChangeStatusPending}
                deliveryFieldsEnabled
                initialDeliveryBabyGender={surrogate.delivery_baby_gender}
                initialDeliveryBabyWeight={surrogate.delivery_baby_weight}
            />
        </>
    )
}

export { EditDialog } from "./EditDialog"
export { ReleaseQueueDialog } from "./ReleaseQueueDialog"
export { ZoomMeetingDialog } from "./ZoomMeetingDialog"
