const LIGHT_FOREGROUND = "#FFFFFF"
const DARK_FOREGROUND = "#422006"

function relativeLuminance(hex: string): number {
    const channels = [0, 2, 4].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16) / 255)
    return channels
        .map((value) => value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
        .reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index]!, 0)
}

function contrastRatio(first: number, second: number): number {
    return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05)
}

const LIGHT_LUMINANCE = relativeLuminance(LIGHT_FOREGROUND.slice(1))
const DARK_LUMINANCE = relativeLuminance(DARK_FOREGROUND.slice(1))

/** Returns the text color (white or dark amber) with the higher WCAG contrast ratio on `background`. */
export function readableForeground(background: string): string {
    const hex = background.trim().replace(/^#/, "")
    if (!/^[0-9a-f]{6}$/i.test(hex)) return LIGHT_FOREGROUND
    const luminance = relativeLuminance(hex)
    return contrastRatio(luminance, DARK_LUMINANCE) > contrastRatio(luminance, LIGHT_LUMINANCE)
        ? DARK_FOREGROUND
        : LIGHT_FOREGROUND
}
