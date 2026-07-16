"use client"

import { redirect, usePathname } from "next/navigation"
import dynamic from "next/dynamic"
import { useAuth } from "@/lib/auth-context"
import { AIContextProvider } from "@/lib/context/ai-context"
import { AIChatDrawerHost } from "@/components/ai/AIChatDrawerHost"
import { AIFloatingButton } from "@/components/ai/AIFloatingButton"
import { OfflineBanner } from "@/components/offline-banner"
import { SessionExpiredDialog } from "@/components/session-expired-dialog"

// Dynamic import with SSR disabled to prevent hydration mismatch from Base UI's ID generation
const AppSidebar = dynamic(
  () => import("@/components/app-sidebar").then(mod => mod.AppSidebar),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-screen items-center justify-center">
        <div className="animate-spin rounded-full size-8 border-b-2 border-primary"></div>
      </div>
    )
  }
)

function getMfaRedirectPath(pathname: string) {
  const hasOpsCookie =
    typeof document !== "undefined" &&
    document.cookie
      .split(";")
      .some((cookie) => cookie.trim().startsWith("auth_return_to=ops"))
  const isOpsRoute =
    pathname.startsWith("/ops") ||
    (typeof window !== "undefined" && window.location.hostname.startsWith("ops."))

  return hasOpsCookie || isOpsRoute ? "/mfa?return_to=ops" : "/mfa"
}

function AppShellLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="animate-spin rounded-full size-8 border-b-2 border-primary"></div>
    </div>
  )
}

export default function AppShellClient({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading } = useAuth();
  const pathname = usePathname();

  const shouldRedirectToWelcome =
    !!user &&
    !isLoading &&
    !user.profile_complete &&
    pathname !== "/welcome" &&
    !(user.mfa_required && !user.mfa_verified)

  // Show loading state while checking auth
  if (isLoading) {
    return <AppShellLoading />;
  }

  if (!user) {
    redirect("/login");
    return <AppShellLoading />;
  }

  if (user.mfa_required && !user.mfa_verified) {
    redirect(getMfaRedirectPath(pathname));
    return <AppShellLoading />;
  }

  if (shouldRedirectToWelcome) {
    redirect("/welcome");
    return <AppShellLoading />;
  }

  const inner = (
    <AIContextProvider>
      {children}
      {/* AI Assistant - only shown when AI is enabled */}
      <AIChatDrawerHost />
      <AIFloatingButton />
    </AIContextProvider>
  )

  return (
    <>
      <OfflineBanner />
      <SessionExpiredDialog />
      <AppSidebar>{inner}</AppSidebar>
    </>
  )
}
