import type { Metadata } from "next"

import LoginPageClient from "./LoginPageClient"

export const metadata: Metadata = {
  title: "Login | Surrogacy Force",
  description: "Sign in to Surrogacy Force with Google SSO and complete Duo verification.",
}

type LoginSearchParams = {
  error?: string | string[]
}

type LoginPageProps = {
  searchParams?: Promise<LoginSearchParams>
}

function firstSearchParam(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] ?? null : value ?? null
}

export default async function LoginPage({ searchParams }: LoginPageProps = {}) {
  const params = searchParams ? await searchParams : {}
  return <LoginPageClient authError={firstSearchParam(params.error)} />
}
