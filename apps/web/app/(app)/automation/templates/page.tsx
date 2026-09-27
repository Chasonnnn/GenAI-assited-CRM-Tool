import { redirect } from "next/navigation"

// Workflow templates live in the /automation Workflow Templates tab; this route keeps old links working.
export default function TemplatesPage() {
    redirect("/automation?scope=templates")
}
