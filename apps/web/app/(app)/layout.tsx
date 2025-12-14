"use client"

import { AppSidebar } from "@/components/app-sidebar"
import { useRequireAuth } from "@/lib/auth-context"

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading } = useRequireAuth();

  // Show loading state while checking auth
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  // Don't render app shell if not authenticated (redirect happens in useRequireAuth)
  if (!user) {
    return null;
  }

  return <AppSidebar>{children}</AppSidebar>;
}