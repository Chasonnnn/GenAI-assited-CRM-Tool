'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ShieldCheck, AlertCircle } from 'lucide-react';
import { getAuthApiBase } from '@/lib/auth-utils';

const ERROR_MESSAGES: Record<string, string> = {
    auth_failed: 'Authentication failed. Please try again.',
    domain_not_allowed: 'Your email domain is not authorized.',
    no_invite: 'No active invitation found for your email.',
    state_expired: 'Session expired. Please try again.',
    state_mismatch: 'Security verification failed. Please try again.',
};

export default function OpsLoginPage() {
    const [isLoading, setIsLoading] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    const apiBase = getAuthApiBase();

    useEffect(() => {
        if (typeof window === 'undefined') return;
        const errorCode = new URLSearchParams(window.location.search).get('error');
        setErrorMessage(errorCode ? ERROR_MESSAGES[errorCode] || 'An error occurred.' : null);
    }, []);

    const handleGoogleLogin = () => {
        setIsLoading(true);
        try {
            sessionStorage.setItem('auth_return_to', 'ops');
            // Pass return_to=ops to redirect back to ops console after auth
            window.location.assign(`${apiBase}/auth/google/login?return_to=ops`);
        } catch {
            // Ignore navigation errors in non-browser runtimes
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-stone-100 dark:bg-stone-950 p-4">
            <Card className="w-full max-w-md border-stone-200 dark:border-stone-800 shadow-lg">
                <CardHeader className="text-center space-y-4 pb-4">
                    <Badge className="mx-auto bg-teal-600 text-white px-3 py-1 text-xs tracking-widest font-semibold">
                        OPS CONSOLE
                    </Badge>
                    <div className="w-14 h-14 mx-auto rounded-xl bg-stone-100 dark:bg-stone-800 border border-stone-200 dark:border-stone-700 flex items-center justify-center">
                        <ShieldCheck className="w-8 h-8 text-teal-600" strokeWidth={1.5} />
                    </div>
                    <CardTitle className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
                        Platform Administration
                    </CardTitle>
                    <CardDescription className="text-stone-500 dark:text-stone-400">
                        Sign in to manage agencies and platform operations
                    </CardDescription>
                </CardHeader>

                <CardContent className="space-y-4">
                    {errorMessage && (
                        <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900/50 rounded-lg text-red-700 dark:text-red-300 text-sm">
                            <AlertCircle className="size-4 flex-shrink-0" />
                            <span>{errorMessage}</span>
                        </div>
                    )}

                    <Button
                        className="w-full py-6 bg-stone-900 hover:bg-stone-800 dark:bg-stone-100 dark:hover:bg-stone-200 dark:text-stone-900"
                        onClick={handleGoogleLogin}
                        disabled={isLoading}
                    >
                        <svg className="mr-2 size-5" viewBox="0 0 24 24">
                            <path
                                fill="currentColor"
                                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                            />
                            <path
                                fill="currentColor"
                                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                            />
                            <path
                                fill="currentColor"
                                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                            />
                            <path
                                fill="currentColor"
                                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                            />
                        </svg>
                        {isLoading ? 'Signing In...' : 'Sign in with Google'}
                    </Button>

                    <p className="text-xs text-center text-stone-400 dark:text-stone-500">
                        Requires platform administrator access
                    </p>
                </CardContent>
            </Card>
        </div>
    );
}
