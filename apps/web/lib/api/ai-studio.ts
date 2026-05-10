import api from "../api"

export type AIStudioPlatform = "instagram" | "facebook" | "linkedin" | "x" | "tiktok"
export type AIStudioFormat = "feed" | "story" | "reel" | "carousel" | "ad"
export type AIStudioTone = "warm" | "professional" | "bold" | "calm" | "educational"
type AIStudioDraftStatus = "preview" | "saved"
export type AIStudioImageSize =
    | "auto"
    | "1024x1024"
    | "1024x1536"
    | "1536x1024"
    | "2560x1440"
    | "3840x2160"
export type AIStudioImageQuality = "auto" | "high" | "medium" | "low"

export interface AIStudioSettings {
    has_api_key: boolean
    api_key_masked: string | null
    agents_md: string
    skills_md: string
    reasoning_model: "gpt-5.5"
    image_model: "gpt-image-2"
}

export interface AIStudioSettingsUpdate {
    api_key?: string
    agents_md?: string
    skills_md?: string
}

export interface AIStudioGenerateRequest {
    brief: string
    platform: AIStudioPlatform
    format: AIStudioFormat
    tone: AIStudioTone
    audience: string
    image_size: AIStudioImageSize
    image_quality: AIStudioImageQuality
}

export interface AIStudioDraft {
    id: string
    status: AIStudioDraftStatus
    platform: AIStudioPlatform
    format: AIStudioFormat
    tone: AIStudioTone
    audience: string
    brief: string
    caption: string
    hashtags: string[]
    image_prompt: string
    image_url: string | null
    image_revised_prompt: string | null
    image_size: AIStudioImageSize
    image_quality: AIStudioImageQuality
    reasoning_model: "gpt-5.5"
    image_model: "gpt-image-2"
    created_at: string
    updated_at: string
}

export interface AIStudioDraftsResponse {
    items: AIStudioDraft[]
}

export async function getAIStudioSettings(): Promise<AIStudioSettings> {
    return api.get<AIStudioSettings>("/ai/studio/settings")
}

export async function updateAIStudioSettings(
    update: AIStudioSettingsUpdate
): Promise<AIStudioSettings> {
    return api.patch<AIStudioSettings>("/ai/studio/settings", update)
}

export async function generateAIStudioDraft(
    request: AIStudioGenerateRequest
): Promise<AIStudioDraft> {
    return api.post<AIStudioDraft>("/ai/studio/generate", request)
}

export async function saveAIStudioDraft(draftId: string): Promise<AIStudioDraft> {
    return api.post<AIStudioDraft>(`/ai/studio/drafts/${draftId}/save`)
}

export async function listAIStudioDrafts(): Promise<AIStudioDraftsResponse> {
    return api.get<AIStudioDraftsResponse>("/ai/studio/drafts")
}
