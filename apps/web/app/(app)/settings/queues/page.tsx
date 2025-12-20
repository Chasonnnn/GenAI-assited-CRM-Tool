"use client"

import * as React from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { PlusIcon, MoreVerticalIcon, LoaderIcon, UsersIcon } from "lucide-react"
import { useQueues, useCreateQueue, useUpdateQueue, useDeleteQueue, type Queue, type QueueCreatePayload } from "@/lib/hooks/use-queues"
import { useAuth } from "@/lib/auth-context"
import { useRouter } from "next/navigation"

export default function QueuesSettingsPage() {
    const router = useRouter()
    const { user } = useAuth()
    const { data: queues, isLoading, error } = useQueues(true) // Include inactive
    const createQueueMutation = useCreateQueue()
    const updateQueueMutation = useUpdateQueue()
    const deleteQueueMutation = useDeleteQueue()

    const [createDialogOpen, setCreateDialogOpen] = React.useState(false)
    const [editDialogOpen, setEditDialogOpen] = React.useState(false)
    const [editingQueue, setEditingQueue] = React.useState<Queue | null>(null)
    const [formData, setFormData] = React.useState<QueueCreatePayload>({ name: "", description: "" })

    // Check if user is a manager
    const isManager = user?.role && ['admin', 'developer'].includes(user.role)

    // Redirect if not manager
    React.useEffect(() => {
        if (user && !isManager) {
            router.push('/settings')
        }
    }, [user, isManager, router])

    const handleCreateQueue = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!formData.name.trim()) return

        await createQueueMutation.mutateAsync(formData)
        setFormData({ name: "", description: "" })
        setCreateDialogOpen(false)
    }

    const handleUpdateQueue = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!editingQueue || !formData.name.trim()) return

        await updateQueueMutation.mutateAsync({
            queueId: editingQueue.id,
            data: { name: formData.name, description: formData.description }
        })
        setEditDialogOpen(false)
        setEditingQueue(null)
        setFormData({ name: "", description: "" })
    }

    const handleToggleActive = async (queue: Queue) => {
        await updateQueueMutation.mutateAsync({
            queueId: queue.id,
            data: { is_active: !queue.is_active }
        })
    }

    const handleDeleteQueue = async (queueId: string) => {
        if (!confirm("Are you sure you want to deactivate this queue?")) return
        await deleteQueueMutation.mutateAsync(queueId)
    }

    const openEditDialog = (queue: Queue) => {
        setEditingQueue(queue)
        setFormData({ name: queue.name, description: queue.description || "" })
        setEditDialogOpen(true)
    }

    if (!isManager) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
            </div>
        )
    }

    return (
        <div className="p-6 max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <UsersIcon className="h-6 w-6" />
                        Queue Management
                    </h1>
                    <p className="text-muted-foreground">
                        Manage case queues for your organization
                    </p>
                </div>
                <Button onClick={() => setCreateDialogOpen(true)}>
                    <PlusIcon className="h-4 w-4 mr-2" />
                    Create Queue
                </Button>
            </div>

            {/* Error State */}
            {error && (
                <Card className="p-6 text-center text-destructive mb-6">
                    Error loading queues: {error.message}
                </Card>
            )}

            {/* Loading State */}
            {isLoading && (
                <Card className="p-12 flex items-center justify-center">
                    <LoaderIcon className="size-8 animate-spin text-muted-foreground" />
                </Card>
            )}

            {/* Empty State */}
            {!isLoading && !error && queues?.length === 0 && (
                <Card className="p-12 text-center">
                    <UsersIcon className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                    <h3 className="text-lg font-medium mb-2">No queues yet</h3>
                    <p className="text-muted-foreground mb-4">
                        Create your first queue to organize cases
                    </p>
                    <Button onClick={() => setCreateDialogOpen(true)}>
                        <PlusIcon className="h-4 w-4 mr-2" />
                        Create Queue
                    </Button>
                </Card>
            )}

            {/* Queues Table */}
            {!isLoading && !error && queues && queues.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Queues</CardTitle>
                        <CardDescription>
                            {queues.filter(q => q.is_active).length} active, {queues.filter(q => !q.is_active).length} inactive
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="p-0">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Description</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead className="w-[50px]"></TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {queues.map((queue) => (
                                    <TableRow key={queue.id} className={!queue.is_active ? "opacity-50" : ""}>
                                        <TableCell className="font-medium">{queue.name}</TableCell>
                                        <TableCell className="text-muted-foreground max-w-[300px] truncate">
                                            {queue.description || "—"}
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant={queue.is_active ? "default" : "secondary"}>
                                                {queue.is_active ? "Active" : "Inactive"}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <DropdownMenu>
                                                <DropdownMenuTrigger className="inline-flex items-center justify-center size-8 p-0 rounded-md hover:bg-accent">
                                                    <MoreVerticalIcon className="size-4" />
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end">
                                                    <DropdownMenuItem onClick={() => openEditDialog(queue)}>
                                                        Edit
                                                    </DropdownMenuItem>
                                                    <DropdownMenuItem onClick={() => handleToggleActive(queue)}>
                                                        {queue.is_active ? "Deactivate" : "Activate"}
                                                    </DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>
            )}

            {/* Create Queue Dialog */}
            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Create Queue</DialogTitle>
                    </DialogHeader>
                    <form onSubmit={handleCreateQueue}>
                        <div className="space-y-4 py-4">
                            <div>
                                <Label htmlFor="queue-name">Name</Label>
                                <Input
                                    id="queue-name"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    placeholder="e.g., New Leads Queue"
                                    className="mt-2"
                                />
                            </div>
                            <div>
                                <Label htmlFor="queue-description">Description (optional)</Label>
                                <Textarea
                                    id="queue-description"
                                    value={formData.description || ""}
                                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                    placeholder="Brief description of the queue purpose"
                                    className="mt-2"
                                    rows={3}
                                />
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" type="button" onClick={() => setCreateDialogOpen(false)}>
                                Cancel
                            </Button>
                            <Button type="submit" disabled={createQueueMutation.isPending || !formData.name.trim()}>
                                {createQueueMutation.isPending ? "Creating..." : "Create Queue"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* Edit Queue Dialog */}
            <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Edit Queue</DialogTitle>
                    </DialogHeader>
                    <form onSubmit={handleUpdateQueue}>
                        <div className="space-y-4 py-4">
                            <div>
                                <Label htmlFor="edit-queue-name">Name</Label>
                                <Input
                                    id="edit-queue-name"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    className="mt-2"
                                />
                            </div>
                            <div>
                                <Label htmlFor="edit-queue-description">Description (optional)</Label>
                                <Textarea
                                    id="edit-queue-description"
                                    value={formData.description || ""}
                                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                    className="mt-2"
                                    rows={3}
                                />
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" type="button" onClick={() => setEditDialogOpen(false)}>
                                Cancel
                            </Button>
                            <Button type="submit" disabled={updateQueueMutation.isPending || !formData.name.trim()}>
                                {updateQueueMutation.isPending ? "Saving..." : "Save Changes"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>
        </div>
    )
}
