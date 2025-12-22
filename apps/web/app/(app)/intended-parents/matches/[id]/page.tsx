"use client"

import { useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import {
    MailIcon,
    PhoneIcon,
    MapPinIcon,
    CalendarIcon,
    CakeIcon,
    DollarSignIcon,
    StickyNoteIcon,
    FolderIcon,
    CheckSquareIcon,
    HistoryIcon,
    Loader2Icon,
    ArrowLeftIcon,
    UserIcon,
    UsersIcon,
} from "lucide-react"
import { useMatch } from "@/lib/hooks/use-matches"
import { MatchTasksCalendar } from "@/components/matches/MatchTasksCalendar"
import { useCase } from "@/lib/hooks/use-cases"
import { useIntendedParent } from "@/lib/hooks/use-intended-parents"

const STATUS_LABELS: Record<string, string> = {
    proposed: "Proposed",
    reviewing: "Reviewing",
    accepted: "Accepted",
    rejected: "Rejected",
    cancelled: "Cancelled",
}

const STATUS_COLORS: Record<string, string> = {
    proposed: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
    reviewing: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    accepted: "bg-green-500/10 text-green-500 border-green-500/20",
    rejected: "bg-red-500/10 text-red-500 border-red-500/20",
    cancelled: "bg-gray-500/10 text-gray-500 border-gray-500/20",
}

export default function MatchDetailPage() {
    const params = useParams()
    const matchId = params.id as string
    const [activeTab, setActiveTab] = useState<"notes" | "files" | "tasks" | "activity">("notes")

    const { data: match, isLoading: matchLoading } = useMatch(matchId)

    // Fetch full profile data for both sides
    const { data: caseData, isLoading: caseLoading } = useCase(match?.case_id || "")
    const { data: ipData, isLoading: ipLoading } = useIntendedParent(match?.intended_parent_id || "")

    const formatDate = (dateStr: string | null | undefined) => {
        if (!dateStr) return "—"
        return new Date(dateStr).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        })
    }

    const formatDateTime = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "numeric",
            minute: "2-digit",
        })
    }

    if (matchLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (!match) {
        return (
            <div className="flex min-h-screen flex-col items-center justify-center">
                <h2 className="text-xl font-semibold">Match not found</h2>
                <Link href="/intended-parents/matches">
                    <Button variant="outline" className="mt-4">
                        <ArrowLeftIcon className="mr-2 size-4" />
                        Back to Matches
                    </Button>
                </Link>
            </div>
        )
    }

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-12 items-center gap-4 px-4">
                    <Link href="/intended-parents/matches">
                        <Button variant="ghost" size="sm" className="h-7 text-xs">
                            <ArrowLeftIcon className="mr-1 size-3" />
                            Matches
                        </Button>
                    </Link>
                    <div className="flex-1">
                        <h1 className="text-base font-semibold">
                            {match.case_name || "Surrogate"} ↔ {match.ip_name || "Intended Parents"}
                        </h1>
                    </div>
                    <Badge className={STATUS_COLORS[match.status]}>
                        {STATUS_LABELS[match.status]}
                    </Badge>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-4">
                <Tabs defaultValue="overview" className="w-full">
                    <TabsList className="mb-3">
                        <TabsTrigger value="overview">Overview</TabsTrigger>
                        <TabsTrigger value="calendar">Calendar</TabsTrigger>
                    </TabsList>

                    <TabsContent value="overview" className="h-[calc(100vh-145px)]">
                        {/* 3-Column Horizontal Layout: 35% | 35% | 30% */}
                        <div className="grid gap-4 h-full" style={{ gridTemplateColumns: '35% 35% 30%' }}>
                            {/* Surrogate Column - 35% */}
                            <div className="border rounded-lg p-4 overflow-y-auto">
                                <div className="flex items-center gap-2 mb-3">
                                    <UserIcon className="size-4 text-purple-500" />
                                    <h2 className="text-sm font-semibold text-purple-500">Surrogate</h2>
                                </div>

                                {caseLoading ? (
                                    <div className="flex items-center justify-center h-32">
                                        <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
                                    </div>
                                ) : caseData ? (
                                    <div className="space-y-3">
                                        {/* Profile Header */}
                                        <div className="flex items-start gap-3">
                                            <Avatar className="h-10 w-10">
                                                <AvatarFallback className="bg-purple-500/10 text-purple-500 text-sm">
                                                    {(caseData.full_name || "S").charAt(0).toUpperCase()}
                                                </AvatarFallback>
                                            </Avatar>
                                            <div className="flex-1 min-w-0">
                                                <h3 className="text-base font-semibold truncate">{caseData.full_name}</h3>
                                                <div className="flex items-center gap-1 mt-0.5">
                                                    <Badge variant="outline" className="text-xs px-1.5 py-0">#{caseData.case_number}</Badge>
                                                    <Badge variant="secondary" className="text-xs px-1.5 py-0">{caseData.status_label}</Badge>
                                                </div>
                                            </div>
                                        </div>

                                        <Separator />

                                        {/* Contact Info - Compact */}
                                        <div className="space-y-2 text-sm">
                                            <div className="flex items-center gap-2">
                                                <MailIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                <span className="truncate">{caseData.email || "—"}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <PhoneIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                <span>{caseData.phone || "—"}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <MapPinIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                <span>{caseData.state || "—"}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <CakeIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                <span>{formatDate(caseData.date_of_birth)}</span>
                                            </div>
                                        </div>

                                        <Separator />

                                        {/* Demographics - Compact */}
                                        <div>
                                            <p className="text-xs text-muted-foreground mb-1">Demographics</p>
                                            <div className="grid grid-cols-3 gap-1 text-xs">
                                                <div><span className="text-muted-foreground">Race:</span> {caseData.race || "—"}</div>
                                                <div><span className="text-muted-foreground">Ht:</span> {caseData.height_ft ? `${caseData.height_ft}ft` : "—"}</div>
                                                <div><span className="text-muted-foreground">Wt:</span> {caseData.weight_lb ? `${caseData.weight_lb}lb` : "—"}</div>
                                            </div>
                                        </div>

                                        <Link href={`/cases/${caseData.id}`}>
                                            <Button variant="outline" size="sm" className="w-full text-xs h-7">View Full Profile</Button>
                                        </Link>
                                    </div>
                                ) : (
                                    <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
                                        No surrogate data
                                    </div>
                                )}
                            </div>

                            {/* Intended Parents Column - 35% */}
                            <div className="border rounded-lg p-4 overflow-y-auto">
                                <div className="flex items-center gap-2 mb-3">
                                    <UsersIcon className="size-4 text-green-500" />
                                    <h2 className="text-sm font-semibold text-green-500">Intended Parents</h2>
                                </div>

                                {ipLoading ? (
                                    <div className="flex items-center justify-center h-32">
                                        <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
                                    </div>
                                ) : ipData ? (
                                    <div className="space-y-3">
                                        {/* Profile Header */}
                                        <div className="flex items-start gap-3">
                                            <Avatar className="h-10 w-10">
                                                <AvatarFallback className="bg-green-500/10 text-green-500 text-sm">
                                                    {(ipData.full_name || "IP").charAt(0).toUpperCase()}
                                                </AvatarFallback>
                                            </Avatar>
                                            <div className="flex-1 min-w-0">
                                                <h3 className="text-base font-semibold truncate">{ipData.full_name}</h3>
                                                <Badge variant="secondary" className="text-xs px-1.5 py-0 mt-0.5">{ipData.status}</Badge>
                                            </div>
                                        </div>

                                        <Separator />

                                        {/* Contact Info - Compact */}
                                        <div className="space-y-2 text-sm">
                                            <div className="flex items-center gap-2">
                                                <MailIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                <span className="truncate">{ipData.email || "—"}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <PhoneIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                <span>{ipData.phone || "—"}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <MapPinIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                <span>{ipData.state || "—"}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <DollarSignIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                <span>
                                                    {ipData.budget
                                                        ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(ipData.budget)
                                                        : "—"}
                                                </span>
                                            </div>
                                        </div>

                                        {ipData.notes_internal && (
                                            <>
                                                <Separator />
                                                <div>
                                                    <p className="text-xs text-muted-foreground mb-1">Notes</p>
                                                    <p className="text-xs line-clamp-2">{ipData.notes_internal}</p>
                                                </div>
                                            </>
                                        )}

                                        <Link href={`/intended-parents/${ipData.id}`}>
                                            <Button variant="outline" size="sm" className="w-full text-xs h-7">View Full Profile</Button>
                                        </Link>
                                    </div>
                                ) : (
                                    <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
                                        No intended parent data
                                    </div>
                                )}
                            </div>

                            {/* Notes/Files/Tasks/Activity Column - 30% */}
                            <div className="border rounded-lg flex flex-col overflow-hidden">
                                {/* Tab Buttons */}
                                <div className="flex border-b p-1.5 gap-0.5 flex-shrink-0">
                                    <Button
                                        variant={activeTab === "notes" ? "secondary" : "ghost"}
                                        size="sm"
                                        className="h-6 text-xs px-2"
                                        onClick={() => setActiveTab("notes")}
                                    >
                                        <StickyNoteIcon className="size-3 mr-1" />
                                        Notes
                                    </Button>
                                    <Button
                                        variant={activeTab === "files" ? "secondary" : "ghost"}
                                        size="sm"
                                        className="h-6 text-xs px-2"
                                        onClick={() => setActiveTab("files")}
                                    >
                                        <FolderIcon className="size-3 mr-1" />
                                        Files
                                    </Button>
                                    <Button
                                        variant={activeTab === "tasks" ? "secondary" : "ghost"}
                                        size="sm"
                                        className="h-6 text-xs px-2"
                                        onClick={() => setActiveTab("tasks")}
                                    >
                                        <CheckSquareIcon className="size-3 mr-1" />
                                        Tasks
                                    </Button>
                                    <Button
                                        variant={activeTab === "activity" ? "secondary" : "ghost"}
                                        size="sm"
                                        className="h-6 text-xs px-2"
                                        onClick={() => setActiveTab("activity")}
                                    >
                                        <HistoryIcon className="size-3 mr-1" />
                                        Activity
                                    </Button>
                                </div>

                                {/* Tab Content */}
                                <div className="flex-1 p-3 overflow-y-auto">
                                    {activeTab === "notes" && (
                                        <div className="space-y-2">
                                            {match.notes ? (
                                                <div className="p-2 rounded bg-muted/30">
                                                    <p className="text-xs whitespace-pre-wrap">{match.notes}</p>
                                                    <p className="text-xs text-muted-foreground mt-1">Match Notes</p>
                                                </div>
                                            ) : (
                                                <p className="text-xs text-muted-foreground italic text-center py-4">
                                                    No notes yet
                                                </p>
                                            )}
                                        </div>
                                    )}

                                    {activeTab === "files" && (
                                        <div className="text-center py-4">
                                            <FolderIcon className="mx-auto h-6 w-6 text-muted-foreground mb-1" />
                                            <p className="text-xs text-muted-foreground">
                                                Files will appear here
                                            </p>
                                        </div>
                                    )}

                                    {activeTab === "tasks" && (
                                        <div className="text-center py-4">
                                            <CheckSquareIcon className="mx-auto h-6 w-6 text-muted-foreground mb-1" />
                                            <p className="text-xs text-muted-foreground">
                                                Tasks will appear here
                                            </p>
                                        </div>
                                    )}

                                    {activeTab === "activity" && (
                                        <div className="space-y-2">
                                            <div className="flex gap-2">
                                                <div className="h-1.5 w-1.5 rounded-full bg-teal-500 mt-1.5 flex-shrink-0"></div>
                                                <div>
                                                    <p className="text-xs font-medium">Match Proposed</p>
                                                    <p className="text-xs text-muted-foreground">{formatDateTime(match.proposed_at)}</p>
                                                </div>
                                            </div>
                                            {match.reviewed_at && (
                                                <div className="flex gap-2">
                                                    <div className="h-1.5 w-1.5 rounded-full bg-teal-500 mt-1.5 flex-shrink-0"></div>
                                                    <div>
                                                        <p className="text-xs font-medium">
                                                            {match.status === "accepted" ? "Accepted" : match.status === "rejected" ? "Rejected" : "Reviewed"}
                                                        </p>
                                                        <p className="text-xs text-muted-foreground">{formatDateTime(match.reviewed_at)}</p>
                                                        {match.rejection_reason && (
                                                            <p className="text-xs text-muted-foreground">Reason: {match.rejection_reason}</p>
                                                        )}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </TabsContent>

                    <TabsContent value="calendar" className="h-[calc(100vh-145px)]">
                        {match && (
                            <MatchTasksCalendar
                                caseId={match.case_id}
                                ipId={match.intended_parent_id}
                            />
                        )}
                    </TabsContent>
                </Tabs>
            </div>
        </div >
    )
}
