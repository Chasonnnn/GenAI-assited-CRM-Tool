export const REPORT_SERIES_COLORS = [
    "var(--chart-1)",
    "var(--chart-2)",
    "var(--chart-3)",
    "var(--chart-4)",
    "var(--chart-5)",
] as const

export const REPORT_THEME = {
    primary: "var(--chart-1)",
    secondary: "var(--chart-2)",
    tertiary: "var(--chart-3)",
    quaternary: "var(--chart-4)",
    quinary: "var(--chart-5)",
    success: "var(--status-success)",
    warning: "var(--status-warning)",
    danger: "var(--status-danger)",
    muted: "var(--status-muted)",
} as const

export function getReportSeriesColor(index: number): string {
    return REPORT_SERIES_COLORS[index % REPORT_SERIES_COLORS.length] ?? REPORT_THEME.primary
}

export function getReportPerformanceColor(rate: number): string {
    if (rate >= 30) return REPORT_THEME.success
    if (rate >= 20) return REPORT_THEME.primary
    if (rate >= 10) return REPORT_THEME.warning
    return REPORT_THEME.muted
}

export function getEfficiencyColor(
    value: number | null | undefined,
    {
        lowThreshold = 50,
        highThreshold = 100,
    }: {
        lowThreshold?: number
        highThreshold?: number
    } = {}
): string | undefined {
    if (value === null || value === undefined) return undefined
    if (value < lowThreshold) return REPORT_THEME.success
    if (value > highThreshold) return REPORT_THEME.warning
    return undefined
}

export function getDirectionalColor(value: number | null | undefined): string | undefined {
    if (value === null || value === undefined) return undefined
    return value >= 0 ? REPORT_THEME.success : REPORT_THEME.danger
}
