'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Loader2, LogOut } from 'lucide-react'

import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/components/ui/toast'

type CliSession = {
    id: string
    expires_at: string
    created_at: string
    revoked_at: string | null
}

export default function OpsCliPage() {
    const queryClient = useQueryClient()
    const [code, setCode] = useState('')
    const approve = useMutation({
        mutationFn: () => api.post('/platform/cli/login/approve', { code }),
        onSuccess: () => setCode(''),
    })
    const sessions = useQuery({
        queryKey: ['platform', 'cli-tokens'],
        queryFn: () => api.get<CliSession[]>('/platform/cli/tokens'),
        // Approval precedes the terminal's exchange; refresh while it finishes signing in.
        refetchInterval: approve.isSuccess ? 3000 : false,
    })
    const revoke = useMutation({
        mutationFn: (id: string) => api.delete<void>(`/platform/cli/tokens/${id}`),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['platform', 'cli-tokens'] }),
        onError: () => toast.error('Unable to sign out CLI session'),
    })

    return (
        <div className="mx-auto max-w-4xl space-y-6 p-6">
            <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">CLI login</h1>
            <Card>
                <CardHeader><CardTitle>Connect your terminal</CardTitle></CardHeader>
                <CardContent>
                    {approve.isSuccess ? (
                        <div role="status" className="flex flex-wrap items-center gap-2">
                            <span className="flex items-center gap-2"><Check className="size-5 shrink-0 text-teal-600" /> Approved. Return to your terminal.</span>
                            <Button variant="ghost" onClick={() => approve.reset()}>Connect another terminal</Button>
                        </div>
                    ) : (
                        <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); approve.mutate() }}>
                            <code className="block rounded bg-stone-100 p-3 text-sm dark:bg-stone-900">ops login --env &lt;environment&gt;</code>
                            <div className="space-y-2">
                                <Label htmlFor="cli-code">Code from your terminal</Label>
                                <Input id="cli-code" value={code} onChange={(event) => setCode(event.target.value)}
                                    placeholder="ABCD-EFGH-JKLM" maxLength={32} autoComplete="off" required />
                            </div>
                            <p className="text-sm text-stone-500">Only approve a code from a login you started. This grants template publishing access for eight hours.</p>
                            {approve.isError && <p role="alert" className="text-sm text-red-600">Unable to approve. Check the code and your connection, or run ops login again.</p>}
                            <Button type="submit" disabled={approve.isPending || code.replace(/[- ]/g, '').length !== 12}>
                                {approve.isPending && <Loader2 className="size-4 animate-spin" />} Sign in to CLI
                            </Button>
                        </form>
                    )}
                </CardContent>
            </Card>
            <Card>
                <CardHeader><CardTitle>CLI sessions</CardTitle></CardHeader>
                <CardContent>
                    {sessions.isPending ? (
                        <Loader2 className="size-5 animate-spin" aria-label="Loading sessions" />
                    ) : sessions.isError ? (
                        <div role="alert" className="space-y-2">
                            <p className="text-sm text-red-600">Unable to load CLI sessions.</p>
                            <Button variant="outline" onClick={() => sessions.refetch()}>Retry</Button>
                        </div>
                    ) : sessions.data.length === 0 ? (
                        <p className="text-sm text-stone-500">No CLI sessions.</p>
                    ) : (
                        <div className="divide-y divide-stone-200 dark:divide-stone-800">
                            {sessions.data.map((session) => (
                                <div key={session.id} className="flex flex-col items-start justify-between gap-3 py-3 sm:flex-row sm:items-center">
                                    <div className="min-w-0">
                                        <p className="text-sm">Signed in {new Date(session.created_at).toLocaleString()}</p>
                                        <p className="text-sm text-stone-500">
                                            {session.revoked_at ? 'Signed out' : `${new Date(session.expires_at).getTime() <= sessions.dataUpdatedAt ? 'Expired' : 'Expires'} ${new Date(session.expires_at).toLocaleString()}`}
                                        </p>
                                    </div>
                                    {!session.revoked_at && (
                                        <Button variant="ghost" size="sm" onClick={() => revoke.mutate(session.id)} disabled={revoke.isPending}>
                                            <LogOut className="size-4" /> Sign out
                                        </Button>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}
