import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import * as appointmentApi from "@/lib/api/interview-appointment"
import { surrogateKeys } from "@/lib/hooks/use-surrogates"
import { appointmentKeys } from "@/lib/hooks/use-appointments"

export const interviewAppointmentKeys = {
    detail: surrogateKeys.interviewAppointment,
}

export function useInterviewAppointment(surrogateId: string) {
    return useQuery({
        queryKey: interviewAppointmentKeys.detail(surrogateId),
        queryFn: () => appointmentApi.getInterviewAppointment(surrogateId),
        enabled: Boolean(surrogateId),
        retry: false,
        refetchInterval: (query) => query.state.data?.external_sync_status === "pending" ? 2_000 : 30_000,
    })
}

export function useManageInterviewAppointment(surrogateId: string) {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (payload: appointmentApi.ManageInterviewAppointmentPayload) =>
            appointmentApi.manageInterviewAppointment(surrogateId, payload),
        onSuccess: (state) => {
            queryClient.setQueryData(interviewAppointmentKeys.detail(surrogateId), state)
            for (const key of [
                surrogateKeys.detail(surrogateId), surrogateKeys.activity(surrogateId),
                surrogateKeys.history(surrogateId), surrogateKeys.lists(), ["interviews", surrogateId],
                appointmentKeys.all,
            ]) void queryClient.invalidateQueries({ queryKey: key })
        },
        onError: () => {
            void queryClient.invalidateQueries({ queryKey: interviewAppointmentKeys.detail(surrogateId) })
            void queryClient.invalidateQueries({ queryKey: surrogateKeys.detail(surrogateId) })
        },
    })
}

export function useRetryInterviewAppointmentGoogleSync(surrogateId: string) {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (expectedAppointmentId: string) =>
            appointmentApi.retryInterviewAppointmentGoogleSync(surrogateId, expectedAppointmentId),
        onSuccess: (state) => {
            queryClient.setQueryData(interviewAppointmentKeys.detail(surrogateId), state)
            void queryClient.invalidateQueries({ queryKey: appointmentKeys.all })
        },
        onError: () => {
            void queryClient.invalidateQueries({ queryKey: interviewAppointmentKeys.detail(surrogateId) })
        },
    })
}
