"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Separator } from "@/components/ui/separator"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
    ArrowLeftIcon,
    LoaderIcon,
    MoreVerticalIcon,
    MailIcon,
    PhoneIcon,
    MapPinIcon,
    DollarSignIcon,
    ClockIcon,
    UserIcon,
    ArchiveIcon,
    ArchiveRestoreIcon,
    Trash2Icon,
} from "lucide-react"
import {
    useIntendedParent,
    useIntendedParentHistory,
    useIntendedParentNotes,
    useUpdateIntendedParent,
    useUpdateIntendedParentStatus,
    useArchiveIntendedParent,
    useRestoreIntendedParent,
    useDeleteIntendedParent,
    useCreateIntendedParentNote,
    useDeleteIntendedParentNote,
} from "@/lib/hooks/use-intended-parents"
import type { IntendedParentStatus } from "@/lib/types/intended-parent"

const STATUS_LABELS: Record<IntendedParentStatus, string> = {
    new: "New",
    in_review: "In Review",
    matched: "Matched",
    inactive: "Inactive",
}

const STATUS_COLORS: Record<IntendedParentStatus, string> = {
    new: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    in_review: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
    matched: "bg-green-500/10 text-green-500 border-green-500/20",
    inactive: "bg-gray-500/10 text-gray-500 border-gray-500/20",
}

export default function IntendedParentDetailPage() {
    const params = useParams()
    const router = useRouter()
    const id = params.id as string

    const [isEditOpen, setIsEditOpen] = useState(false)
    const [newNote, setNewNote] = useState("")
    const [formData, setFormData] = useState({
        full_name: "",
        email: "",
        phone: "",
        state: "",
        budget: "",
        notes_internal: "",
    })

    // Queries
    const { data: ip, isLoading } = useIntendedParent(id)
    const { data: history } = useIntendedParentHistory(id)
    const { data: notes } = useIntendedParentNotes(id)

    // Mutations
    const updateMutation = useUpdateIntendedParent()
    const statusMutation = useUpdateIntendedParentStatus()
    const archiveMutation = useArchiveIntendedParent()
    const restoreMutation = useRestoreIntendedParent()
    const deleteMutation = useDeleteIntendedParent()
    const createNoteMutation = useCreateIntendedParentNote()
    const deleteNoteMutation = useDeleteIntendedParentNote()

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "numeric",
            minute: "2-digit",
        })
    }

    const formatBudget = (budget: number | null) => {
        if (!budget) return "Not specified"
        return new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: "USD",
            maximumFractionDigits: 0,
        }).format(budget)
    }

    const handleEdit = () => {
        if (!ip) return
        setFormData({
            full_name: ip.full_name,
            email: ip.email,
            phone: ip.phone || "",
            state: ip.state || "",
            budget: ip.budget?.toString() || "",
            notes_internal: ip.notes_internal || "",
        })
        setIsEditOpen(true)
    }

    const handleSave = async () => {
        await updateMutation.mutateAsync({
            id,
            data: {
                full_name: formData.full_name,
                email: formData.email,
                phone: formData.phone || undefined,
                state: formData.state || undefined,
                budget: formData.budget ? parseFloat(formData.budget) : undefined,
                notes_internal: formData.notes_internal || undefined,
            },
        })
        setIsEditOpen(false)
    }

    const handleStatusChange = async (newStatus: string | null) => {
        if (newStatus) {
            await statusMutation.mutateAsync({ id, data: { status: newStatus as IntendedParentStatus } })
        }
    }

    const handleArchive = async () => {
        if (confirm("Are you sure you want to archive this intended parent?")) {
            await archiveMutation.mutateAsync(id)
        }
    }

    const handleRestore = async () => {
        await restoreMutation.mutateAsync(id)
    }

    const handleDelete = async () => {
        if (confirm("This will permanently delete this intended parent. Are you sure?")) {
            await deleteMutation.mutateAsync(id)
            router.push("/intended-parents")
        }
    }

    const handleAddNote = async () => {
        if (!newNote.trim()) return
        await createNoteMutation.mutateAsync({ id, data: { content: newNote } })
        setNewNote("")
    }

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <LoaderIcon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (!ip) {
        return (
            <div className="flex min-h-screen flex-col items-center justify-center">
                <h1 className="text-2xl font-semibold">Not Found</h1>
                <p className="text-muted-foreground">This intended parent doesn&apos;t exist.</p>
                <Link href="/intended-parents" className="mt-4 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90">
                    Back to List
                </Link>
            </div>
        )
    }

    return (
        <div className="flex min-h-screen flex-col">
            {/* Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur">
                <div className="flex h-16 items-center justify-between px-6">
                    <div className="flex items-center gap-4">
                        <Link href="/intended-parents" className="inline-flex items-center justify-center rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground size-9">
                            <ArrowLeftIcon className="size-5" />
                        </Link>
                        <div>
                            <h1 className="text-xl font-semibold">{ip.full_name}</h1>
                            <p className="text-sm text-muted-foreground">{ip.email}</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <Badge className={STATUS_COLORS[ip.status as IntendedParentStatus]}>
                            {STATUS_LABELS[ip.status as IntendedParentStatus]}
                        </Badge>
                        <DropdownMenu>
                            <DropdownMenuTrigger className="inline-flex items-center justify-center size-10 rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground">
                                <MoreVerticalIcon className="size-4" />
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={handleEdit}>Edit</DropdownMenuItem>
                                <DropdownMenuSeparator />
                                {!ip.is_archived ? (
                                    <DropdownMenuItem onClick={handleArchive}>
                                        <ArchiveIcon className="mr-2 size-4" /> Archive
                                    </DropdownMenuItem>
                                ) : (
                                    <>
                                        <DropdownMenuItem onClick={handleRestore}>
                                            <ArchiveRestoreIcon className="mr-2 size-4" /> Restore
                                        </DropdownMenuItem>
                                        <DropdownMenuItem onClick={handleDelete} className="text-destructive">
                                            <Trash2Icon className="mr-2 size-4" /> Delete Permanently
                                        </DropdownMenuItem>
                                    </>
                                )}
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6">
                <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-3">
                    {/* Left Column - Details */}
                    <div className="space-y-6 lg:col-span-2">
                        {/* Contact Info */}
                        <Card>
                            <CardHeader>
                                <CardTitle>Contact Information</CardTitle>
                            </CardHeader>
                            <CardContent className="grid gap-4 sm:grid-cols-2">
                                <div className="flex items-center gap-3">
                                    <MailIcon className="size-5 text-muted-foreground" />
                                    <div>
                                        <p className="text-sm text-muted-foreground">Email</p>
                                        <p className="font-medium">{ip.email}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <PhoneIcon className="size-5 text-muted-foreground" />
                                    <div>
                                        <p className="text-sm text-muted-foreground">Phone</p>
                                        <p className="font-medium">{ip.phone || "Not provided"}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <MapPinIcon className="size-5 text-muted-foreground" />
                                    <div>
                                        <p className="text-sm text-muted-foreground">State</p>
                                        <p className="font-medium">{ip.state || "Not provided"}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <DollarSignIcon className="size-5 text-muted-foreground" />
                                    <div>
                                        <p className="text-sm text-muted-foreground">Budget</p>
                                        <p className="font-medium">{formatBudget(ip.budget)}</p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Status Change */}
                        <Card>
                            <CardHeader>
                                <CardTitle>Status</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <Select
                                    value={ip.status}
                                    onValueChange={handleStatusChange}
                                    disabled={statusMutation.isPending}
                                >
                                    <SelectTrigger className="w-[200px]">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="new">New</SelectItem>
                                        <SelectItem value="in_review">In Review</SelectItem>
                                        <SelectItem value="matched">Matched</SelectItem>
                                        <SelectItem value="inactive">Inactive</SelectItem>
                                    </SelectContent>
                                </Select>
                            </CardContent>
                        </Card>

                        {/* Notes */}
                        <Card>
                            <CardHeader>
                                <CardTitle>Notes</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="flex gap-2">
                                    <Textarea
                                        placeholder="Add a note..."
                                        value={newNote}
                                        onChange={(e) => setNewNote(e.target.value)}
                                        rows={2}
                                    />
                                    <Button
                                        onClick={handleAddNote}
                                        disabled={!newNote.trim() || createNoteMutation.isPending}
                                        className="bg-teal-600 hover:bg-teal-700"
                                    >
                                        Add
                                    </Button>
                                </div>
                                <Separator />
                                {notes?.length ? (
                                    <div className="space-y-3">
                                        {notes.map((note) => (
                                            <div key={note.id} className="rounded-lg border p-3">
                                                <p className="text-sm">{note.content}</p>
                                                <p className="mt-2 text-xs text-muted-foreground">
                                                    {formatDate(note.created_at)}
                                                </p>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-muted-foreground">No notes yet.</p>
                                )}
                            </CardContent>
                        </Card>
                    </div>

                    {/* Right Column - History */}
                    <div className="space-y-6">
                        <Card>
                            <CardHeader>
                                <CardTitle>Status History</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {history?.length ? (
                                    <div className="space-y-4">
                                        {history.map((item, idx) => (
                                            <div key={item.id} className="flex gap-3">
                                                <div className="flex flex-col items-center">
                                                    <div className="size-2 rounded-full bg-teal-500" />
                                                    {idx < history.length - 1 && (
                                                        <div className="mt-1 h-full w-px bg-border" />
                                                    )}
                                                </div>
                                                <div className="flex-1 pb-4">
                                                    <p className="text-sm font-medium">
                                                        {item.old_status ? (
                                                            <>
                                                                <span className="text-muted-foreground">
                                                                    {STATUS_LABELS[item.old_status as IntendedParentStatus] || item.old_status}
                                                                </span>
                                                                {" → "}
                                                            </>
                                                        ) : null}
                                                        {STATUS_LABELS[item.new_status as IntendedParentStatus] || item.new_status}
                                                    </p>
                                                    {item.reason && (
                                                        <p className="text-xs text-muted-foreground">{item.reason}</p>
                                                    )}
                                                    <p className="text-xs text-muted-foreground mt-1">
                                                        {formatDate(item.changed_at)}
                                                    </p>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-muted-foreground">No history yet.</p>
                                )}
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader>
                                <CardTitle>Activity</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3 text-sm">
                                <div className="flex items-center gap-2">
                                    <ClockIcon className="size-4 text-muted-foreground" />
                                    <span className="text-muted-foreground">Created:</span>
                                    <span>{formatDate(ip.created_at)}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <ClockIcon className="size-4 text-muted-foreground" />
                                    <span className="text-muted-foreground">Last Activity:</span>
                                    <span>{formatDate(ip.last_activity)}</span>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </div>

            {/* Edit Modal */}
            <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Edit Intended Parent</DialogTitle>
                        <DialogDescription>Update the intended parent details</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="edit_name">Full Name</Label>
                            <Input
                                id="edit_name"
                                value={formData.full_name}
                                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="edit_email">Email</Label>
                            <Input
                                id="edit_email"
                                type="email"
                                value={formData.email}
                                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                            />
                        </div>
                        <div className="grid gap-4 md:grid-cols-2">
                            <div className="space-y-2">
                                <Label htmlFor="edit_phone">Phone</Label>
                                <Input
                                    id="edit_phone"
                                    value={formData.phone}
                                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="edit_state">State</Label>
                                <Input
                                    id="edit_state"
                                    value={formData.state}
                                    onChange={(e) => setFormData({ ...formData, state: e.target.value })}
                                />
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="edit_budget">Budget</Label>
                            <Input
                                id="edit_budget"
                                type="number"
                                value={formData.budget}
                                onChange={(e) => setFormData({ ...formData, budget: e.target.value })}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="edit_notes">Internal Notes</Label>
                            <Textarea
                                id="edit_notes"
                                value={formData.notes_internal}
                                onChange={(e) => setFormData({ ...formData, notes_internal: e.target.value })}
                                rows={3}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsEditOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            className="bg-teal-600 hover:bg-teal-700"
                            onClick={handleSave}
                            disabled={updateMutation.isPending}
                        >
                            {updateMutation.isPending && <LoaderIcon className="mr-2 size-4 animate-spin" />}
                            Save Changes
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
