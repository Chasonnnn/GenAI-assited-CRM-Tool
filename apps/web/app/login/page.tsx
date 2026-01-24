"use client"

import type React from "react"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ChevronDown, ChevronUp, ShieldCheck } from "lucide-react"

export default function LoginPage() {
  const [username, setUsername] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [showOtherOptions, setShowOtherOptions] = useState(false)

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

  const getReturnTo = () =>
    typeof window !== "undefined" && window.location.hostname.startsWith("ops.") ? "ops" : "app"

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

  const handleUsernameLogin = (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    const hint = username.trim()
    try {
      const returnTo = getReturnTo()
      const url = buildGoogleLoginUrl(hint || undefined)
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
      {/* Soft watercolor blobs - purple bottom-left, pink top-right */}
      <div
        className="absolute -left-32 top-1/2 w-[600px] h-[600px] rounded-full blur-3xl"
        style={{
          background: "radial-gradient(circle, rgba(99, 102, 241, 0.6) 0%, rgba(139, 92, 246, 0.5) 40%, transparent 70%)",
        }}
      />
      <div
        className="absolute -right-32 top-0 w-[500px] h-[500px] rounded-full blur-3xl"
        style={{
          background: "radial-gradient(circle, rgba(236, 72, 153, 0.5) 0%, rgba(244, 114, 182, 0.4) 40%, transparent 70%)",
        }}
      />
      <Card
        className="w-full max-w-md relative z-10 border border-white/40 shadow-2xl"
        style={{
          background: "linear-gradient(180deg, rgba(255, 255, 255, 0.7) 0%, rgba(253, 242, 248, 0.6) 100%)",
          backdropFilter: "blur(24px) saturate(180%)",
          WebkitBackdropFilter: "blur(24px) saturate(180%)",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.6)",
        }}
      >
        <CardHeader className="text-center space-y-4 pb-2">
          <div className="flex justify-center mb-2">
            <div className="w-14 h-14 rounded-xl flex items-center justify-center bg-gray-100 border border-gray-200">
              <ShieldCheck className="w-8 h-8 text-gray-700" strokeWidth={1.5} />
            </div>
          </div>
          <div className="space-y-1">
            <div className="text-xs font-semibold text-gray-500 tracking-widest">SURROGACY FORCE</div>
            <CardTitle className="text-3xl font-bold text-gray-900">Welcome Back</CardTitle>
          </div>
          <CardDescription className="text-gray-500">
            Sign in with Google SSO, then complete Duo verification
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-5">
          <Button
            onClick={handleGoogleLogin}
            className="w-full font-semibold py-6 text-base rounded-full transition-all duration-300 bg-indigo-950 text-white hover:bg-indigo-900"
            disabled={isLoading}
          >
            <ShieldCheck className="w-5 h-5 mr-2" />
            {isLoading ? "Signing In..." : "Sign in with Google"}
          </Button>

          <div className="relative py-2">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-gray-300/50" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="px-3 bg-transparent text-gray-500 font-medium tracking-wider">
                Or use other sign-in options
              </span>
            </div>
          </div>

          <div className="space-y-4">
            <Button
              variant="outline"
              onClick={() => setShowOtherOptions(!showOtherOptions)}
              className="w-full flex items-center justify-between px-4 py-3 border-gray-200 bg-gray-50/50 hover:bg-gray-100/50 text-gray-700 font-medium transition-all duration-200"
            >
              <span>Other sign-in methods</span>
              {showOtherOptions ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
            </Button>

            {showOtherOptions && (
              <div className="space-y-4 pt-2 animate-in fade-in slide-in-from-top-2 duration-300">
                <form onSubmit={handleUsernameLogin} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="username" className="text-sm font-medium text-gray-700">
                      Email (optional)
                    </Label>
                    <Input
                      id="username"
                      type="email"
                      placeholder="Enter your email (optional)"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      className="border-gray-200 bg-white placeholder:text-gray-400 text-gray-900 py-3 focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 transition-all duration-200"
                    />
                  </div>

                  <Button
                    type="submit"
                    variant="outline"
                    className="w-full border-gray-300 text-gray-700 hover:bg-gray-50 font-semibold py-5 transition-all duration-300 rounded-lg"
                    disabled={isLoading}
                  >
                    {isLoading ? "Authenticating..." : "Continue with Google"}
                  </Button>
                </form>

                <p className="text-xs text-center text-gray-400">
                  You will be redirected to Google, then prompted for Duo verification
                </p>
              </div>
            )}
          </div>

          <div className="pt-4 space-y-3 border-t border-gray-100">
            <div className="text-center">
              <p className="text-sm text-gray-500">
                Need help signing in? Contact your administrator.
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-400">© 2025 Surrogacy Force. All rights reserved.</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
