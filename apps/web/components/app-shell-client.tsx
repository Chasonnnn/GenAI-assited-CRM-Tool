"use client"

import { Suspense, useEffect } from "react"
import { usePathname, useRouter } from "next/navigation"
import dynamic from "next/dynamic"
import { useRequireAuth } from "@/lib/auth-context"
import { AIContextProvider } from "@/lib/context/ai-context"
import { AIChatDrawer } from "@/components/ai/AIChatDrawer"
import { AIFloatingButton } from "@/components/ai/AIFloatingButton"
import { OfflineBanner } from "@/components/offline-banner"

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

export default function AppShellClient({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading } = useRequireAuth();
  const pathname = usePathname();
  const router = useRouter();

  const shouldRedirectToWelcome =
    !!user &&
    !isLoading &&
    !user.profile_complete &&
    pathname !== "/welcome" &&
    !(user.mfa_required && !user.mfa_verified)

  // Redirect to welcome page if profile is incomplete
  useEffect(() => {
    if (shouldRedirectToWelcome) {
      router.replace("/welcome");
    }
  }, [shouldRedirectToWelcome, router]);

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

  // Don't render app shell while redirecting to welcome
  if (shouldRedirectToWelcome) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  const inner = (
    <AIContextProvider>
      {children}
      {/* AI Assistant - only shown when AI is enabled */}
      <AIChatDrawer />
      <AIFloatingButton />
    </AIContextProvider>
  )

  const content = (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
      }
    >
      <AppSidebar>{inner}</AppSidebar>
    </Suspense>
  )

  return (
    <>
      <OfflineBanner />
      {content}
    </>
  )
}
