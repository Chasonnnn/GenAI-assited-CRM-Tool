"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Loader2Icon, PlusIcon, RefreshCwIcon, TrashIcon, FacebookIcon, CheckCircleIcon, XCircleIcon, CalendarIcon } from "lucide-react"
import { useMetaPages, useCreateMetaPage, useDeleteMetaPage } from "@/lib/hooks/use-admin-meta"
import { formatDistanceToNow } from "date-fns"

export default function MetaLeadsAdminPage() {
    const { data: pages = [], isLoading, refetch, isFetching } = useMetaPages()
    const createMutation = useCreateMetaPage()
    const deleteMutation = useDeleteMetaPage()

    const [showAddDialog, setShowAddDialog] = useState(false)
    const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

    // Form state
    const [pageId, setPageId] = useState("")
    const [pageName, setPageName] = useState("")
    const [accessToken, setAccessToken] = useState("")
    const [expiresDays, setExpiresDays] = useState("60")
    const [formError, setFormError] = useState("")

    const handleAddPage = async (e: React.FormEvent) => {
        e.preventDefault()
        setFormError("")

        if (!pageId || !accessToken) {
            setFormError("Page ID and Access Token are required")
            return
        }

        if (!/^\d+$/.test(pageId)) {
            setFormError("Page ID must be numeric")
            return
        }

        try {
            await createMutation.mutateAsync({
                page_id: pageId,
                page_name: pageName || undefined,
                access_token: accessToken,
                expires_days: parseInt(expiresDays),
            })

            // Reset form
            setPageId("")
            setPageName("")
            setAccessToken("")
            setExpiresDays("60")
            setShowAddDialog(false)
        } catch (error: any) {
            setFormError(error.response?.data?.detail || "Failed to add page")
        }
    }

    const handleDelete = async (pageId: string) => {
        try {
            await deleteMutation.mutateAsync(pageId)
            setDeleteConfirm(null)
        } catch (error) {
            console.error("Failed to delete page:", error)
        }
    }

    const getTokenStatus = (expiresAt: string | null) => {
        if (!expiresAt) return { label: "Active", variant: "default" as const, color: "text-green-600" }

        const expiryDate = new Date(expiresAt)
        const now = new Date()
        const daysUntilExpiry = Math.floor((expiryDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))

        if (daysUntilExpiry < 0) {
            return { label: "Expired", variant: "destructive" as const, color: "text-red-600" }
        }
        if (daysUntilExpiry < 7) {
            return { label: "Expires Soon", variant: "secondary" as const, color: "text-amber-600" }
        }
        return { label: "Active", variant: "default" as const, color: "text-green-600" }
    }

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <div>
                        <h1 className="text-2xl font-semibold">Meta Lead Ads Configuration</h1>
                        <p className="text-sm text-muted-foreground">Manage Facebook/Instagram page tokens for lead capture</p>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
                            <RefreshCwIcon className={`mr-2 size-4 ${isFetching ? "animate-spin" : ""}`} />
                            Refresh
                        </Button>
                        <Button onClick={() => setShowAddDialog(true)}>
                            <PlusIcon className="mr-2 size-4" />
                            Add Page
                        </Button>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6">
                {isLoading ? (
                    <Card>
                        <CardContent className="flex items-center justify-center py-12">
                            <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                        </CardContent>
                    </Card>
                ) : pages.length === 0 ? (
                    <Card>
                        <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                            <FacebookIcon className="mb-4 size-12" />
                            <p className="text-lg font-medium">No pages configured yet</p>
                            <p className="text-sm">Add a Meta page to start capturing leads from Facebook/Instagram ads</p>
                            <Button className="mt-4" onClick={() => setShowAddDialog(true)}>
                                <PlusIcon className="mr-2 size-4" />
                                Add Your First Page
                            </Button>
                        </CardContent>
                    </Card>
                ) : (
                    <Card>
                        <CardHeader>
                            <CardTitle>Configured Pages</CardTitle>
                            <CardDescription>Manage Meta page access tokens and monitor sync status</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Page ID</TableHead>
                                        <TableHead>Page Name</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Token Expires</TableHead>
                                        <TableHead>Last Sync</TableHead>
                                        <TableHead className="text-right">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {pages.map((page) => {
                                        const status = getTokenStatus(page.token_expires_at)
                                        return (
                                            <TableRow key={page.id}>
                                                <TableCell className="font-mono">{page.page_id}</TableCell>
                                                <TableCell>{page.page_name || <span className="text-muted-foreground italic">Unnamed</span>}</TableCell>
                                                <TableCell>
                                                    <Badge variant={status.variant} className="gap-1">
                                                        {page.is_active ? (
                                                            <CheckCircleIcon className="size-3" />
                                                        ) : (
                                                            <XCircleIcon className="size-3" />
                                                        )}
                                                        {status.label}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    {page.token_expires_at ? (
                                                        <div className="flex items-center gap-2 text-sm">
                                                            <CalendarIcon className="size-4 text-muted-foreground" />
                                                            <span className={status.color}>
                                                                {formatDistanceToNow(new Date(page.token_expires_at), { addSuffix: true })}
                                                            </span>
                                                        </div>
                                                    ) : (
                                                        <span className="text-muted-foreground">—</span>
                                                    )}
                                                </TableCell>
                                                <TableCell>
                                                    {page.last_success_at ? (
                                                        <span className="text-sm text-muted-foreground">
                                                            {formatDistanceToNow(new Date(page.last_success_at), { addSuffix: true })}
                                                        </span>
                                                    ) : (
                                                        <span className="text-muted-foreground">Never</span>
                                                    )}
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => setDeleteConfirm(page.page_id)}
                                                        disabled={deleteMutation.isPending}
                                                    >
                                                        <TrashIcon className="size-4" />
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                        )
                                    })}
                                </TableBody>
                            </Table>
                        </CardContent>
                    </Card>
                )}
            </div>

            {/* Add Page Dialog */}
            <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Add Meta Page</DialogTitle>
                        <DialogDescription>
                            Add a Facebook/Instagram page for lead ads integration. The access token will be encrypted.
                        </DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleAddPage}>
                        <div className="space-y-4 py-4">
                            <div className="space-y-2">
                                <Label htmlFor="pageId">Page ID *</Label>
                                <Input
                                    id="pageId"
                                    placeholder="123456789"
                                    value={pageId}
                                    onChange={(e) => setPageId(e.target.value)}
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="pageName">Page Name (Optional)</Label>
                                <Input
                                    id="pageName"
                                    placeholder="My Business Page"
                                    value={pageName}
                                    onChange={(e) => setPageName(e.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="accessToken">Page Access Token *</Label>
                                <Input
                                    id="accessToken"
                                    type="password"
                                    placeholder="EAAxx..."
                                    value={accessToken}
                                    onChange={(e) => setAccessToken(e.target.value)}
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="expiresDays">Token Expiry (days)</Label>
                                <Input
                                    id="expiresDays"
                                    type="number"
                                    min="1"
                                    max="365"
                                    value={expiresDays}
                                    onChange={(e) => setExpiresDays(e.target.value)}
                                />
                            </div>
                            {formError && (
                                <div className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded-lg">
                                    {formError}
                                </div>
                            )}
                            {createMutation.isSuccess && (
                                <div className="text-sm text-green-600 bg-green-500/10 px-3 py-2 rounded-lg">
                                    Page added successfully!
                                </div>
                            )}
                        </div>
                        <DialogFooter>
                            <Button type="button" variant="outline" onClick={() => setShowAddDialog(false)}>
                                Cancel
                            </Button>
                            <Button type="submit" disabled={createMutation.isPending}>
                                {createMutation.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                                Add Page
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* Delete Confirmation Dialog */}
            <Dialog open={!!deleteConfirm} onOpenChange={() => setDeleteConfirm(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Delete Page Mapping?</DialogTitle>
                        <DialogDescription>
                            Are you sure you want to remove this page? Lead capture webhooks will stop working for this page.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDeleteConfirm(null)}>
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={() => deleteConfirm && handleDelete(deleteConfirm)}
                            disabled={deleteMutation.isPending}
                        >
                            {deleteMutation.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                            Delete
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
