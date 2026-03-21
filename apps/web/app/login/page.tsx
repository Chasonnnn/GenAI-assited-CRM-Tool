import type { Metadata } from "next"

import LoginPageClient from "./LoginPageClient"

export const metadata: Metadata = {
  title: "Login | Surrogacy Force",
  description: "Sign in to Surrogacy Force with Google SSO and complete Duo verification.",
}

export default function LoginPage() {
  return <LoginPageClient />
}
