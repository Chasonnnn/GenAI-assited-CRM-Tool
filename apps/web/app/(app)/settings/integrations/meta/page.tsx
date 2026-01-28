"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
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
import {
    Loader2Icon,
    PlusIcon,
    RefreshCwIcon,
    TrashIcon,
    FacebookIcon,
    CheckCircleIcon,
    XCircleIcon,
    CalendarIcon,
    PencilIcon,
} from "lucide-react"
import {
    useMetaPages,
    useCreateMetaPage,
    useDeleteMetaPage,
    useAdminMetaAdAccounts,
    useCreateMetaAdAccount,
    useUpdateMetaAdAccount,
    useDeleteMetaAdAccount,
} from "@/lib/hooks/use-admin-meta"
import type { MetaAdAccount, MetaAdAccountCreate, MetaAdAccountUpdate } from "@/lib/api/admin-meta"
import { formatDistanceToNow } from "date-fns"

export default function MetaLeadsAdminPage() {
    const { data: pages = [], isLoading, refetch, isFetching } = useMetaPages()
    const createMutation = useCreateMetaPage()
    const deleteMutation = useDeleteMetaPage()
    const {
        data: adAccounts = [],
        isLoading: adAccountsLoading,
        refetch: refetchAdAccounts,
        isFetching: adAccountsFetching,
    } = useAdminMetaAdAccounts()
    const createAccountMutation = useCreateMetaAdAccount()
    const updateAccountMutation = useUpdateMetaAdAccount()
    const deleteAccountMutation = useDeleteMetaAdAccount()

    const [showAddDialog, setShowAddDialog] = useState(false)
    const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
    const [showAddAccountDialog, setShowAddAccountDialog] = useState(false)
    const [editAccount, setEditAccount] = useState<MetaAdAccount | null>(null)
    const [deleteAccountConfirm, setDeleteAccountConfirm] = useState<string | null>(null)

    // Form state
    const [pageId, setPageId] = useState("")
    const [pageName, setPageName] = useState("")
    const [accessToken, setAccessToken] = useState("")
    const [expiresDays, setExpiresDays] = useState("60")
    const [formError, setFormError] = useState("")

    const [adAccountId, setAdAccountId] = useState("")
    const [adAccountName, setAdAccountName] = useState("")
    const [systemToken, setSystemToken] = useState("")
    const [accountExpiresDays, setAccountExpiresDays] = useState("60")
    const [pixelId, setPixelId] = useState("")
    const [capiEnabled, setCapiEnabled] = useState(false)
    const [useSystemTokenForCapi, setUseSystemTokenForCapi] = useState(true)
    const [capiToken, setCapiToken] = useState("")
    const [accountActive, setAccountActive] = useState(true)
    const [accountFormError, setAccountFormError] = useState("")

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
                access_token: accessToken,
                expires_days: parseInt(expiresDays),
                ...(pageName.trim() ? { page_name: pageName.trim() } : {}),
            })

            // Reset form
            setPageId("")
            setPageName("")
            setAccessToken("")
            setExpiresDays("60")
            setShowAddDialog(false)
        } catch (error: unknown) {
            const message = error instanceof Error ? error.message : "Failed to add page"
            setFormError(message)
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

    const resetAccountForm = () => {
        setAdAccountId("")
        setAdAccountName("")
        setSystemToken("")
        setAccountExpiresDays("60")
        setPixelId("")
        setCapiEnabled(false)
        setUseSystemTokenForCapi(true)
        setCapiToken("")
        setAccountActive(true)
        setAccountFormError("")
    }

    const openEditAccount = (account: MetaAdAccount) => {
        setEditAccount(account)
        setAdAccountId(account.ad_account_external_id)
        setAdAccountName(account.ad_account_name || "")
        setSystemToken("")
        setAccountExpiresDays("")
        setPixelId(account.pixel_id || "")
        setCapiEnabled(account.capi_enabled)
        setUseSystemTokenForCapi(true)
        setCapiToken("")
        setAccountActive(account.is_active)
        setAccountFormError("")
    }

    const handleAddAdAccount = async (e: React.FormEvent) => {
        e.preventDefault()
        setAccountFormError("")

        if (!adAccountId || !systemToken) {
            setAccountFormError("Ad account ID and system token are required")
            return
        }

        if (!/^act_\d+$/.test(adAccountId)) {
            setAccountFormError("Ad account ID must be in the format act_123456789")
            return
        }

        const expiresDaysValue = accountExpiresDays ? parseInt(accountExpiresDays, 10) : undefined
        if (expiresDaysValue !== undefined && Number.isNaN(expiresDaysValue)) {
            setAccountFormError("Token expiry must be a number of days")
            return
        }

        const payload: MetaAdAccountCreate = {
            ad_account_external_id: adAccountId.trim(),
            system_token: systemToken,
            ...(adAccountName.trim() ? { ad_account_name: adAccountName.trim() } : {}),
            ...(expiresDaysValue !== undefined ? { expires_days: expiresDaysValue } : {}),
            ...(pixelId.trim() ? { pixel_id: pixelId.trim() } : {}),
            ...(capiEnabled ? { capi_enabled: true } : {}),
        }

        if (capiEnabled) {
            if (useSystemTokenForCapi) {
                Object.assign(payload, { capi_token: systemToken })
            } else if (capiToken.trim()) {
                Object.assign(payload, { capi_token: capiToken.trim() })
            } else {
                setAccountFormError("Provide a CAPI token or enable Use system token for CAPI")
                return
            }
        }

        try {
            await createAccountMutation.mutateAsync(payload)
            resetAccountForm()
            setShowAddAccountDialog(false)
        } catch (error: unknown) {
            const message = error instanceof Error ? error.message : "Failed to add ad account"
            setAccountFormError(message)
        }
    }

    const handleUpdateAdAccount = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!editAccount) return
        setAccountFormError("")

        const expiresDaysValue = accountExpiresDays ? parseInt(accountExpiresDays, 10) : undefined
        if (accountExpiresDays && Number.isNaN(expiresDaysValue)) {
            setAccountFormError("Token expiry must be a number of days")
            return
        }

        const payload: MetaAdAccountUpdate = {
            capi_enabled: capiEnabled,
            is_active: accountActive,
        }

        if (adAccountName.trim() !== (editAccount.ad_account_name || "")) {
            payload.ad_account_name = adAccountName.trim()
        }
        if (pixelId.trim() !== (editAccount.pixel_id || "")) {
            payload.pixel_id = pixelId.trim()
        }
        if (expiresDaysValue !== undefined) {
            payload.expires_days = expiresDaysValue
        }
        if (systemToken.trim()) {
            payload.system_token = systemToken.trim()
            if (capiEnabled && useSystemTokenForCapi) {
                payload.capi_token = systemToken.trim()
            }
        }
        if (capiEnabled && !useSystemTokenForCapi && capiToken.trim()) {
            payload.capi_token = capiToken.trim()
        }

        try {
            await updateAccountMutation.mutateAsync({
                accountId: editAccount.id,
                data: payload,
            })
            setEditAccount(null)
            resetAccountForm()
        } catch (error: unknown) {
            const message = error instanceof Error ? error.message : "Failed to update ad account"
            setAccountFormError(message)
        }
    }

    const handleDeleteAdAccount = async (accountId: string) => {
        try {
            await deleteAccountMutation.mutateAsync(accountId)
            setDeleteAccountConfirm(null)
        } catch (error) {
            console.error("Failed to delete ad account:", error)
        }
    }

    const closeAddAccountDialog = () => {
        setShowAddAccountDialog(false)
        resetAccountForm()
    }

    const closeEditAccountDialog = () => {
        setEditAccount(null)
        resetAccountForm()
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

    const formatRelative = (value: string | null) => {
        if (!value) return "Never"
        return formatDistanceToNow(new Date(value), { addSuffix: true })
    }

    const isRefreshing = isFetching || adAccountsFetching

    const handleRefresh = () => {
        refetch()
        refetchAdAccounts()
    }

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <div>
                        <h1 className="text-2xl font-semibold">Meta Lead Ads Configuration</h1>
                        <p className="text-sm text-muted-foreground">
                            Manage page tokens and ad accounts for lead capture, spend sync, and CAPI.
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isRefreshing}>
                            <RefreshCwIcon className={`mr-2 size-4 ${isRefreshing ? "animate-spin" : ""}`} />
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
            <div className="flex-1 space-y-6 p-6">
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

                {adAccountsLoading ? (
                    <Card>
                        <CardContent className="flex items-center justify-center py-12">
                            <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                        </CardContent>
                    </Card>
                ) : adAccounts.length === 0 ? (
                    <Card>
                        <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                            <p className="text-lg font-medium">No ad accounts configured yet</p>
                            <p className="text-sm">
                                Add a Meta ad account to sync spend data and enable CAPI status updates.
                            </p>
                            <Button className="mt-4" onClick={() => setShowAddAccountDialog(true)}>
                                <PlusIcon className="mr-2 size-4" />
                                Add Ad Account
                            </Button>
                        </CardContent>
                    </Card>
                ) : (
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0">
                            <div>
                                <CardTitle>Meta Ad Accounts</CardTitle>
                                <CardDescription>Manage ad accounts for spend sync and CAPI</CardDescription>
                            </div>
                            <Button size="sm" onClick={() => setShowAddAccountDialog(true)}>
                                <PlusIcon className="mr-2 size-4" />
                                Add Ad Account
                            </Button>
                        </CardHeader>
                        <CardContent>
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Ad Account</TableHead>
                                        <TableHead>Name</TableHead>
                                        <TableHead>CAPI</TableHead>
                                        <TableHead>Token Expires</TableHead>
                                        <TableHead>Sync</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead className="text-right">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {adAccounts.map((account) => {
                                        const status = getTokenStatus(account.token_expires_at)
                                        return (
                                            <TableRow key={account.id}>
                                                <TableCell className="font-mono">
                                                    {account.ad_account_external_id}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="font-medium">
                                                        {account.ad_account_name || (
                                                            <span className="text-muted-foreground italic">Unnamed</span>
                                                        )}
                                                    </div>
                                                    {account.last_error && (
                                                        <div className="text-xs text-destructive">
                                                            {account.last_error}
                                                        </div>
                                                    )}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant={account.capi_enabled ? "default" : "secondary"}>
                                                        {account.capi_enabled ? "Enabled" : "Disabled"}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    {account.token_expires_at ? (
                                                        <div className="flex items-center gap-2 text-sm">
                                                            <CalendarIcon className="size-4 text-muted-foreground" />
                                                            <span className={status.color}>
                                                                {formatRelative(account.token_expires_at)}
                                                            </span>
                                                        </div>
                                                    ) : (
                                                        <span className="text-muted-foreground">—</span>
                                                    )}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="text-sm text-muted-foreground">
                                                        <div>Hierarchy: {formatRelative(account.hierarchy_synced_at)}</div>
                                                        <div>Spend: {formatRelative(account.spend_synced_at)}</div>
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant={account.is_active ? "default" : "secondary"} className="gap-1">
                                                        {account.is_active ? (
                                                            <CheckCircleIcon className="size-3" />
                                                        ) : (
                                                            <XCircleIcon className="size-3" />
                                                        )}
                                                        {account.is_active ? "Active" : "Inactive"}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => openEditAccount(account)}
                                                    >
                                                        <PencilIcon className="size-4" />
                                                    </Button>
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => setDeleteAccountConfirm(account.id)}
                                                        disabled={deleteAccountMutation.isPending}
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

            {/* Add Ad Account Dialog */}
            <Dialog
                open={showAddAccountDialog}
                onOpenChange={(open) => {
                    if (!open) {
                        closeAddAccountDialog()
                    } else {
                        setShowAddAccountDialog(true)
                    }
                }}
            >
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Add Meta Ad Account</DialogTitle>
                        <DialogDescription>
                            Configure an ad account for spend sync and CAPI. Tokens are encrypted at rest.
                        </DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleAddAdAccount}>
                        <div className="space-y-4 py-4">
                            <div className="space-y-2">
                                <Label htmlFor="adAccountId">Ad Account ID *</Label>
                                <Input
                                    id="adAccountId"
                                    placeholder="act_123456789"
                                    value={adAccountId}
                                    onChange={(e) => setAdAccountId(e.target.value)}
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="adAccountName">Account Name (Optional)</Label>
                                <Input
                                    id="adAccountName"
                                    placeholder="Primary Ads Account"
                                    value={adAccountName}
                                    onChange={(e) => setAdAccountName(e.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="systemToken">System Token *</Label>
                                <Input
                                    id="systemToken"
                                    type="password"
                                    placeholder="EAA..."
                                    value={systemToken}
                                    onChange={(e) => setSystemToken(e.target.value)}
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="accountExpiresDays">Token Expiry (days)</Label>
                                <Input
                                    id="accountExpiresDays"
                                    type="number"
                                    min="1"
                                    max="365"
                                    value={accountExpiresDays}
                                    onChange={(e) => setAccountExpiresDays(e.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="pixelId">Pixel ID (Optional)</Label>
                                <Input
                                    id="pixelId"
                                    placeholder="1234567890"
                                    value={pixelId}
                                    onChange={(e) => setPixelId(e.target.value)}
                                />
                            </div>
                            <div className="flex items-center justify-between rounded-lg border border-border p-3">
                                <div>
                                    <Label className="text-sm font-medium">Enable CAPI</Label>
                                    <p className="text-xs text-muted-foreground">
                                        Send lead status updates back to Meta.
                                    </p>
                                </div>
                                <Switch checked={capiEnabled} onCheckedChange={setCapiEnabled} />
                            </div>
                            {capiEnabled && (
                                <div className="space-y-3 rounded-lg border border-border p-3">
                                    <div className="flex items-center justify-between">
                                        <Label className="text-sm">Use system token for CAPI</Label>
                                        <Switch
                                            checked={useSystemTokenForCapi}
                                            onCheckedChange={setUseSystemTokenForCapi}
                                        />
                                    </div>
                                    {!useSystemTokenForCapi && (
                                        <div className="space-y-2">
                                            <Label htmlFor="capiToken">CAPI Token</Label>
                                            <Input
                                                id="capiToken"
                                                type="password"
                                                placeholder="EAA..."
                                                value={capiToken}
                                                onChange={(e) => setCapiToken(e.target.value)}
                                            />
                                        </div>
                                    )}
                                </div>
                            )}
                            {accountFormError && (
                                <div className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded-lg">
                                    {accountFormError}
                                </div>
                            )}
                            {createAccountMutation.isSuccess && (
                                <div className="text-sm text-green-600 bg-green-500/10 px-3 py-2 rounded-lg">
                                    Ad account added successfully!
                                </div>
                            )}
                        </div>
                        <DialogFooter>
                            <Button type="button" variant="outline" onClick={closeAddAccountDialog}>
                                Cancel
                            </Button>
                            <Button type="submit" disabled={createAccountMutation.isPending}>
                                {createAccountMutation.isPending && (
                                    <Loader2Icon className="mr-2 size-4 animate-spin" />
                                )}
                                Add Ad Account
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* Edit Ad Account Dialog */}
            <Dialog
                open={!!editAccount}
                onOpenChange={(open) => {
                    if (!open) {
                        closeEditAccountDialog()
                    }
                }}
            >
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Edit Meta Ad Account</DialogTitle>
                        <DialogDescription>
                            Update tokens, CAPI configuration, or status for this ad account.
                        </DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleUpdateAdAccount}>
                        <div className="space-y-4 py-4">
                            <div className="space-y-2">
                                <Label htmlFor="editAdAccountId">Ad Account ID</Label>
                                <Input id="editAdAccountId" value={adAccountId} disabled />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="editAdAccountName">Account Name</Label>
                                <Input
                                    id="editAdAccountName"
                                    placeholder="Primary Ads Account"
                                    value={adAccountName}
                                    onChange={(e) => setAdAccountName(e.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="editSystemToken">System Token (optional)</Label>
                                <Input
                                    id="editSystemToken"
                                    type="password"
                                    placeholder="Leave blank to keep current token"
                                    value={systemToken}
                                    onChange={(e) => setSystemToken(e.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="editAccountExpiresDays">Token Expiry (days)</Label>
                                <Input
                                    id="editAccountExpiresDays"
                                    type="number"
                                    min="1"
                                    max="365"
                                    placeholder="Leave blank to keep current expiry"
                                    value={accountExpiresDays}
                                    onChange={(e) => setAccountExpiresDays(e.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="editPixelId">Pixel ID</Label>
                                <Input
                                    id="editPixelId"
                                    placeholder="1234567890"
                                    value={pixelId}
                                    onChange={(e) => setPixelId(e.target.value)}
                                />
                            </div>
                            <div className="flex items-center justify-between rounded-lg border border-border p-3">
                                <div>
                                    <Label className="text-sm font-medium">Active</Label>
                                    <p className="text-xs text-muted-foreground">
                                        Inactive accounts stop syncs and CAPI.
                                    </p>
                                </div>
                                <Switch checked={accountActive} onCheckedChange={setAccountActive} />
                            </div>
                            <div className="flex items-center justify-between rounded-lg border border-border p-3">
                                <div>
                                    <Label className="text-sm font-medium">Enable CAPI</Label>
                                    <p className="text-xs text-muted-foreground">
                                        Send lead status updates back to Meta.
                                    </p>
                                </div>
                                <Switch checked={capiEnabled} onCheckedChange={setCapiEnabled} />
                            </div>
                            {capiEnabled && (
                                <div className="space-y-3 rounded-lg border border-border p-3">
                                    <div className="flex items-center justify-between">
                                        <Label className="text-sm">Use system token for CAPI</Label>
                                        <Switch
                                            checked={useSystemTokenForCapi}
                                            onCheckedChange={setUseSystemTokenForCapi}
                                        />
                                    </div>
                                    {!useSystemTokenForCapi && (
                                        <div className="space-y-2">
                                            <Label htmlFor="editCapiToken">CAPI Token (optional)</Label>
                                            <Input
                                                id="editCapiToken"
                                                type="password"
                                                placeholder="Leave blank to keep current token"
                                                value={capiToken}
                                                onChange={(e) => setCapiToken(e.target.value)}
                                            />
                                        </div>
                                    )}
                                </div>
                            )}
                            {accountFormError && (
                                <div className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded-lg">
                                    {accountFormError}
                                </div>
                            )}
                        </div>
                        <DialogFooter>
                            <Button type="button" variant="outline" onClick={closeEditAccountDialog}>
                                Cancel
                            </Button>
                            <Button type="submit" disabled={updateAccountMutation.isPending}>
                                {updateAccountMutation.isPending && (
                                    <Loader2Icon className="mr-2 size-4 animate-spin" />
                                )}
                                Save Changes
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* Delete Page Dialog */}
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

            {/* Delete Ad Account Dialog */}
            <Dialog open={!!deleteAccountConfirm} onOpenChange={() => setDeleteAccountConfirm(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Deactivate Ad Account?</DialogTitle>
                        <DialogDescription>
                            This will disable syncs and CAPI for this ad account. You can re-enable it later.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDeleteAccountConfirm(null)}>
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={() => deleteAccountConfirm && handleDeleteAdAccount(deleteAccountConfirm)}
                            disabled={deleteAccountMutation.isPending}
                        >
                            {deleteAccountMutation.isPending && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            Deactivate
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
