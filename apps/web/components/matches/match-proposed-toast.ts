import { toast } from "@/components/ui/toast"
import type { MatchRead } from "@/lib/api/matches"

/** Success toast for a new match proposal, with a View action that opens the match. */
export function showMatchProposedToast(
    match: Pick<MatchRead, "id" | "match_number">,
    navigate: (href: string) => void,
) {
    toast.success(match.match_number ? `Match ${match.match_number} proposed` : "Match proposed", {
        action: {
            label: "View",
            onClick: () => navigate(`/intended-parents/matches/${match.id}`),
        },
    })
}
