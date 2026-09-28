import { redirect } from "next/navigation"

// Active Sessions lives on the Settings General tab; this route keeps old /settings/sessions links working.
export default function SessionsRedirectPage() {
    redirect("/settings")
}
