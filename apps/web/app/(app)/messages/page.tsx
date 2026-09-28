import { redirect } from "next/navigation"

// The SMS/MMS inbox lives in the Tickets workspace; page.client.tsx is the component it embeds.
export default function MessagesPage() {
    redirect("/tickets?view=messages")
}
