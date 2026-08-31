import { useQuery } from "@tanstack/react-query"

import {
    listFormMappingOptions,
    DEFAULT_FORM_DONOR_FIELD_OPTIONS,
    DEFAULT_FORM_SURROGATE_FIELD_OPTIONS,
    type FormLeadKind,
    type FormSurrogateFieldOption,
} from "@/lib/api/forms"
import { isDonorFormLeadKind } from "@/lib/forms/form-lead-kind"

const FORM_MAPPING_OPTIONS_QUERY_KEY = (leadKind: FormLeadKind) =>
    ["forms", "mapping-options", leadKind] as const

export function useFormMappingOptions(leadKind: FormLeadKind = "surrogate") {
    return useQuery<FormSurrogateFieldOption[]>({
        queryKey: FORM_MAPPING_OPTIONS_QUERY_KEY(leadKind),
        queryFn: async () => {
            try {
                const options = await listFormMappingOptions(leadKind)
                if (options.length > 0) {
                    return options
                }
            } catch {
                // Backend endpoint may not exist in all environments.
            }

            return isDonorFormLeadKind(leadKind)
                ? DEFAULT_FORM_DONOR_FIELD_OPTIONS
                : DEFAULT_FORM_SURROGATE_FIELD_OPTIONS
        },
        retry: false,
    })
}
