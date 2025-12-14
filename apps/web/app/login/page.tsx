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

  const handleDuoSSOLogin = async () => {
    setIsLoading(true)
    // Simulate Duo SSO process
    await new Promise((resolve) => setTimeout(resolve, 1000))
    setIsLoading(false)
    console.log("[v0] Duo SSO login initiated")
  }

  const handleUsernameLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    // Simulate username + Duo push authentication
    await new Promise((resolve) => setTimeout(resolve, 1000))
    setIsLoading(false)
    console.log("[v0] Username + Duo push initiated for:", username)
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4"
      style={{
        background: "linear-gradient(135deg, #667eea 0%, #764ba2 25%, #f093fb 50%, #f5576c 75%, #4facfe 100%)",
        backgroundSize: "400% 400%",
        animation: "gradient 15s ease infinite",
      }}
    >
      <div
        className="absolute inset-0 opacity-0"
        style={{
          background: "rgba(0, 0, 0, 0.15)",
        }}
      ></div>

      {/* Floating glass orbs for visual interest */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div
          className="absolute top-1/4 left-1/4 w-32 h-32 rounded-full opacity-50 animate-pulse"
          style={{
            background: "rgba(255, 255, 255, 0.15)",
            backdropFilter: "blur(20px) saturate(180%)",
            border: "2px solid rgba(255, 255, 255, 0.3)",
            boxShadow: "0 8px 32px rgba(255, 255, 255, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.4)",
          }}
        ></div>
        <div
          className="absolute top-3/4 right-1/4 w-24 h-24 rounded-full opacity-40 animate-pulse delay-1000"
          style={{
            background: "rgba(255, 255, 255, 0.15)",
            backdropFilter: "blur(20px) saturate(180%)",
            border: "2px solid rgba(255, 255, 255, 0.3)",
            boxShadow: "0 8px 32px rgba(255, 255, 255, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.4)",
          }}
        ></div>
        <div
          className="absolute top-1/2 right-1/3 w-16 h-16 rounded-full opacity-45 animate-pulse delay-500"
          style={{
            background: "rgba(255, 255, 255, 0.15)",
            backdropFilter: "blur(20px) saturate(180%)",
            border: "2px solid rgba(255, 255, 255, 0.3)",
            boxShadow: "0 8px 32px rgba(255, 255, 255, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.4)",
          }}
        ></div>
      </div>

      <Card
        className="max-w-md hover-lift shadow-2xl relative z-10 opacity-100 w-[126%] mx-[0] border-transparent"
        style={{
          background: "rgba(255, 255, 255, 0.25)",
          backdropFilter: "blur(40px) saturate(250%)",
          border: "1px solid rgba(255, 255, 255, 0.4)",
          boxShadow:
            "0 32px 80px rgba(0, 0, 0, 0.3), 0 16px 64px rgba(255, 255, 255, 0.2), inset 0 3px 0 rgba(255, 255, 255, 0.6), inset 0 -1px 0 rgba(255, 255, 255, 0.3)",
        }}
      >
        <CardHeader className="text-center space-y-3">
          <div className="flex justify-center mb-2">
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center bg-white/20 backdrop-blur-md border border-white/40">
              <ShieldCheck className="w-9 h-9 text-card-foreground" strokeWidth={2.5} />
            </div>
          </div>
          <div className="space-y-1">
            <div className="text-sm font-semibold text-card-foreground/80 font-sans tracking-wide">SURROGACY CRM</div>
            <CardTitle className="text-3xl font-bold font-sans text-card-foreground">Welcome Back</CardTitle>
          </div>
          <CardDescription className="text-card-foreground/70 font-sans">Sign in with Single Sign-On</CardDescription>
        </CardHeader>

        <CardContent className="space-y-5">
          <Button
            onClick={handleDuoSSOLogin}
            className="w-full ripple-effect hover-lift font-sans font-bold py-6 text-base transition-all duration-300 shadow-lg"
            style={{ backgroundColor: "#0C115B", color: "white" }}
            disabled={isLoading}
          >
            <svg className="w-6 h-6 mr-3" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z" />
            </svg>
            {isLoading ? "Signing In..." : "Sign in with Duo SSO"}
          </Button>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-white/30" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="px-3 bg-transparent text-card-foreground/60 font-sans font-semibold tracking-wider">
                Or use other sign-in options
              </span>
            </div>
          </div>

          <div className="space-y-4">
            <button
              onClick={() => setShowOtherOptions(!showOtherOptions)}
              className="w-full flex items-center justify-between px-4 py-3 rounded-lg border border-white/30 bg-white/10 hover:bg-white/20 text-card-foreground font-sans font-medium transition-all duration-200"
            >
              <span>Other sign-in methods</span>
              {showOtherOptions ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </button>

            {showOtherOptions && (
              <div className="space-y-4 pt-2 animate-in fade-in slide-in-from-top-2 duration-300">
                <form onSubmit={handleUsernameLogin} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="username" className="text-sm font-medium text-card-foreground font-sans">
                      Username
                    </Label>
                    <Input
                      id="username"
                      type="text"
                      placeholder="Enter your username"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      className="border-white/40 bg-white/10 placeholder:text-card-foreground/50 text-card-foreground py-3 focus:ring-2 focus:ring-blue-400 focus:border-blue-400 focus:bg-white/15 transition-all duration-200"
                      required
                    />
                  </div>

                  <Button
                    type="submit"
                    variant="outline"
                    className="w-full glass-effect border-white/40 hover-lift ripple-effect text-card-foreground hover:bg-white/25 font-sans font-semibold py-5 transition-all duration-300 bg-transparent"
                    disabled={isLoading}
                  >
                    {isLoading ? "Authenticating..." : "Continue with Duo"}
                  </Button>
                </form>

                <p className="text-xs text-center text-card-foreground/60 font-sans">
                  You will receive a Duo push notification to complete authentication
                </p>
              </div>
            )}
          </div>

          <div className="pt-4 space-y-3 border-t border-white/20">
            <div className="text-center">
              <a
                href="#"
                className="text-sm text-card-foreground/70 hover:text-card-foreground font-sans transition-colors inline-flex items-center gap-1"
              >
                Need help signing in? Contact IT Support
              </a>
            </div>
            <div className="text-center">
              <p className="text-xs text-card-foreground/50 font-sans">© 2025 Surrogacy CRM. All rights reserved.</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
