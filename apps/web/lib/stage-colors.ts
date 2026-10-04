const BADGE_FOREGROUND = "#FFFFFF"
// WCAG AA for normal-size text.
const MIN_CONTRAST = 4.5
// Darkened fills keep the original lightness order: OKLCH lightness in
// [SOURCE_MIN_L, SOURCE_MAX_L] (the range of seeded stage colors that fail AA with white,
// #6366F1 to #FDE68A) maps linearly onto [TARGET_MIN_L, TARGET_MAX_L], capped by each
// color's own AA limit. Without this, every darkened color stops at the same lightness
// and neighboring greens and teals become indistinguishable.
const SOURCE_MIN_L = 0.585
const SOURCE_MAX_L = 0.924
const TARGET_MIN_L = 0.42
const TARGET_MAX_L = 0.6

type Rgb = [number, number, number]

function parseHex(color: string): Rgb | null {
    // Stage payloads are typed as strings, but a missing color must render, not throw.
    if (typeof color !== "string") return null
    const hex = color.trim().replace(/^#/, "")
    if (!/^[0-9a-f]{6}$/i.test(hex)) return null
    return [0, 2, 4].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16) / 255) as Rgb
}

function toHex(rgb: Rgb): string {
    return `#${rgb
        .map((value) => Math.round(Math.min(1, Math.max(0, value)) * 255).toString(16).padStart(2, "0"))
        .join("")
        .toUpperCase()}`
}

const toLinear = (value: number) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
const fromLinear = (value: number) => value <= 0.0031308 ? 12.92 * value : 1.055 * value ** (1 / 2.4) - 0.055

function contrastWithWhite(rgb: Rgb): number {
    const [r, g, b] = rgb.map(toLinear) as Rgb
    return 1.05 / (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.05)
}

/** sRGB to OKLCH as [lightness, chroma, hue in radians]. */
function toOklch(rgb: Rgb): Rgb {
    const [r, g, b] = rgb.map(toLinear) as Rgb
    const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    const lightness = 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s
    const a = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s
    const bAxis = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s
    return [lightness, Math.hypot(a, bAxis), Math.atan2(bAxis, a)]
}

function oklabToRgb(lightness: number, a: number, b: number): Rgb {
    const l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    const m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    const s = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3
    return [
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
    ].map(fromLinear) as Rgb
}

const inGamut = (rgb: Rgb) => rgb.every((value) => value >= -0.0005 && value <= 1.0005)

/** OKLCH to sRGB, lowering chroma (hue kept) until the color fits in sRGB. */
function fromOklch(lightness: number, chroma: number, hue: number): Rgb {
    const full = oklabToRgb(lightness, chroma * Math.cos(hue), chroma * Math.sin(hue))
    if (inGamut(full)) return full
    let low = 0
    let high = chroma
    let best = oklabToRgb(lightness, 0, 0)
    for (let step = 0; step < 24; step += 1) {
        const mid = (low + high) / 2
        const candidate = oklabToRgb(lightness, mid * Math.cos(hue), mid * Math.sin(hue))
        if (inGamut(candidate)) {
            best = candidate
            low = mid
        } else {
            high = mid
        }
    }
    return best
}

/** Highest lightness (same hue and chroma) where white text still reaches AA. */
function maxReadableLightness([lightness, chroma, hue]: Rgb): number {
    let low = 0
    let high = lightness
    for (let step = 0; step < 30; step += 1) {
        const mid = (low + high) / 2
        if (contrastWithWhite(fromOklch(mid, chroma, hue)) >= MIN_CONTRAST) low = mid
        else high = mid
    }
    return low
}

const displayColors = new Map<string, string>()

/**
 * The one color shown for a stage everywhere: badges, dots, swatches, charts and the Pipelines
 * color picker. Unchanged when white text already reaches AA, otherwise darkened (hue kept) so
 * white text does, keeping lighter stages lighter than darker ones. Idempotent: a displayed
 * color passes AA, so it maps to itself, which is why Pipelines can store it as-is and stored
 * colors from before this rule need no migration.
 */
export function stageDisplayColor(color: string): string {
    const cached = displayColors.get(color)
    if (cached) return cached
    const rgb = parseHex(color)
    if (!rgb) return color
    let background = toHex(rgb)
    if (contrastWithWhite(rgb) < MIN_CONTRAST) {
        const oklch = toOklch(rgb)
        const [lightness, chroma, hue] = oklch
        const spread = TARGET_MIN_L
            + (lightness - SOURCE_MIN_L) * (TARGET_MAX_L - TARGET_MIN_L) / (SOURCE_MAX_L - SOURCE_MIN_L)
        let target = Math.max(0, Math.min(maxReadableLightness(oklch), spread))
        background = toHex(fromOklch(target, chroma, hue))
        // Rounding to 8-bit channels can land just under AA; step down until it holds.
        while (target > 0 && contrastWithWhite(parseHex(background)!) < MIN_CONTRAST) {
            target = Math.max(0, target - 0.002)
            background = toHex(fromOklch(target, chroma, hue))
        }
    }
    displayColors.set(color, background)
    return background
}

/** Inline style for a stage badge: white text on the stage color, darkened only as needed. */
export function stageBadgeStyle(color: string): { backgroundColor: string; borderColor: string; color: string } {
    return { backgroundColor: stageDisplayColor(color), borderColor: "transparent", color: BADGE_FOREGROUND }
}
