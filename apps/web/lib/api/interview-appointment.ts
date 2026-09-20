import api from "@/lib/api"

export type InterviewAppointment = {
    id: string
    scheduled_start: string
    scheduled_end: string
    client_timezone: string
    status: string
    meeting_started_at: string | null
    meeting_ended_at: string | null
}

export type AppointmentStage = { id: string; label: string; color: string }

export type InterviewAppointmentState = {
    appointment: InterviewAppointment | null
    can_manage: boolean
    scheduled_stage: AppointmentStage | null
    reschedule_stage: AppointmentStage | null
}

export type ManageInterviewAppointmentPayload = {
    action: "schedule" | "reschedule" | "cancel"
    scheduled_start?: string
    move_stage: boolean
    expected_stage_id: string
    expected_appointment_id: string | null
    expected_scheduled_start: string | null
}

export const getInterviewAppointment = (surrogateId: string) =>
    api.get<InterviewAppointmentState>(`/surrogates/${surrogateId}/interview-appointment`)

export const manageInterviewAppointment = (surrogateId: string, payload: ManageInterviewAppointmentPayload) =>
    api.post<InterviewAppointmentState>(`/surrogates/${surrogateId}/interview-appointment`, payload)
