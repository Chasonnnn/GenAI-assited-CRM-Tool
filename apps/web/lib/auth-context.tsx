'use client';

import { createContext, use, useEffect, useState, type ReactNode } from 'react';
import api from '@/lib/api';
import { useMountEffect } from '@/lib/hooks/use-mount-effect';

// Interface matches backend MeResponse schema
export interface User {
    user_id: string;
    email: string;
    display_name: string;
    avatar_url?: string;
    phone?: string;
    title?: string;
    org_id: string;
    org_name: string;
    org_display_name: string;
    org_slug: string;
    org_timezone: string;
    org_portal_base_url: string;
    role: string;
    ai_enabled: boolean;
    mfa_enabled: boolean;
    mfa_required: boolean;
    mfa_verified: boolean;
    profile_complete: boolean;
}

interface AuthContextType {
    user: User | null;
    isLoading: boolean;
    error: Error | null;
    refetch: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function shouldSkipAuthFetch() {
    if (typeof window === 'undefined') return false;

    const pathname = window.location.pathname || '';
    const hostname = window.location.hostname || '';
    const isOpsRoute = pathname.startsWith('/ops') || hostname.startsWith('ops.');
    const isMfaRoute = pathname.startsWith('/mfa') || pathname.startsWith('/auth/duo/callback');

    return isOpsRoute && !isMfaRoute;
}

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(() => !shouldSkipAuthFetch());
    const [error, setError] = useState<Error | null>(null);

    const fetchUser = async () => {
        setIsLoading(true);
        setError(null);
        const result = await api.get<User>('/auth/me').then((data) => ({
            status: 'success' as const,
            data,
        })).catch((err: unknown) => ({
            status: 'error' as const,
            err,
        }));

        if (result.status === 'success') {
            setUser(result.data);
        } else {
            setUser(null);
            if (result.err instanceof Error) {
                // Don't treat 401 as error - just means not logged in
                if ('status' in result.err && (result.err as { status: number }).status === 401) {
                    setError(null);
                } else {
                    setError(result.err);
                }
            }
        }
        setIsLoading(false);
    };

    useMountEffect(() => {
        if (shouldSkipAuthFetch()) return;

        const timeoutId = window.setTimeout(() => {
            void fetchUser()
        }, 0);
        return () => window.clearTimeout(timeoutId);
    });

    return (
        <AuthContext.Provider value={{ user, isLoading, error, refetch: () => { void fetchUser() } }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = use(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}

// Hook for protected pages
export function useRequireAuth() {
    const { user, isLoading } = useAuth();

    useEffect(() => {
        if (!isLoading && !user) {
            window.location.href = '/login';
        }
        if (
            !isLoading &&
            user &&
            user.mfa_required &&
            !user.mfa_verified
        ) {
            const hasOpsCookie = document.cookie
                .split(';')
                .some((c) => c.trim().startsWith('auth_return_to=ops'));
            const isOpsRoute =
                window.location.pathname.startsWith('/ops') ||
                window.location.hostname.startsWith('ops.');
            const url = hasOpsCookie || isOpsRoute ? '/mfa?return_to=ops' : '/mfa';
            window.location.href = url;
        }
    }, [user, isLoading]);

    return { user, isLoading };
}
