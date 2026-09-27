import { notFound } from "next/navigation"

import { NotFoundState } from "@/components/error-state"
import { getRecordNotFoundState } from "@/lib/record-not-found"

type PageProps = {
    params: Promise<{ kind: string }>
}

/** Proxy rewrite target for unknown record ids; proxy.ts sets the 404 status. */
export default async function RecordNotFoundPage({ params }: PageProps) {
    const { kind } = await params
    const state = getRecordNotFoundState(kind)
    if (!state) {
        notFound()
    }

    return (
        <NotFoundState
            title={state.title}
            backHref={state.backHref}
            backLabel={state.backLabel}
            headingLevel={1}
            className="min-h-[50vh]"
        />
    )
}
