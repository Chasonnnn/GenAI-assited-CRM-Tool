import { redirect } from "next/navigation"

// The Matches list lives under Intended Parents; this keeps old /matches links working.
export default function MatchesRedirectPage() {
    redirect("/intended-parents/matches")
}
