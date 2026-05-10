"use client"

import { SafeHtmlContent } from "@/components/safe-html-content"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    CheckSquareIcon,
    DownloadIcon,
    FolderIcon,
    HistoryIcon,
    StickyNoteIcon,
    TrashIcon,
    UploadIcon,
} from "lucide-react"
import {
    type CombinedActivity,
    type CombinedFile,
    type CombinedNote,
    type CombinedTask,
    isDeletableSource,
} from "../hooks/useMatchDetailTabData"
import {
    isSourceFilter,
    SOURCE_OPTIONS,
    sourceLabel,
    type SourceFilter,
    type TabType,
} from "../hooks/useMatchDetailTabState"

type MatchDetailOverviewTabsProps = {
    activeTab: TabType
    sourceFilter: SourceFilter
    filteredNotes: CombinedNote[]
    filteredFiles: CombinedFile[]
    filteredTasks: CombinedTask[]
    filteredActivity: CombinedActivity[]
    onTabChange: (tab: TabType) => void
    onSourceFilterChange: (source: SourceFilter) => void
    onAddTask: () => void
    onAddNote: () => void
    onUploadFile: () => void
    onDownloadFile: (attachmentId: string) => void
    onDeleteFile: (attachmentId: string, source: "surrogate" | "ip") => void
    isDownloadPending: boolean
    isDeletePending: boolean
    formatDate: (dateStr: string | null | undefined) => string
    formatDateTime: (dateStr: string | null | undefined) => string
}

type SourceKind = "surrogate" | "ip" | "match"

function sourceBadgeClassName(source: SourceKind) {
    if (source === "surrogate") {
        return "border-green-500/50 text-green-600 bg-green-500/5"
    }
    if (source === "ip") {
        return "border-blue-500/50 text-blue-600 bg-blue-500/5"
    }
    return "border-purple-500/50 text-purple-600 bg-purple-500/5"
}

function sourceDotClassName(source: SourceKind) {
    if (source === "surrogate") return "bg-green-500"
    if (source === "ip") return "bg-blue-500"
    return "bg-purple-500"
}

function compactSourceLabel(source: SourceKind) {
    if (source === "surrogate") return "Surrogate"
    if (source === "ip") return "IP"
    return "Match"
}

function SourceBadge({ source, className = "" }: { source: SourceKind; className?: string }) {
    return (
        <Badge
            variant="outline"
            className={`text-[10px] px-1 py-0 ${sourceBadgeClassName(source)} ${className}`}
        >
            {compactSourceLabel(source)}
        </Badge>
    )
}

function SourceFilterBar({
    sourceFilter,
    onSourceFilterChange,
}: Pick<MatchDetailOverviewTabsProps, "sourceFilter" | "onSourceFilterChange">) {
    return (
        <div className="flex items-center gap-2 px-3 py-2 border-b bg-muted/30">
            <Select
                value={sourceFilter}
                onValueChange={(value) => {
                    if (isSourceFilter(value)) {
                        onSourceFilterChange(value)
                    }
                }}
            >
                <SelectTrigger className="w-[160px] h-9 text-sm">
                    <SelectValue placeholder="All Source">
                        {(value: string | null) => sourceLabel(isSourceFilter(value) ? value : null)}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    {SOURCE_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                            {option.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    )
}

function OverviewTabButtons({
    activeTab,
    onTabChange,
}: Pick<MatchDetailOverviewTabsProps, "activeTab" | "onTabChange">) {
    const tabs: Array<{ value: TabType; label: string; icon: typeof StickyNoteIcon }> = [
        { value: "notes", label: "Notes", icon: StickyNoteIcon },
        { value: "files", label: "Files", icon: FolderIcon },
        { value: "tasks", label: "Tasks", icon: CheckSquareIcon },
        { value: "activity", label: "Activity", icon: HistoryIcon },
    ]

    return (
        <div className="flex border-b p-1.5 gap-0.5 flex-shrink-0">
            {tabs.map(({ value, label, icon: Icon }) => (
                <Button
                    key={value}
                    variant={activeTab === value ? "secondary" : "ghost"}
                    size="sm"
                    className="h-7 text-sm px-2"
                    onClick={() => onTabChange(value)}
                >
                    <Icon className="size-3.5 mr-1" />
                    {label}
                </Button>
            ))}
        </div>
    )
}

function EmptyTabState({ icon: Icon, label }: { icon: typeof FolderIcon; label: string }) {
    return (
        <div className="text-center py-4">
            <Icon className="mx-auto size-6 text-muted-foreground mb-1" />
            <p className="text-sm text-muted-foreground">{label}</p>
        </div>
    )
}

function NotesTab({
    filteredNotes,
    onAddNote,
    formatDateTime,
}: Pick<MatchDetailOverviewTabsProps, "filteredNotes" | "onAddNote" | "formatDateTime">) {
    return (
        <div className="space-y-2">
            <Button
                variant="outline"
                size="sm"
                className="w-full h-8 text-xs mb-3"
                onClick={onAddNote}
            >
                <StickyNoteIcon className="size-3.5 mr-1.5" />
                Add Note
            </Button>
            {filteredNotes.length > 0 ? (
                <div className="space-y-2">
                    {filteredNotes.map((note) => (
                        <div
                            key={note.id}
                            className="p-3 rounded-lg border border-border bg-card hover:bg-accent/30 transition-colors"
                        >
                            <div className="flex items-center gap-1.5 mb-2">
                                <SourceBadge source={note.source} className="px-1.5" />
                                {note.author_name && (
                                    <span className="text-xs text-muted-foreground">
                                        by {note.author_name}
                                    </span>
                                )}
                            </div>
                            <SafeHtmlContent
                                html={note.content}
                                className="text-sm prose prose-sm max-w-none dark:prose-invert whitespace-pre-wrap leading-relaxed"
                            />
                            <p className="text-xs text-muted-foreground mt-2">
                                {formatDateTime(note.created_at)}
                            </p>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                    <StickyNoteIcon className="size-8 text-muted-foreground/40 mb-2" />
                    <p className="text-sm text-muted-foreground">No notes yet</p>
                </div>
            )}
        </div>
    )
}

function FilesTab({
    filteredFiles,
    onUploadFile,
    onDownloadFile,
    onDeleteFile,
    isDownloadPending,
    isDeletePending,
    formatDateTime,
}: Pick<
    MatchDetailOverviewTabsProps,
    | "filteredFiles"
    | "onUploadFile"
    | "onDownloadFile"
    | "onDeleteFile"
    | "isDownloadPending"
    | "isDeletePending"
    | "formatDateTime"
>) {
    return (
        <div className="space-y-2">
            <Button
                variant="outline"
                size="sm"
                className="w-full h-8 text-xs mb-3"
                onClick={onUploadFile}
            >
                <UploadIcon className="size-3.5 mr-1.5" />
                Upload File
            </Button>
            {filteredFiles.length > 0 ? (
                filteredFiles.map((file) => {
                    const deletableSource = isDeletableSource(file.source) ? file.source : null
                    return (
                        <div key={file.id} className="p-2 rounded bg-muted/30 flex items-center gap-2">
                            <FolderIcon className="size-4 text-muted-foreground flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-1 mb-0.5">
                                    <SourceBadge source={file.source} />
                                </div>
                                <p className="text-sm font-medium truncate">{file.filename}</p>
                                <p className="text-xs text-muted-foreground">
                                    {(file.file_size / 1024).toFixed(1)} KB • {formatDateTime(file.created_at)}
                                </p>
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="size-7 p-0 text-muted-foreground hover:text-primary"
                                onClick={() => onDownloadFile(file.id)}
                                disabled={isDownloadPending}
                                title={`Download ${file.filename}`}
                                aria-label={`Download ${file.filename}`}
                            >
                                <DownloadIcon className="size-4" aria-hidden="true" />
                            </Button>
                            {deletableSource && (
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="size-7 p-0 text-muted-foreground hover:text-destructive"
                                    onClick={() => onDeleteFile(file.id, deletableSource)}
                                    disabled={isDeletePending}
                                    title={`Delete ${file.filename}`}
                                    aria-label={`Delete ${file.filename}`}
                                >
                                    <TrashIcon className="size-4" aria-hidden="true" />
                                </Button>
                            )}
                        </div>
                    )
                })
            ) : (
                <EmptyTabState icon={FolderIcon} label="No files yet" />
            )}
        </div>
    )
}

function TasksTab({
    filteredTasks,
    onAddTask,
    formatDate,
}: Pick<MatchDetailOverviewTabsProps, "filteredTasks" | "onAddTask" | "formatDate">) {
    return (
        <div className="space-y-2">
            <Button
                variant="outline"
                size="sm"
                className="w-full h-8 text-xs mb-3"
                onClick={onAddTask}
            >
                <CheckSquareIcon className="size-3.5 mr-1.5" />
                Add Task
            </Button>
            {filteredTasks.length > 0 ? (
                filteredTasks.map((task) => (
                    <div key={task.id} className="p-2 rounded bg-muted/30 flex items-center gap-2">
                        <CheckSquareIcon
                            className={`size-4 flex-shrink-0 ${task.is_completed ? "text-green-500" : "text-muted-foreground"}`}
                        />
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1 mb-0.5">
                                <SourceBadge source={task.source} />
                                {task.is_completed && (
                                    <Badge variant="secondary" className="text-[10px] px-1 py-0">Done</Badge>
                                )}
                            </div>
                            <p className={`text-sm font-medium truncate ${task.is_completed ? "line-through text-muted-foreground" : ""}`}>
                                {task.title}
                            </p>
                            {task.due_date && (
                                <p className="text-xs text-muted-foreground">
                                    Due: {formatDate(task.due_date)}
                                </p>
                            )}
                        </div>
                    </div>
                ))
            ) : (
                <EmptyTabState icon={CheckSquareIcon} label="No tasks yet" />
            )}
        </div>
    )
}

function ActivityTab({
    filteredActivity,
    formatDateTime,
}: Pick<MatchDetailOverviewTabsProps, "filteredActivity" | "formatDateTime">) {
    return (
        <div className="space-y-2">
            {filteredActivity.length > 0 ? (
                filteredActivity.map((activity) => (
                    <div key={activity.id} className="flex gap-2">
                        <div className={`size-2 rounded-full mt-1.5 flex-shrink-0 ${sourceDotClassName(activity.source)}`} />
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1 mb-0.5">
                                <SourceBadge source={activity.source} />
                            </div>
                            <p className="text-sm font-medium">{activity.event_type}</p>
                            <p className="text-xs text-muted-foreground">{activity.description}</p>
                            <p className="text-xs text-muted-foreground">
                                {formatDateTime(activity.created_at)}
                                {activity.actor_name && <span className="ml-1">by {activity.actor_name}</span>}
                            </p>
                        </div>
                    </div>
                ))
            ) : (
                <EmptyTabState icon={HistoryIcon} label="No activity yet" />
            )}
        </div>
    )
}

function ActiveTabContent(props: MatchDetailOverviewTabsProps) {
    if (props.activeTab === "notes") {
        return (
            <NotesTab
                filteredNotes={props.filteredNotes}
                onAddNote={props.onAddNote}
                formatDateTime={props.formatDateTime}
            />
        )
    }
    if (props.activeTab === "files") {
        return (
            <FilesTab
                filteredFiles={props.filteredFiles}
                onUploadFile={props.onUploadFile}
                onDownloadFile={props.onDownloadFile}
                onDeleteFile={props.onDeleteFile}
                isDownloadPending={props.isDownloadPending}
                isDeletePending={props.isDeletePending}
                formatDateTime={props.formatDateTime}
            />
        )
    }
    if (props.activeTab === "tasks") {
        return (
            <TasksTab
                filteredTasks={props.filteredTasks}
                onAddTask={props.onAddTask}
                formatDate={props.formatDate}
            />
        )
    }
    return (
        <ActivityTab
            filteredActivity={props.filteredActivity}
            formatDateTime={props.formatDateTime}
        />
    )
}

export function MatchDetailOverviewTabs(props: MatchDetailOverviewTabsProps) {
    return (
        <div className="min-w-0 border rounded-lg flex flex-col overflow-hidden">
            <SourceFilterBar
                sourceFilter={props.sourceFilter}
                onSourceFilterChange={props.onSourceFilterChange}
            />
            <OverviewTabButtons activeTab={props.activeTab} onTabChange={props.onTabChange} />
            <div className="flex-1 p-3 overflow-y-auto">
                <ActiveTabContent {...props} />
            </div>
        </div>
    )
}
