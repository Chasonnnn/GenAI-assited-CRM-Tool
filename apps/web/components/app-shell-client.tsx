"use client"

import { Suspense, useEffect } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
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

  const searchParams = useSearchParams();
  const disableShell = searchParams?.get("noShell") === "1";
  const disableSidebar = disableShell || searchParams?.get("noSidebar") === "1";
  const disableAI = disableShell || searchParams?.get("noAI") === "1";
  const disableOffline = disableShell || searchParams?.get("noOffline") === "1";

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

  if (disableShell) {
    return <>{children}</>;
  }

  const content = (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
      }
    >
      {disableSidebar ? children : <AppSidebar>{children}</AppSidebar>}
    </Suspense>
  );

  if (disableAI) {
    return (
      <>
        {!disableOffline && <OfflineBanner />}
        {content}
      </>
    );
  }

  return (
    <AIContextProvider>
      {!disableOffline && <OfflineBanner />}
      {content}

      {/* AI Assistant - only shown when AI is enabled */}
      <AIChatDrawer />
      <AIFloatingButton />
    </AIContextProvider>
  )
}
