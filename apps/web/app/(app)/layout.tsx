"use client"

import { Suspense } from "react"
import dynamic from "next/dynamic"
import { useRequireAuth } from "@/lib/auth-context"

// Dynamic import with SSR disabled to prevent hydration mismatch from Base UI's ID generation
const AppSidebar = dynamic(
  () => import("@/components/app-sidebar").then(mod => mod.AppSidebar),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-screen items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }
)

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

  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
      }
    >
      <AppSidebar>{children}</AppSidebar>
    </Suspense>
  )
}
