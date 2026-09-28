const BADGE_FOREGROUND = "#FFFFFF"
// WCAG AA for normal-size text.
const MIN_CONTRAST = 4.5
const LIGHTNESS_STEP = 0.005

type Rgb = [number, number, number]
type Hsl = [number, number, number]

function parseHex(color: string): Rgb | null {
    const hex = color.trim().replace(/^#/, "")
    if (!/^[0-9a-f]{6}$/i.test(hex)) return null
    return [0, 2, 4].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16)) as Rgb
}

function toHex(rgb: Rgb): string {
    return `#${rgb.map((value) => Math.round(value).toString(16).padStart(2, "0")).join("").toUpperCase()}`
}

function relativeLuminance(rgb: Rgb): number {
    return rgb
        .map((value) => value / 255)
        .map((value) => value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
        .reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index]!, 0)
}

function contrastWithWhite(rgb: Rgb): number {
    return 1.05 / (relativeLuminance(rgb) + 0.05)
}

function rgbToHsl([red, green, blue]: Rgb): Hsl {
    const [r, g, b] = [red / 255, green / 255, blue / 255]
    const max = Math.max(r, g, b)
    const min = Math.min(r, g, b)
    const lightness = (max + min) / 2
    if (max === min) return [0, 0, lightness]
    const delta = max - min
    const saturation = lightness > 0.5 ? delta / (2 - max - min) : delta / (max + min)
    const hue = max === r
        ? (g - b) / delta + (g < b ? 6 : 0)
        : max === g
            ? (b - r) / delta + 2
            : (r - g) / delta + 4
    return [hue / 6, saturation, lightness]
}

function hslToRgb([hue, saturation, lightness]: Hsl): Rgb {
    if (saturation === 0) return [lightness * 255, lightness * 255, lightness * 255]
    const q = lightness < 0.5 ? lightness * (1 + saturation) : lightness + saturation - lightness * saturation
    const p = 2 * lightness - q
    const channel = (offset: number) => {
        const t = (hue + offset + 1) % 1
        if (t < 1 / 6) return (p + (q - p) * 6 * t) * 255
        if (t < 1 / 2) return q * 255
        if (t < 2 / 3) return (p + (q - p) * (2 / 3 - t) * 6) * 255
        return p * 255
    }
    return [channel(1 / 3), channel(0), channel(-1 / 3)]
}

const badgeBackgrounds = new Map<string, string>()

/** Darkens a stage color (hue and saturation kept) until white text reaches WCAG AA. */
export function stageBadgeBackground(color: string): string {
    const cached = badgeBackgrounds.get(color)
    if (cached) return cached
    const rgb = parseHex(color)
    if (!rgb) return color
    let result = rgb
    const [hue, saturation, initialLightness] = rgbToHsl(rgb)
    let lightness = initialLightness
    while (contrastWithWhite(result) < MIN_CONTRAST && lightness > 0) {
        lightness = Math.max(0, lightness - LIGHTNESS_STEP)
        result = hslToRgb([hue, saturation, lightness])
    }
    const background = result === rgb ? `#${color.trim().replace(/^#/, "").toUpperCase()}` : toHex(result)
    badgeBackgrounds.set(color, background)
    return background
}

/** Inline style for a stage badge: white text on the stage color, darkened only as needed. */
export function stageBadgeStyle(color: string): { backgroundColor: string; color: string } {
    return { backgroundColor: stageBadgeBackground(color), color: BADGE_FOREGROUND }
}
