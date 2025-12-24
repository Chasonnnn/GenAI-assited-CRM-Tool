"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog"
import { CheckIcon, XIcon, ArrowLeftIcon, Loader2Icon, CalendarPlusIcon } from "lucide-react"
import Link from "next/link"
import { useMatch, useAcceptMatch, useRejectMatch } from "@/lib/hooks/use-matches"
import { formatDistanceToNow } from "date-fns"
import { ScheduleParserDialog } from "@/components/ai/ScheduleParserDialog"
import { useAuth } from "@/lib/auth-context"

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
    proposed: { label: "Proposed", color: "bg-blue-100 text-blue-700" },
    reviewing: { label: "Reviewing", color: "bg-amber-100 text-amber-700" },
    accepted: { label: "Accepted", color: "bg-green-100 text-green-700" },
    rejected: { label: "Rejected", color: "bg-red-100 text-red-700" },
    cancelled: { label: "Cancelled", color: "bg-gray-100 text-gray-700" },
}

export default function MatchReviewPage({ params }: { params: { id: string } }) {
    const router = useRouter()
    const { data: match, isLoading, isError } = useMatch(params.id)
    const acceptMatch = useAcceptMatch()
    const rejectMatch = useRejectMatch()

    const [notes, setNotes] = useState("")
    const [rejectReason, setRejectReason] = useState("")
    const [showRejectDialog, setShowRejectDialog] = useState(false)
    const [showScheduleParser, setShowScheduleParser] = useState(false)
    const { user } = useAuth()

    if (isLoading) {
        return (
            <div className="flex flex-1 items-center justify-center p-6">
                <Loader2Icon className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (isError || !match) {
        return (
            <div className="flex flex-1 flex-col items-center justify-center p-6 gap-4">
                <p className="text-muted-foreground">Match not found</p>
                <Button variant="outline" onClick={() => router.push("/matches")}>
                    Back to Matches
                </Button>
            </div>
        )
    }

    const statusConfig = STATUS_CONFIG[match.status] || STATUS_CONFIG.proposed
    const canTakeAction = match.status === "proposed" || match.status === "reviewing"
    const compatibilityScore = match.compatibility_score ?? 0

    const handleAccept = async () => {
        try {
            await acceptMatch.mutateAsync({ matchId: params.id, data: { notes: notes || undefined } })
            router.push("/matches")
        } catch (e) {
            console.error("Failed to accept match", e)
        }
    }

    const handleReject = async () => {
        if (!rejectReason.trim()) return
        try {
            await rejectMatch.mutateAsync({
                matchId: params.id,
                data: { rejection_reason: rejectReason, notes: notes || undefined }
            })
            setShowRejectDialog(false)
            router.push("/matches")
        } catch (e) {
            console.error("Failed to reject match", e)
        }
    }

    return (
        <div className="flex flex-1 flex-col gap-6 p-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Link href="/matches">
                    <Button variant="ghost" size="icon">
                        <ArrowLeftIcon className="h-5 w-5" />
                    </Button>
                </Link>
                <div className="flex-1">
                    <div className="flex items-center gap-3">
                        <h1 className="text-2xl font-bold">Match Review</h1>
                        <Badge variant="outline" className={statusConfig.color}>
                            {statusConfig.label}
                        </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">
                        Proposed {formatDistanceToNow(new Date(match.proposed_at), { addSuffix: true })}
                    </p>
                </div>
                {user?.ai_enabled && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowScheduleParser(true)}
                        className="gap-1"
                    >
                        <CalendarPlusIcon className="h-4 w-4" />
                        Parse Schedule
                    </Button>
                )}
            </div>

            {/* Profile Cards */}
            <div className="grid gap-6 md:grid-cols-2">
                {/* Surrogate Profile */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg">Surrogate</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex items-start gap-4">
                            <Avatar className="h-12 w-12">
                                <AvatarFallback className="text-lg">
                                    {(match.case_name || "?")[0].toUpperCase()}
                                </AvatarFallback>
                            </Avatar>
                            <div className="flex-1 space-y-1">
                                <h3 className="text-xl font-semibold">{match.case_name || "Unknown"}</h3>
                                {match.case_number && (
                                    <Badge variant="outline">{match.case_number}</Badge>
                                )}
                            </div>
                        </div>
                        <div className="pt-2">
                            <Link href={`/cases/${match.case_id}`}>
                                <Button variant="outline" size="sm" className="w-full bg-transparent">
                                    View Full Profile
                                </Button>
                            </Link>
                        </div>
                    </CardContent>
                </Card>

                {/* Intended Parent Profile */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg">Intended Parents</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex items-start gap-4">
                            <Avatar className="h-12 w-12">
                                <AvatarFallback className="text-lg">
                                    {(match.ip_name || "?")[0].toUpperCase()}
                                </AvatarFallback>
                            </Avatar>
                            <div className="flex-1 space-y-1">
                                <h3 className="text-xl font-semibold">{match.ip_name || "Unknown"}</h3>
                            </div>
                        </div>
                        <div className="pt-2">
                            <Link href={`/intended-parents/${match.intended_parent_id}`}>
                                <Button variant="outline" size="sm" className="w-full bg-transparent">
                                    View Full Profile
                                </Button>
                            </Link>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Compatibility Section */}
            {compatibilityScore > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Compatibility Score</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex flex-col items-center justify-center py-6">
                            <div className="relative flex h-32 w-32 items-center justify-center">
                                <svg className="h-32 w-32 -rotate-90 transform">
                                    <circle
                                        cx="64"
                                        cy="64"
                                        r="56"
                                        stroke="currentColor"
                                        strokeWidth="8"
                                        fill="none"
                                        className="text-muted"
                                    />
                                    <circle
                                        cx="64"
                                        cy="64"
                                        r="56"
                                        stroke="currentColor"
                                        strokeWidth="8"
                                        fill="none"
                                        strokeDasharray={`${2 * Math.PI * 56}`}
                                        strokeDashoffset={`${2 * Math.PI * 56 * (1 - compatibilityScore / 100)}`}
                                        className="text-teal-500 transition-all duration-1000"
                                        strokeLinecap="round"
                                    />
                                </svg>
                                <div className="absolute inset-0 flex flex-col items-center justify-center">
                                    <span className="text-3xl font-bold">{compatibilityScore.toFixed(0)}%</span>
                                    <span className="text-xs text-muted-foreground">Match Score</span>
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Notes Section */}
            <Card>
                <CardHeader>
                    <CardTitle>Coordinator Notes</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    {match.notes && (
                        <div className="rounded-lg bg-muted/50 p-4">
                            <p className="text-sm whitespace-pre-wrap">{match.notes}</p>
                        </div>
                    )}
                    {canTakeAction && (
                        <Textarea
                            placeholder="Add notes about this match..."
                            className="min-h-24"
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                        />
                    )}
                    {match.rejection_reason && (
                        <div className="rounded-lg bg-red-50 dark:bg-red-950 p-4 border border-red-200 dark:border-red-800">
                            <p className="text-sm font-medium text-red-700 dark:text-red-300 mb-1">Rejection Reason</p>
                            <p className="text-sm text-red-600 dark:text-red-400">{match.rejection_reason}</p>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Action Buttons */}
            {canTakeAction && (
                <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                    <Button
                        variant="outline"
                        className="bg-transparent"
                        onClick={() => setShowRejectDialog(true)}
                        disabled={rejectMatch.isPending}
                    >
                        <XIcon className="mr-2 h-4 w-4" />
                        Reject Match
                    </Button>
                    <Button
                        className="bg-teal-500 hover:bg-teal-600"
                        onClick={handleAccept}
                        disabled={acceptMatch.isPending}
                    >
                        {acceptMatch.isPending ? (
                            <Loader2Icon className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                            <CheckIcon className="mr-2 h-4 w-4" />
                        )}
                        Accept Match
                    </Button>
                </div>
            )}

            {/* Reject Dialog */}
            <Dialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Reject Match</DialogTitle>
                        <DialogDescription>
                            Please provide a reason for rejecting this match.
                        </DialogDescription>
                    </DialogHeader>
                    <Textarea
                        placeholder="Reason for rejection..."
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        className="min-h-24"
                    />
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShowRejectDialog(false)}>
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={handleReject}
                            disabled={!rejectReason.trim() || rejectMatch.isPending}
                        >
                            {rejectMatch.isPending && <Loader2Icon className="mr-2 h-4 w-4 animate-spin" />}
                            Reject Match
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Schedule Parser Dialog (mount only when open to avoid unnecessary hooks) */}
            {showScheduleParser && (
                <ScheduleParserDialog
                    open={showScheduleParser}
                    onOpenChange={setShowScheduleParser}
                    entityType="match"
                    entityId={params.id}
                    entityName={`${match.case_name} & ${match.ip_name}`}
                />
            )}
        </div>
    )
}
