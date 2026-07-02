"use client"

import { useState } from "react"
import Link from "next/link"
import { AlertCircle, ArrowLeft, Loader2Icon, ShieldCheck } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { buttonVariants } from "@/components/ui/button-variants"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { getAuthApiBase } from "@/lib/auth-utils"

type LoginErrorMessage = {
  title: string
  description: string
}

const LOGIN_ERROR_MESSAGES: Record<string, LoginErrorMessage> = {
  no_membership: {
    title: "Access not available",
    description:
      "The Google account selected by your browser is not connected to an active team membership. Go back to login and choose the account your team uses for Surrogacy Force.",
  },
  not_invited: {
    title: "Invite required",
    description:
      "No active invitation was found for this Google account. Ask your administrator to send or resend an invitation.",
  },
  invite_expired: {
    title: "Invite expired",
    description: "This invite link is no longer active. Ask your administrator to resend it.",
  },
  invalid_invite_role: {
    title: "Invite cannot be used",
    description:
      "This invitation has an invalid role. Ask your administrator to resend it before trying again.",
  },
  account_disabled: {
    title: "Account disabled",
    description: "This account has been disabled. Contact your administrator before trying again.",
  },
}

const FALLBACK_LOGIN_ERROR: LoginErrorMessage = {
  title: "Sign-in could not continue",
  description: "Try signing in again. If this keeps happening, contact your administrator.",
}

function getLoginErrorMessage(errorCode: string | null | undefined) {
  const normalizedCode = errorCode?.trim()
  if (!normalizedCode) return null
  return LOGIN_ERROR_MESSAGES[normalizedCode] ?? FALLBACK_LOGIN_ERROR
}

function getLoginReturnTo() {
  return typeof window !== "undefined" &&
    (window.location.pathname.startsWith("/ops") || window.location.hostname.startsWith("ops."))
    ? "ops"
    : "app"
}

type LoginPageClientProps = {
  authError?: string | null
  authAccountHint?: string | null
}

export default function LoginPageClient({
  authError = null,
  authAccountHint = null,
}: LoginPageClientProps) {
  const [redirectStatus, setRedirectStatus] = useState<"idle" | "redirecting">("idle")

  const apiBase = getAuthApiBase()
  const errorMessage = getLoginErrorMessage(authError)
  const isRedirecting = redirectStatus === "redirecting"

  const buildGoogleLoginUrl = (loginHint?: string) => {
    const returnTo = getLoginReturnTo()
    const params = new URLSearchParams()
    if (loginHint) params.set("login_hint", loginHint)
    params.set("return_to", returnTo)
    return `${apiBase}/auth/google/login?${params.toString()}`
  }

  const handleGoogleLogin = () => {
    setRedirectStatus("redirecting")
    try {
      const returnTo = getLoginReturnTo()
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
    <div
      className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden"
      style={{
        background: "linear-gradient(135deg, #f8f9fa 0%, #f1f3f5 50%, #f8f9fa 100%)",
      }}
    >
      <div
        className="absolute -left-32 top-1/2 size-[600px] rounded-full blur-3xl"
        style={{
          background: "radial-gradient(circle, rgba(99, 102, 241, 0.6) 0%, rgba(139, 92, 246, 0.5) 40%, transparent 70%)",
        }}
      />
      <div
        className="absolute -right-32 top-0 size-[500px] rounded-full blur-3xl"
        style={{
          background: "radial-gradient(circle, rgba(236, 72, 153, 0.5) 0%, rgba(244, 114, 182, 0.4) 40%, transparent 70%)",
        }}
      />
      <Card
        className="w-full max-w-md relative z-10 border border-white/40 shadow-2xl"
        style={{
          background: "linear-gradient(180deg, rgba(255, 255, 255, 0.7) 0%, rgba(253, 242, 248, 0.6) 100%)",
          backdropFilter: "blur(8px) saturate(160%)",
          WebkitBackdropFilter: "blur(8px) saturate(160%)",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.6)",
        }}
      >
        <CardHeader className="text-center space-y-4 pb-2">
          <div className="flex justify-center mb-2">
            <div className="size-14 rounded-xl flex items-center justify-center bg-zinc-100 border border-zinc-200">
              <ShieldCheck className="size-8 text-zinc-700" strokeWidth={1.5} />
            </div>
          </div>
          <div className="space-y-1">
            <div className="text-xs font-semibold text-zinc-500 tracking-widest">SURROGACY FORCE</div>
            <CardTitle className="text-3xl font-bold text-zinc-900">Welcome Back</CardTitle>
          </div>
          <CardDescription className="text-zinc-500">
            Sign in with Google SSO, then complete Duo verification
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-5">
          {errorMessage && (
            <Alert variant="destructive" className="border-red-200 bg-red-50 text-red-950">
              <AlertCircle className="size-4" aria-hidden="true" />
              <AlertTitle>{errorMessage.title}</AlertTitle>
              <AlertDescription className="text-red-800">
                {errorMessage.description}
                {authAccountHint && (
                  <span className="mt-2 block font-semibold text-red-950">
                    Google selected: {authAccountHint}
                  </span>
                )}
              </AlertDescription>
            </Alert>
          )}

          {errorMessage && (
            <Link
              href="/login"
              className={buttonVariants({
                variant: "outline",
                className:
                  "h-11 w-full rounded-full border-red-200 bg-white/70 font-semibold text-red-950 hover:bg-white hover:text-red-950",
              })}
            >
              <ArrowLeft className="size-4" aria-hidden="true" />
              Back to login
            </Link>
          )}

          <Button
            onClick={handleGoogleLogin}
            className="w-full font-semibold py-6 text-base rounded-full transition-all duration-300 bg-teal-950 text-white hover:bg-teal-900"
            disabled={isRedirecting}
          >
            {isRedirecting ? (
              <Loader2Icon className="lucide-loader-2 size-5 mr-2 animate-spin" aria-hidden="true" />
            ) : (
              <ShieldCheck className="size-5 mr-2" aria-hidden="true" />
            )}
            {isRedirecting ? "Signing In..." : "Sign in with Google"}
          </Button>

          <div className="pt-4 space-y-3 border-t border-zinc-100">
            <div className="text-center">
              <p className="text-sm text-zinc-500">
                Need help signing in? Contact your administrator.
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-zinc-400">
                © 2026 Surrogacy Force. All rights reserved.{" "}
                <Link href="/privacy" className="underline underline-offset-2 hover:text-zinc-600">
                  Privacy Policy
                </Link>
                {" "}·{" "}
                <Link href="/terms" className="underline underline-offset-2 hover:text-zinc-600">
                  Terms
                </Link>
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
