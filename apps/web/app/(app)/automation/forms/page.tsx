"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
    PlusIcon,
    MoreVerticalIcon,
    FileTextIcon,
    EditIcon,
    LoaderIcon,
    ArrowLeftIcon,
} from "lucide-react"
import { useForms, useCreateForm } from "@/lib/hooks/use-forms"
import { parseDateInput } from "@/lib/utils/date"

function formatRelativeTime(dateString: string): string {
    const date = parseDateInput(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays === 1) return "Yesterday"
    return `${diffDays}d ago`
}

export default function FormsListPage() {
    const router = useRouter()
    const { data: forms, isLoading } = useForms()
    const createFormMutation = useCreateForm()

    const [showCreateModal, setShowCreateModal] = useState(false)
    const [formName, setFormName] = useState("")
    const [formDescription, setFormDescription] = useState("")

    const handleCreate = async () => {
        if (!formName.trim()) return
        try {
            const newForm = await createFormMutation.mutateAsync({
                name: formName.trim(),
                description: formDescription.trim() || undefined,
            })
            setShowCreateModal(false)
            setFormName("")
            setFormDescription("")
            router.push(`/automation/forms/${newForm.id}`)
        } catch {
            // Error handling is done by React Query
        }
    }

    const statusVariant = (status: string) => {
        switch (status) {
            case "published":
                return "default"
            case "draft":
                return "secondary"
            case "archived":
                return "outline"
            default:
                return "secondary"
        }
    }

    const statusLabel = (status: string) => {
        switch (status) {
            case "published":
                return "Published"
            case "draft":
                return "Draft"
            case "archived":
                return "Archived"
            default:
                return status
        }
    }

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <div className="flex items-center gap-4">
                        <Button variant="ghost" size="icon" onClick={() => router.push("/automation")}>
                            <ArrowLeftIcon className="size-4" />
                        </Button>
                        <h1 className="text-2xl font-semibold">Form Builder</h1>
                    </div>
                    <Button onClick={() => setShowCreateModal(true)}>
                        <PlusIcon className="mr-2 size-4" />
                        Create Form
                    </Button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6">
                <div className="space-y-6">
                    {/* Description */}
                    <p className="text-sm text-muted-foreground max-w-2xl">
                        Create dynamic application forms to collect information from candidates.
                        Forms can be sent via secure links and submissions can be reviewed and approved.
                    </p>

                    {/* Form List */}
                    {isLoading ? (
                        <div className="flex items-center justify-center py-12">
                            <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
                        </div>
                    ) : !forms?.length ? (
                        <Card>
                            <CardContent className="flex flex-col items-center justify-center py-12">
                                <FileTextIcon className="size-12 text-muted-foreground/50" />
                                <h3 className="mt-4 text-lg font-medium">No forms yet</h3>
                                <p className="mt-1 text-sm text-muted-foreground">
                                    Create your first form to start collecting applications
                                </p>
                                <Button className="mt-4" onClick={() => setShowCreateModal(true)}>
                                    <PlusIcon className="mr-2 size-4" />
                                    Create Form
                                </Button>
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                            {[...forms]
                                .sort((a, b) => {
                                    // Published first, then draft, then archived
                                    const order = { published: 0, draft: 1, archived: 2 }
                                    const aOrder = order[a.status as keyof typeof order] ?? 3
                                    const bOrder = order[b.status as keyof typeof order] ?? 3
                                    if (aOrder !== bOrder) return aOrder - bOrder
                                    // Then by updated_at descending
                                    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
                                })
                                .map((form) => (
                                    <Card
                                        key={form.id}
                                        className="cursor-pointer hover:bg-accent/50 transition-colors"
                                        onClick={() => router.push(`/automation/forms/${form.id}`)}
                                    >
                                        <CardHeader className="pb-3">
                                            <div className="flex items-start justify-between">
                                                <div className="flex items-center gap-3">
                                                    <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-teal-500/10 text-teal-500">
                                                        <FileTextIcon className="size-5" />
                                                    </div>
                                                    <div>
                                                        <CardTitle className="text-base">{form.name}</CardTitle>
                                                        <Badge
                                                            variant={statusVariant(form.status)}
                                                            className={`mt-1 text-xs ${form.status === "published" ? "bg-green-500 hover:bg-green-500/80" : ""}`}
                                                        >
                                                            {statusLabel(form.status)}
                                                        </Badge>
                                                    </div>
                                                </div>
                                                <DropdownMenu>
                                                    <DropdownMenuTrigger
                                                        render={
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="h-8 w-8"
                                                                onClick={(e) => e.stopPropagation()}
                                                            >
                                                                <MoreVerticalIcon className="size-4" />
                                                            </Button>
                                                        }
                                                    />
                                                    <DropdownMenuContent align="end">
                                                        <DropdownMenuItem
                                                            onClick={(e) => {
                                                                e.stopPropagation()
                                                                router.push(`/automation/forms/${form.id}`)
                                                            }}
                                                        >
                                                            <EditIcon className="mr-2 size-4" />
                                                            Edit
                                                        </DropdownMenuItem>
                                                    </DropdownMenuContent>
                                                </DropdownMenu>
                                            </div>
                                        </CardHeader>
                                        <CardContent className="pt-0">
                                            <p className="text-xs text-muted-foreground">
                                                Updated {formatRelativeTime(form.updated_at)}
                                            </p>
                                        </CardContent>
                                    </Card>
                                ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Create Form Modal */}
            <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Create New Form</DialogTitle>
                        <DialogDescription>
                            Give your form a name and optional description.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="form-name">Form Name *</Label>
                            <Input
                                id="form-name"
                                placeholder="e.g., Surrogate Application"
                                value={formName}
                                onChange={(e) => setFormName(e.target.value)}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="form-description">Description (optional)</Label>
                            <Input
                                id="form-description"
                                placeholder="Brief description of the form"
                                value={formDescription}
                                onChange={(e) => setFormDescription(e.target.value)}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShowCreateModal(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleCreate}
                            disabled={!formName.trim() || createFormMutation.isPending}
                        >
                            {createFormMutation.isPending && (
                                <LoaderIcon className="mr-2 size-4 animate-spin" />
                            )}
                            Create Form
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
