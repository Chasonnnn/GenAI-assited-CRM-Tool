export function readableForeground(background: string): string {
    const hex = background.trim().replace(/^#/, "")
    if (!/^[0-9a-f]{6}$/i.test(hex)) return "#FFFFFF"
    const channels = [0, 2, 4].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16) / 255)
    const luminance = channels
        .map((value) => value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
        .reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index]!, 0)
    return luminance > 0.45 ? "#422006" : "#FFFFFF"
}
