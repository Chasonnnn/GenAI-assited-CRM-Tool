import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import * as appointmentApi from "@/lib/api/interview-appointment"
import { surrogateKeys } from "@/lib/hooks/use-surrogates"
import { appointmentKeys } from "@/lib/hooks/use-appointments"

export const interviewAppointmentKeys = {
    detail: (id: string) => ["surrogates", "interview-appointment", id] as const,
}

export function useInterviewAppointment(surrogateId: string) {
    return useQuery({
        queryKey: interviewAppointmentKeys.detail(surrogateId),
        queryFn: () => appointmentApi.getInterviewAppointment(surrogateId),
        enabled: Boolean(surrogateId),
        retry: false,
        refetchInterval: 30_000,
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
