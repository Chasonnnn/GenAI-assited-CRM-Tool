"use client"

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
    onAddNote: () => void
    onUploadFile: () => void
    onDownloadFile: (attachmentId: string) => void
    onDeleteFile: (attachmentId: string, source: "surrogate" | "ip") => void
    isDownloadPending: boolean
    isDeletePending: boolean
    formatDate: (dateStr: string | null | undefined) => string
    formatDateTime: (dateStr: string | null | undefined) => string
}

export function MatchDetailOverviewTabs({
    activeTab,
    sourceFilter,
    filteredNotes,
    filteredFiles,
    filteredTasks,
    filteredActivity,
    onTabChange,
    onSourceFilterChange,
    onAddNote,
    onUploadFile,
    onDownloadFile,
    onDeleteFile,
    isDownloadPending,
    isDeletePending,
    formatDate,
    formatDateTime,
}: MatchDetailOverviewTabsProps) {
    return (
        <div className="min-w-0 border rounded-lg flex flex-col overflow-hidden">
            {/* Source Filter - above tabs */}
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
                            {(value: string | null) =>
                                sourceLabel(isSourceFilter(value) ? value : null)
                            }
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

            {/* Tab Buttons */}
            <div className="flex border-b p-1.5 gap-0.5 flex-shrink-0">
                <Button
                    variant={activeTab === "notes" ? "secondary" : "ghost"}
                    size="sm"
                    className="h-7 text-sm px-2"
                    onClick={() => onTabChange("notes")}
                >
                    <StickyNoteIcon className="size-3.5 mr-1" />
                    Notes
                </Button>
                <Button
                    variant={activeTab === "files" ? "secondary" : "ghost"}
                    size="sm"
                    className="h-7 text-sm px-2"
                    onClick={() => onTabChange("files")}
                >
                    <FolderIcon className="size-3.5 mr-1" />
                    Files
                </Button>
                <Button
                    variant={activeTab === "tasks" ? "secondary" : "ghost"}
                    size="sm"
                    className="h-7 text-sm px-2"
                    onClick={() => onTabChange("tasks")}
                >
                    <CheckSquareIcon className="size-3.5 mr-1" />
                    Tasks
                </Button>
                <Button
                    variant={activeTab === "activity" ? "secondary" : "ghost"}
                    size="sm"
                    className="h-7 text-sm px-2"
                    onClick={() => onTabChange("activity")}
                >
                    <HistoryIcon className="size-3.5 mr-1" />
                    Activity
                </Button>
            </div>

            {/* Tab Content */}
            <div className="flex-1 p-3 overflow-y-auto">
                {activeTab === "notes" && (
                    <div className="space-y-2">
                        {/* Add Note Button */}
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
                                            <Badge
                                                variant="outline"
                                                className={`text-[10px] px-1.5 py-0 ${note.source === "surrogate" ? "border-green-500/50 text-green-600 bg-green-500/5" :
                                                    note.source === "ip" ? "border-blue-500/50 text-blue-600 bg-blue-500/5" :
                                                        "border-purple-500/50 text-purple-600 bg-purple-500/5"
                                                    }`}
                                            >
                                                {note.source === "surrogate" ? "Surrogate" :
                                                    note.source === "ip" ? "IP" : "Match"}
                                            </Badge>
                                            {note.author_name && (
                                                <span className="text-xs text-muted-foreground">
                                                    by {note.author_name}
                                                </span>
                                            )}
                                        </div>
                                        <div
                                            className="text-sm prose prose-sm max-w-none dark:prose-invert whitespace-pre-wrap leading-relaxed"
                                            dangerouslySetInnerHTML={{ __html: note.content }}
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
                )}

                {activeTab === "files" && (
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
                                const deletableSource = isDeletableSource(file.source)
                                    ? file.source
                                    : null
                                return (
                                    <div key={file.id} className="p-2 rounded bg-muted/30 flex items-center gap-2">
                                        <FolderIcon className="size-4 text-muted-foreground flex-shrink-0" />
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-1 mb-0.5">
                                                <Badge
                                                    variant="outline"
                                                    className={`text-[10px] px-1 py-0 ${file.source === "surrogate" ? "border-green-500 text-green-600" :
                                                        file.source === "ip" ? "border-blue-500 text-blue-600" :
                                                            "border-purple-500 text-purple-600"
                                                        }`}
                                                >
                                                    {file.source === "surrogate" ? "Surrogate" :
                                                        file.source === "ip" ? "IP" : "Match"}
                                                </Badge>
                                            </div>
                                            <p className="text-sm font-medium truncate">{file.filename}</p>
                                            <p className="text-xs text-muted-foreground">
                                                {(file.file_size / 1024).toFixed(1)} KB • {formatDateTime(file.created_at)}
                                            </p>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="h-7 w-7 p-0 text-muted-foreground hover:text-primary"
                                            onClick={() => onDownloadFile(file.id)}
                                            disabled={isDownloadPending}
                                            title="Download file"
                                        >
                                            <DownloadIcon className="size-4" />
                                        </Button>
                                        {deletableSource && (
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                                                onClick={() => onDeleteFile(file.id, deletableSource)}
                                                disabled={isDeletePending}
                                                title="Delete file"
                                            >
                                                <TrashIcon className="size-4" />
                                            </Button>
                                        )}
                                    </div>
                                )
                            })
                        ) : (
                            <div className="text-center py-4">
                                <FolderIcon className="mx-auto h-6 w-6 text-muted-foreground mb-1" />
                                <p className="text-sm text-muted-foreground">
                                    No files yet
                                </p>
                            </div>
                        )}
                    </div>
                )}

                {activeTab === "tasks" && (
                    <div className="space-y-2">
                        {filteredTasks.length > 0 ? (
                            filteredTasks.map((task) => (
                                <div key={task.id} className="p-2 rounded bg-muted/30 flex items-center gap-2">
                                    <CheckSquareIcon className={`size-4 flex-shrink-0 ${task.is_completed ? "text-green-500" : "text-muted-foreground"}`} />
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-1 mb-0.5">
                                            <Badge
                                                variant="outline"
                                                className={`text-[10px] px-1 py-0 ${task.source === "surrogate" ? "border-green-500 text-green-600" :
                                                    task.source === "ip" ? "border-blue-500 text-blue-600" :
                                                        "border-purple-500 text-purple-600"
                                                    }`}
                                            >
                                                {task.source === "surrogate" ? "Surrogate" :
                                                    task.source === "ip" ? "IP" : "Match"}
                                            </Badge>
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
                            <div className="text-center py-4">
                                <CheckSquareIcon className="mx-auto h-6 w-6 text-muted-foreground mb-1" />
                                <p className="text-sm text-muted-foreground">
                                    No tasks yet
                                </p>
                            </div>
                        )}
                    </div>
                )}

                {activeTab === "activity" && (
                    <div className="space-y-2">
                        {filteredActivity.length > 0 ? (
                            filteredActivity.map((activity) => (
                                <div key={activity.id} className="flex gap-2">
                                    <div className={`h-2 w-2 rounded-full mt-1.5 flex-shrink-0 ${activity.source === "surrogate" ? "bg-green-500" :
                                        activity.source === "ip" ? "bg-blue-500" :
                                            "bg-purple-500"
                                        }`}></div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-1 mb-0.5">
                                            <Badge
                                                variant="outline"
                                                className={`text-[10px] px-1 py-0 ${activity.source === "surrogate" ? "border-green-500 text-green-600" :
                                                    activity.source === "ip" ? "border-blue-500 text-blue-600" :
                                                        "border-purple-500 text-purple-600"
                                                    }`}
                                            >
                                                {activity.source === "surrogate" ? "Surrogate" :
                                                    activity.source === "ip" ? "IP" : "Match"}
                                            </Badge>
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
                            <div className="text-center py-4">
                                <HistoryIcon className="mx-auto h-6 w-6 text-muted-foreground mb-1" />
                                <p className="text-sm text-muted-foreground">
                                    No activity yet
                                </p>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    )
}
