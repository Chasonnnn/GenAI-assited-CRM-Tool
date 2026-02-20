"use client"

import { Badge } from "@/components/ui/badge"
import { ClockIcon, MessageSquareIcon, PaperclipIcon, PhoneIcon, VideoIcon, UsersIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import type { InterviewListItem, InterviewType } from "@/lib/api/interviews"

const INTERVIEW_TYPE_ICONS: Record<InterviewType, typeof PhoneIcon> = {
    phone: PhoneIcon,
    video: VideoIcon,
    in_person: UsersIcon,
}

const INTERVIEW_TYPE_COLORS: Record<InterviewType, string> = {
    phone: "bg-blue-500/10 text-blue-600 border-blue-500/20",
    video: "bg-purple-500/10 text-purple-600 border-purple-500/20",
    in_person: "bg-green-500/10 text-green-600 border-green-500/20",
}

function formatDate(dateString: string): string {
    const date = new Date(dateString)
    return date.toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
    })
}

function formatInterviewType(type: InterviewType): string {
    const labels: Record<InterviewType, string> = {
        phone: "Phone",
        video: "Video",
        in_person: "In-Person",
    }
    return labels[type]
}

interface ListItemProps {
    interview: InterviewListItem
    isSelected: boolean
    onClick: () => void
}

export function ListItem({ interview, isSelected, onClick }: ListItemProps) {
    const Icon = INTERVIEW_TYPE_ICONS[interview.interview_type as InterviewType]
    const colorClass = INTERVIEW_TYPE_COLORS[interview.interview_type as InterviewType]

    return (
        <button
            type="button"
            className={cn(
                "w-full p-4 border-b text-left cursor-pointer transition-colors",
                isSelected ? "bg-primary/5" : "hover:bg-muted/50"
            )}
            onClick={onClick}
        >
            <div className="flex items-start gap-3">
                <div className={cn("p-2 rounded-lg", colorClass)}>
                    <Icon className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-sm">
                            {formatInterviewType(interview.interview_type as InterviewType)}
                        </span>
                        {interview.status === "draft" && (
                            <Badge variant="secondary" className="text-xs">Draft</Badge>
                        )}
                    </div>
                    <div className="text-xs text-muted-foreground">
                        {formatDate(interview.conducted_at)} with {interview.conducted_by_name}
                    </div>
                    <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                        {interview.duration_minutes && (
                            <span className="flex items-center gap-1">
                                <ClockIcon className="h-3 w-3" />
                                {interview.duration_minutes}m
                            </span>
                        )}
                        <span className="flex items-center gap-1">
                            <MessageSquareIcon className="h-3 w-3" />
                            {interview.notes_count}
                        </span>
                        <span className="flex items-center gap-1">
                            <PaperclipIcon className="h-3 w-3" />
                            {interview.attachments_count}
                        </span>
                    </div>
                </div>
            </div>
        </button>
    )
}
