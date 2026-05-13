import type { Metadata } from "next"
import { cookies } from "next/headers"

import LoginPageClient from "./LoginPageClient"

export const metadata: Metadata = {
  title: "Login | Surrogacy Force",
  description: "Sign in to Surrogacy Force with Google SSO and complete Duo verification.",
}

type LoginSearchParams = {
  error?: string | string[]
}

const AUTH_ERROR_ACCOUNT_HINT_COOKIE = "auth_error_account_hint"

type LoginPageProps = {
  searchParams?: Promise<LoginSearchParams>
}

function firstSearchParam(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] ?? null : value ?? null
}

export default async function LoginPage({ searchParams }: LoginPageProps = {}) {
  const params = searchParams ? await searchParams : {}
  const authError = firstSearchParam(params.error)
  const cookieStore = await cookies()
  const accountHint = authError
    ? cookieStore.get(AUTH_ERROR_ACCOUNT_HINT_COOKIE)?.value ?? null
    : null

  return <LoginPageClient authError={authError} authAccountHint={accountHint} />
}
