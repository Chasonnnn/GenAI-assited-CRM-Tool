import { ApiError } from "@/lib/api"

type AxiosDetailError = {
    response?: {
        data?: {
            detail?: unknown
        }
    }
}

type MessageError = {
    message?: unknown
}

type DetailError = {
    detail?: unknown
}

export function getErrorMessage(error: unknown, fallback: string): string {
    if (error instanceof ApiError && error.message) {
        return error.message
    }

    if (typeof error === "object" && error !== null) {
        const axiosDetail = (error as AxiosDetailError).response?.data?.detail
        if (typeof axiosDetail === "string" && axiosDetail.trim()) {
            return axiosDetail
        }

        const detail = (error as DetailError).detail
        if (typeof detail === "string" && detail.trim()) {
            return detail
        }

        const message = (error as MessageError).message
        if (typeof message === "string" && message.trim()) {
            return message
        }
    }

    if (error instanceof Error && error.message) {
        return error.message
    }

    return fallback
}
