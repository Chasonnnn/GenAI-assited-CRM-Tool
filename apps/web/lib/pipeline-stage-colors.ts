import type { StageType } from "@/lib/api/pipelines"

const DEFAULT_CUSTOM_STAGE_COLOR = "#6b7280"
const FALLBACK_GRAY_STAGE_COLORS = new Set([DEFAULT_CUSTOM_STAGE_COLOR])

export const CUSTOM_STAGE_COLOR_PRESETS: Record<StageType, string[]> = {
    intake: ["#2563eb", "#0ea5e9", "#14b8a6", "#22c55e", "#8b5cf6", "#f59e0b"],
    post_approval: ["#0f766e", "#0891b2", "#4f46e5", "#8b5cf6", "#db2777", "#ea580c"],
    paused: ["#b4536a"],
    terminal: ["#ef4444", "#dc2626"],
}

const KEYWORD_STAGE_COLOR_RULES: Array<{ keywords: string[]; color: string }> = [
    { keywords: ["docusign", "docu", "signature", "consent"], color: "#f59e0b" },
    { keywords: ["insurance"], color: "#0891b2" },
    { keywords: ["medical", "medically", "clinic"], color: "#14b8a6" },
    { keywords: ["legal", "contract"], color: "#6366f1" },
    { keywords: ["transfer", "cycle"], color: "#0d9488" },
    { keywords: ["pbo"], color: "#db2777" },
    { keywords: ["anatomy", "heartbeat", "hcg", "pregnancy", "pregnant", "ob"], color: "#16a34a" },
    { keywords: ["interview", "consult", "screen"], color: "#a855f7" },
    { keywords: ["application", "packet", "submit", "submitted"], color: "#8b5cf6" },
    { keywords: ["review"], color: "#f59e0b" },
    { keywords: ["qualif"], color: "#10b981" },
    { keywords: ["contact", "outreach"], color: "#0ea5e9" },
]

type StageColorInput = {
    color?: string | null
    label?: string | null
    slug?: string | null
    stage_key?: string | null
    stage_type?: StageType | string | null
    order?: number | null
    is_locked?: boolean | null
}

function normalizeHexColor(color: string | null | undefined) {
    const normalized = color?.trim()
    return normalized && /^#[0-9a-fA-F]{6}$/.test(normalized) ? normalized : null
}

function normalizeStageText(...parts: Array<string | null | undefined>) {
    return parts
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, " ")
        .trim()
}

function getFallbackPaletteColor(stageType: StageType | string | null | undefined, stageKey: string | null | undefined, order?: number | null) {
    const palette = CUSTOM_STAGE_COLOR_PRESETS[(stageType as StageType) ?? "intake"] ?? [DEFAULT_CUSTOM_STAGE_COLOR]
    if (order && order > 0) {
        return palette[(order - 1) % palette.length] ?? DEFAULT_CUSTOM_STAGE_COLOR
    }
    const seed = normalizeStageText(stageKey, stageType)
    const hash = Array.from(seed).reduce((total, char, index) => total + (index + 1) * char.charCodeAt(0), 0)
    return palette[hash % palette.length] ?? DEFAULT_CUSTOM_STAGE_COLOR
}

export function suggestStageColor(stage: StageColorInput) {
    const normalizedText = normalizeStageText(stage.label, stage.slug, stage.stage_key)
    for (const rule of KEYWORD_STAGE_COLOR_RULES) {
        if (rule.keywords.some((keyword) => normalizedText.includes(keyword))) {
            return rule.color
        }
    }
    return getFallbackPaletteColor(stage.stage_type, stage.stage_key ?? stage.slug, stage.order)
}

export function resolveStageColor(stage: StageColorInput) {
    const normalizedColor = normalizeHexColor(stage.color)
    if (normalizedColor && !FALLBACK_GRAY_STAGE_COLORS.has(normalizedColor.toLowerCase())) {
        return normalizedColor
    }
    if (stage.is_locked) {
        return normalizedColor ?? DEFAULT_CUSTOM_STAGE_COLOR
    }
    return suggestStageColor(stage)
}

export function shouldAutoRefreshStageColor(stage: StageColorInput) {
    if (stage.is_locked) return false
    const normalizedColor = normalizeHexColor(stage.color)
    const autoKey = (stage.stage_key ?? stage.slug ?? "").toLowerCase()
    return (
        !normalizedColor
        || FALLBACK_GRAY_STAGE_COLORS.has(normalizedColor.toLowerCase())
        || stage.label === "New Stage"
        || autoKey.startsWith("custom_stage")
        || normalizedColor === suggestStageColor(stage)
    )
}
