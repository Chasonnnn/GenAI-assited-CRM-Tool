"use client"

import { useMemo, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "@/components/app-link"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Checkbox } from "@/components/ui/checkbox"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import {
    AlertTriangleIcon,
    CheckCircleIcon,
    FacebookIcon,
    Loader2Icon,
    PencilIcon,
    SearchIcon,
    TrashIcon,
    UnlinkIcon,
} from "lucide-react"
import {
    useMetaConnections,
    useMetaConnectUrl,
    useDisconnectMetaConnection,
    useMetaAvailableAssetsInfinite,
    useConnectMetaAssets,
    useMetaConnectionsNeedingReauth,
    useMetaConnectionsWithErrors,
} from "@/lib/hooks/use-meta-oauth"
import {
    getConnectionHealthStatus,
    parseMetaError,
    type AdAccountOption,
    type MetaOAuthConnection,
    type PageOption,
} from "@/lib/api/meta-oauth"
import { useAdminMetaAdAccounts, useDeleteMetaAdAccount, useUpdateMetaAdAccount } from "@/lib/hooks/use-admin-meta"
import type { MetaAdAccount, MetaAdAccountUpdate } from "@/lib/api/admin-meta"
import { formatRelativeTime } from "@/lib/formatters"

// Connection health badge component
function ConnectionHealthBadge({ connection }: { connection: MetaOAuthConnection }) {
    const status = getConnectionHealthStatus(connection)

    if (status === "healthy") {
        return (
            <Badge variant="default" className="gap-1 bg-green-500/10 text-green-600 border-green-500/20">
                <CheckCircleIcon className="size-3" />
                Healthy
            </Badge>
        )
    }

    if (status === "needs_reauth") {
        return (
            <Tooltip>
                <TooltipTrigger>
                    <Badge variant="destructive" className="gap-1">
                        <AlertTriangleIcon className="size-3" />
                        Needs Reauth
                    </Badge>
                </TooltipTrigger>
                <TooltipContent>
                    Token expired or revoked. Click Reconnect to fix.
                </TooltipContent>
            </Tooltip>
        )
    }

    if (status === "rate_limited") {
        return (
            <Tooltip>
                <TooltipTrigger>
                    <Badge variant="secondary" className="gap-1 bg-yellow-500/10 text-yellow-600 border-yellow-500/20">
                        <AlertTriangleIcon className="size-3" />
                        Rate Limited
                    </Badge>
                </TooltipTrigger>
                <TooltipContent>
                    Temporarily rate limited. Will retry automatically.
                </TooltipContent>
            </Tooltip>
        )
    }

    if (status === "permission_error") {
        return (
            <Tooltip>
                <TooltipTrigger>
                    <Badge variant="destructive" className="gap-1">
                        <AlertTriangleIcon className="size-3" />
                        Permission Error
                    </Badge>
                </TooltipTrigger>
                <TooltipContent>
                    Check Lead Access Manager in Meta Business Settings.
                </TooltipContent>
            </Tooltip>
        )
    }

    return (
        <Tooltip>
            <TooltipTrigger>
                <Badge variant="secondary" className="gap-1 bg-yellow-500/10 text-yellow-600 border-yellow-500/20">
                    <AlertTriangleIcon className="size-3" />
                    Error
                </Badge>
            </TooltipTrigger>
            <TooltipContent>{parseMetaError(connection.last_error)}</TooltipContent>
        </Tooltip>
    )
}

// Asset selection component for OAuth flow
function MetaAssetSelection({
    connectionId,
    connectionName,
    onClose,
}: {
    connectionId: string
    connectionName: string
    onClose: () => void
}) {
    const router = useRouter()
    const [search, setSearch] = useState("")
    const [selectedAdAccounts, setSelectedAdAccounts] = useState<string[]>([])
    const [selectedPages, setSelectedPages] = useState<string[]>([])
    const [conflicts, setConflicts] = useState<Array<AdAccountOption | PageOption>>([])
    const [showOverwriteDialog, setShowOverwriteDialog] = useState(false)

    const {
        data,
        fetchNextPage,
        hasNextPage,
        isFetchingNextPage,
        isLoading,
    } = useMetaAvailableAssetsInfinite(connectionId, search)

    const connectMutation = useConnectMetaAssets(connectionId)

    const allAssets = useMemo(() => {
        if (!data?.pages) return { ad_accounts: [], pages: [] }
        return {
            ad_accounts: data.pages.flatMap((p) => p.ad_accounts),
            pages: data.pages.flatMap((p) => p.pages),
        }
    }, [data])

    const toggleAdAccount = (id: string, checked: boolean) => {
        if (checked) {
            setSelectedAdAccounts((prev) => [...prev, id])
        } else {
            setSelectedAdAccounts((prev) => prev.filter((a) => a !== id))
        }
    }

    const togglePage = (id: string, checked: boolean) => {
        if (checked) {
            setSelectedPages((prev) => [...prev, id])
        } else {
            setSelectedPages((prev) => prev.filter((p) => p !== id))
        }
    }

    const handleConnect = async (overwrite = false) => {
        if (!overwrite) {
            const conflicting = [
                ...allAssets.ad_accounts.filter(
                    (a) =>
                        selectedAdAccounts.includes(a.id) &&
                        a.connected_by_connection_id &&
                        a.connected_by_connection_id !== connectionId
                ),
                ...allAssets.pages.filter(
                    (p) =>
                        selectedPages.includes(p.id) &&
                        p.connected_by_connection_id &&
                        p.connected_by_connection_id !== connectionId
                ),
            ]

            if (conflicting.length > 0) {
                setConflicts(conflicting)
                setShowOverwriteDialog(true)
                return
            }
        }

        try {
            await connectMutation.mutateAsync({
                ad_account_ids: selectedAdAccounts,
                page_ids: selectedPages,
                overwrite_existing: overwrite,
            })
            onClose()
            router.push("/settings/integrations/meta")
        } catch {
            // Error handled by mutation
        }
    }

    return (
        <>
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Select Assets for {connectionName}</CardTitle>
                    <CardDescription>
                        Choose ad accounts and pages to connect using this Facebook account.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div className="relative">
                        <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                        <Input
                            placeholder="Search ad accounts or pages"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="pl-9"
                        />
                    </div>

                    <div className="space-y-4">
                        <div>
                            <h3 className="font-medium text-sm">Ad Accounts</h3>
                            {isLoading ? (
                                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                    <Loader2Icon className="size-4 animate-spin" />
                                    Loading...
                                </div>
                            ) : allAssets.ad_accounts.length === 0 ? (
                                <p className="text-sm text-muted-foreground">No ad accounts available</p>
                            ) : (
                                <div className="space-y-2">
                                    {allAssets.ad_accounts.map((account) => (
                                        <div key={account.id} className="flex items-center gap-2">
                                            <Checkbox
                                                checked={selectedAdAccounts.includes(account.id)}
                                                onCheckedChange={(checked) =>
                                                    toggleAdAccount(account.id, !!checked)
                                                }
                                            />
                                            <div className="text-sm">
                                                <span className="font-mono">{account.id}</span>
                                                {account.name && (
                                                    <span className="text-muted-foreground">
                                                        {" "}
                                                        — {account.name}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div>
                            <h3 className="font-medium text-sm">Pages</h3>
                            {isLoading ? (
                                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                    <Loader2Icon className="size-4 animate-spin" />
                                    Loading...
                                </div>
                            ) : allAssets.pages.length === 0 ? (
                                <p className="text-sm text-muted-foreground">No pages available</p>
                            ) : (
                                <div className="space-y-2">
                                    {allAssets.pages.map((page) => (
                                        <div key={page.id} className="flex items-center gap-2">
                                            <Checkbox
                                                checked={selectedPages.includes(page.id)}
                                                onCheckedChange={(checked) =>
                                                    togglePage(page.id, !!checked)
                                                }
                                            />
                                            <div className="text-sm">
                                                <span className="font-mono">{page.id}</span>
                                                {page.name && (
                                                    <span className="text-muted-foreground">
                                                        {" "}
                                                        — {page.name}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>

                    {hasNextPage && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => fetchNextPage()}
                            disabled={isFetchingNextPage}
                        >
                            {isFetchingNextPage ? (
                                <>
                                    <Loader2Icon className="mr-2 size-4 animate-spin" />
                                    Loading...
                                </>
                            ) : (
                                "Load more"
                            )}
                        </Button>
                    )}
                </CardContent>
                <CardContent className="flex justify-end gap-2 pt-0">
                    <Button variant="outline" onClick={onClose}>
                        Cancel
                    </Button>
                    <Button onClick={() => handleConnect(false)} disabled={connectMutation.isPending}>
                        {connectMutation.isPending ? (
                            <>
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                                Connecting...
                            </>
                        ) : (
                            "Connect Selected"
                        )}
                    </Button>
                </CardContent>
            </Card>

            <AlertDialog open={showOverwriteDialog} onOpenChange={setShowOverwriteDialog}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Overwrite existing connections?</AlertDialogTitle>
                        <AlertDialogDescription>
                            Some selected assets are already connected by another user. Overwriting will transfer
                            ownership to this connection.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <div className="space-y-2">
                        {conflicts.map((conflict) => (
                            <div key={`${conflict.id}`} className="text-sm text-muted-foreground">
                                {conflict.id} — connected by {conflict.connected_by_meta_user || "Unknown"}
                            </div>
                        ))}
                    </div>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={() => handleConnect(true)}>Overwrite</AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    )
}

export default function MetaIntegrationPage() {
    const searchParams = useSearchParams()
    const router = useRouter()
    const step = searchParams.get("step")
    const activeConnectionId = searchParams.get("connection")

    const { data: connections = [], isLoading: connectionsLoading } = useMetaConnections()
    const connectUrlMutation = useMetaConnectUrl()
    const disconnectMutation = useDisconnectMetaConnection()
    const connectionsNeedingReauth = useMetaConnectionsNeedingReauth()
    const connectionsWithErrors = useMetaConnectionsWithErrors()

    const { data: adAccounts = [], isLoading: adAccountsLoading } = useAdminMetaAdAccounts()
    const updateAccountMutation = useUpdateMetaAdAccount()
    const deleteAccountMutation = useDeleteMetaAdAccount()

    const [editAccount, setEditAccount] = useState<MetaAdAccount | null>(null)
    const [disconnectConnectionId, setDisconnectConnectionId] = useState<string | null>(null)
    const [accountFormError, setAccountFormError] = useState("")
    const [adAccountName, setAdAccountName] = useState("")
    const [pixelId, setPixelId] = useState("")
    const [capiEnabled, setCapiEnabled] = useState(false)
    const [accountActive, setAccountActive] = useState(true)

    const activeConnection = connections.find((c) => c.id === activeConnectionId)

    const handleConnectWithFacebook = async () => {
        try {
            const result = await connectUrlMutation.mutateAsync()
            window.location.href = result.auth_url
        } catch {
            // Error handled by mutation
        }
    }

    const handleDisconnect = async (connectionId: string) => {
        try {
            await disconnectMutation.mutateAsync(connectionId)
            setDisconnectConnectionId(null)
        } catch {
            // Error handled by mutation
        }
    }

    const openEditAccount = (account: MetaAdAccount) => {
        setEditAccount(account)
        setAdAccountName(account.ad_account_name || "")
        setPixelId(account.pixel_id || "")
        setCapiEnabled(account.capi_enabled)
        setAccountActive(account.is_active)
        setAccountFormError("")
    }

    const handleUpdateAdAccount = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!editAccount) return
        setAccountFormError("")

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

        try {
            await updateAccountMutation.mutateAsync({
                accountId: editAccount.id,
                data: payload,
            })
            setEditAccount(null)
        } catch (error: unknown) {
            const message = error instanceof Error ? error.message : "Failed to update ad account"
            setAccountFormError(message)
        }
    }

    const handleDeleteAdAccount = async (accountId: string) => {
        try {
            await deleteAccountMutation.mutateAsync(accountId)
        } catch (error) {
            console.error("Failed to delete ad account:", error)
        }
    }

    return (
        <div className="flex min-h-screen flex-col">
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <div>
                        <h1 className="text-2xl font-semibold">Meta Integration</h1>
                        <p className="text-sm text-muted-foreground">
                            Connect Meta accounts to sync lead forms and conversions.
                        </p>
                    </div>
                    <Button render={<Link href="/settings/integrations/meta/forms" />} variant="outline">
                        Manage lead forms
                    </Button>
                </div>
            </div>

            <div className="flex-1 space-y-6 p-6">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0">
                        <div>
                            <CardTitle>Connections</CardTitle>
                            <CardDescription>
                                Connect Meta accounts and manage assets for lead ads.
                            </CardDescription>
                        </div>
                        <Button onClick={handleConnectWithFacebook} disabled={connectUrlMutation.isPending}>
                            {connectUrlMutation.isPending ? (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            ) : (
                                <FacebookIcon className="mr-2 size-4" />
                            )}
                            Connect with Facebook
                        </Button>
                    </CardHeader>
                    <CardContent>
                        {connectionsLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                            </div>
                        ) : connections.length === 0 ? (
                            <div className="text-sm text-muted-foreground">No connections yet.</div>
                        ) : (
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Account</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Last validated</TableHead>
                                        <TableHead className="text-right">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {connections.map((connection) => (
                                        <TableRow key={connection.id}>
                                            <TableCell>
                                                <div className="font-medium">
                                                    {connection.meta_user_name || "Meta user"}
                                                </div>
                                                <div className="text-xs text-muted-foreground">
                                                    {connection.meta_user_id}
                                                </div>
                                            </TableCell>
                                            <TableCell>
                                                <ConnectionHealthBadge connection={connection} />
                                            </TableCell>
                                            <TableCell className="text-sm text-muted-foreground">
                                                {connection.last_validated_at
                                                    ? formatRelativeTime(connection.last_validated_at, "—")
                                                    : "—"}
                                            </TableCell>
                                            <TableCell className="text-right">
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() =>
                                                        router.push(
                                                            `/settings/integrations/meta?step=select-assets&connection=${connection.id}`
                                                        )
                                                    }
                                                >
                                                    Manage assets
                                                </Button>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => setDisconnectConnectionId(connection.id)}
                                                >
                                                    <UnlinkIcon className="size-4" />
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        )}
                    </CardContent>
                </Card>

                {connectionsNeedingReauth.length > 0 && (
                    <Alert>
                        <AlertTitle>Reconnect required</AlertTitle>
                        <AlertDescription>
                            <div className="space-y-3">
                                <p>
                                    Some connections need reauthorization. Click Connect with Facebook to refresh
                                    tokens.
                                </p>
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={handleConnectWithFacebook}
                                    disabled={connectUrlMutation.isPending}
                                >
                                    {connectUrlMutation.isPending ? (
                                        <Loader2Icon className="mr-2 size-4 animate-spin" />
                                    ) : (
                                        <FacebookIcon className="mr-2 size-4" />
                                    )}
                                    Reconnect
                                </Button>
                            </div>
                        </AlertDescription>
                    </Alert>
                )}

                {connectionsWithErrors.length > 0 && (
                    <Alert variant="destructive">
                        <AlertTitle>Connection errors</AlertTitle>
                        <AlertDescription>
                            Some connections are returning errors. Review their status and reconnect if needed.
                        </AlertDescription>
                    </Alert>
                )}

                {step === "select-assets" && activeConnection && (
                    <MetaAssetSelection
                        connectionId={activeConnection.id}
                        connectionName={activeConnection.meta_user_name || "Meta user"}
                        onClose={() => router.push("/settings/integrations/meta")}
                    />
                )}

                <Card>
                    <CardHeader>
                        <CardTitle>Ad Accounts</CardTitle>
                        <CardDescription>Configure CAPI settings and sync visibility.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {adAccountsLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                            </div>
                        ) : adAccounts.length === 0 ? (
                            <div className="text-sm text-muted-foreground">No ad accounts connected yet.</div>
                        ) : (
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Ad Account</TableHead>
                                        <TableHead>Name</TableHead>
                                        <TableHead>CAPI</TableHead>
                                        <TableHead>Sync</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead className="text-right">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {adAccounts.map((account) => (
                                        <TableRow key={account.id}>
                                            <TableCell className="font-mono">
                                                {account.ad_account_external_id}
                                            </TableCell>
                                            <TableCell>{account.ad_account_name || "—"}</TableCell>
                                            <TableCell>
                                                <Badge variant={account.capi_enabled ? "default" : "secondary"}>
                                                    {account.capi_enabled ? "Enabled" : "Disabled"}
                                                </Badge>
                                            </TableCell>
                                            <TableCell>
                                                <div className="text-sm text-muted-foreground">
                                                    <div>
                                                        Hierarchy:{" "}
                                                        {account.hierarchy_synced_at
                                                            ? formatRelativeTime(account.hierarchy_synced_at, "—")
                                                            : "—"}
                                                    </div>
                                                    <div>
                                                        Spend:{" "}
                                                        {account.spend_synced_at
                                                            ? formatRelativeTime(account.spend_synced_at, "—")
                                                            : "—"}
                                                    </div>
                                                </div>
                                            </TableCell>
                                            <TableCell>
                                                <Badge variant={account.is_active ? "default" : "secondary"} className="gap-1">
                                                    {account.is_active ? (
                                                        <CheckCircleIcon className="size-3" />
                                                    ) : (
                                                        <AlertTriangleIcon className="size-3" />
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
                                                    onClick={() => handleDeleteAdAccount(account.id)}
                                                    disabled={deleteAccountMutation.isPending}
                                                >
                                                    <TrashIcon className="size-4" />
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        )}
                    </CardContent>
                </Card>
            </div>

            <Dialog open={!!editAccount} onOpenChange={(open) => !open && setEditAccount(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Edit Ad Account</DialogTitle>
                        <DialogDescription>Update CAPI and account settings.</DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleUpdateAdAccount}>
                        <div className="space-y-4 py-4">
                            <div className="space-y-2">
                                <Label htmlFor="adAccountName">Ad account name</Label>
                                <Input
                                    id="adAccountName"
                                    value={adAccountName}
                                    onChange={(e) => setAdAccountName(e.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="pixelId">Pixel ID</Label>
                                <Input
                                    id="pixelId"
                                    value={pixelId}
                                    onChange={(e) => setPixelId(e.target.value)}
                                />
                            </div>
                            <div className="flex items-center justify-between">
                                <div>
                                    <Label htmlFor="capiEnabled">Enable CAPI</Label>
                                    <p className="text-xs text-muted-foreground">
                                        Send lead status updates to Meta.
                                    </p>
                                </div>
                                <Checkbox
                                    checked={capiEnabled}
                                    onCheckedChange={(checked) => setCapiEnabled(!!checked)}
                                    id="capiEnabled"
                                />
                            </div>
                            <div className="flex items-center justify-between">
                                <div>
                                    <Label htmlFor="accountActive">Active</Label>
                                    <p className="text-xs text-muted-foreground">
                                        Disable to pause sync and CAPI for this account.
                                    </p>
                                </div>
                                <Checkbox
                                    checked={accountActive}
                                    onCheckedChange={(checked) => setAccountActive(!!checked)}
                                    id="accountActive"
                                />
                            </div>
                            {accountFormError && (
                                <p className="text-sm text-destructive">{accountFormError}</p>
                            )}
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setEditAccount(null)} type="button">
                                Cancel
                            </Button>
                            <Button type="submit" disabled={updateAccountMutation.isPending}>
                                {updateAccountMutation.isPending ? (
                                    <>
                                        <Loader2Icon className="mr-2 size-4 animate-spin" />
                                        Saving...
                                    </>
                                ) : (
                                    "Save changes"
                                )}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            <AlertDialog open={!!disconnectConnectionId} onOpenChange={(open) => !open && setDisconnectConnectionId(null)}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Disconnect Meta account?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will unlink all ad accounts and pages connected through this Facebook account.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={() => disconnectConnectionId && handleDisconnect(disconnectConnectionId)}
                        >
                            Disconnect
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    )
}
