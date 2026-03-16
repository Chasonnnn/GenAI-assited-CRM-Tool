"use client"

import { useState } from "react"
import { ArrowRight, ShieldCheck } from "lucide-react"

import { PublicAccessShell } from "@/components/public-access-shell"
import { Button } from "@/components/ui/button"
import { getAuthApiBase } from "@/lib/auth-utils"

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState(false)

  const apiBase = getAuthApiBase()

  const getReturnTo = () =>
    typeof window !== "undefined" &&
    (window.location.pathname.startsWith("/ops") || window.location.hostname.startsWith("ops."))
      ? "ops"
      : "app"

  const buildGoogleLoginUrl = (loginHint?: string) => {
    const returnTo = getReturnTo()
    const params = new URLSearchParams()
    if (loginHint) params.set("login_hint", loginHint)
    params.set("return_to", returnTo)
    return `${apiBase}/auth/google/login?${params.toString()}`
  }

  const handleGoogleLogin = () => {
    setIsLoading(true)
    try {
      const returnTo = getReturnTo()
      const url = buildGoogleLoginUrl()
      try {
        sessionStorage.setItem("auth_return_to", returnTo)
      } catch {
        // Ignore storage errors (private browsing, etc.)
      }
      window.location.assign(url)
    } catch {
      // Ignore navigation errors in non-browser runtimes.
    }
  }

  return (
    <PublicAccessShell
      title="Welcome Back"
      description="Use your organization Google account to continue."
      panel={
        <div className="space-y-4">
          <div className="space-y-2">
            <h2 className="font-[family-name:var(--font-display)] text-3xl leading-none text-foreground">
              Sign in with Google
            </h2>
            <p className="text-sm leading-5 text-muted-foreground">
              Duo verification follows after sign-in.
            </p>
          </div>

          <Button
            onClick={handleGoogleLogin}
            className="h-13 w-full justify-between rounded-full px-5 text-base font-semibold"
            disabled={isLoading}
          >
            <span className="inline-flex items-center gap-2">
              <ShieldCheck className="size-5" />
              {isLoading ? "Signing In..." : "Sign in with Google"}
            </span>
            <ArrowRight className="size-5" />
          </Button>
        </div>
      }
      footer={
        <div className="flex flex-col items-start gap-1.5 text-sm text-muted-foreground">
          <span>Need help signing in? Contact your administrator.</span>
          <span>© 2026 Surrogacy Force. All rights reserved.</span>
        </div>
      }
    />
  )
}
