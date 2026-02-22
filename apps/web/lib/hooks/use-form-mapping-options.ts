import { useQuery } from "@tanstack/react-query"

import {
    listFormMappingOptions,
    DEFAULT_FORM_SURROGATE_FIELD_OPTIONS,
    type FormSurrogateFieldOption,
} from "@/lib/api/forms"

const FORM_MAPPING_OPTIONS_QUERY_KEY = ["forms", "mapping-options"] as const

export function useFormMappingOptions() {
    return useQuery<FormSurrogateFieldOption[]>({
        queryKey: FORM_MAPPING_OPTIONS_QUERY_KEY,
        queryFn: async () => {
            try {
                const options = await listFormMappingOptions()
                if (options.length > 0) {
                    return options
                }
            } catch {
                // Backend endpoint may not exist in all environments.
            }

            return DEFAULT_FORM_SURROGATE_FIELD_OPTIONS
        },
        retry: false,
    })
}
