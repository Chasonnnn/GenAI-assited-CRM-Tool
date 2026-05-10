"use client"

import { useState } from "react"
import { Loader2Icon, ShieldCheck } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { getAuthApiBase } from "@/lib/auth-utils"

export default function LoginPageClient() {
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
          <Button
            onClick={handleGoogleLogin}
            className="w-full font-semibold py-6 text-base rounded-full transition-all duration-300 bg-teal-950 text-white hover:bg-teal-900"
            disabled={isLoading}
          >
            {isLoading ? (
              <Loader2Icon className="lucide-loader-2 size-5 mr-2 animate-spin" aria-hidden="true" />
            ) : (
              <ShieldCheck className="size-5 mr-2" aria-hidden="true" />
            )}
            {isLoading ? "Signing In..." : "Sign in with Google"}
          </Button>

          <div className="pt-4 space-y-3 border-t border-zinc-100">
            <div className="text-center">
              <p className="text-sm text-zinc-500">
                Need help signing in? Contact your administrator.
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-zinc-400">© 2025 Surrogacy Force. All rights reserved.</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
