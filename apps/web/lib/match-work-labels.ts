import type { MatchWorkSource } from "@/lib/api/matches"

const sourceLabels: Record<MatchWorkSource, string> = {
    match: "Match", surrogate: "Surrogate", donor: "Donor", ip: "IP",
}

export function getMatchWorkSourceLabel(source: MatchWorkSource, scope: "case" | "record" = "case") {
    return scope === "record" ? `${sourceLabels[source]} record` : sourceLabels[source]
}
