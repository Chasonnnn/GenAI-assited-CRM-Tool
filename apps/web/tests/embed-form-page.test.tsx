import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

vi.mock("../app/embed/forms/[slug]/page.client", () => ({
    default: ({
        slug,
        initialParentOrigin,
    }: {
        slug: string
        initialParentOrigin?: string | null
    }) => (
        <div
            data-testid="embed-page-props"
            data-slug={slug}
            data-parent-origin={initialParentOrigin ?? ""}
        />
    ),
}))

import EmbedFormPage from "../app/embed/forms/[slug]/page"

type EmbedFormPageProps = {
    params: Promise<{ slug: string }>
    searchParams: Promise<{ parent_origin?: string | string[] }>
}

describe("embed form server page", () => {
    it("passes the parent origin from the request to the first client render", async () => {
        const renderPage = EmbedFormPage as unknown as (
            props: EmbedFormPageProps
        ) => Promise<React.ReactNode>

        render(
            await renderPage({
                params: Promise.resolve({ slug: "lead-form" }),
                searchParams: Promise.resolve({
                    parent_origin: "https://www.ewisurrogacy.com",
                }),
            })
        )

        expect(screen.getByTestId("embed-page-props")).toHaveAttribute(
            "data-parent-origin",
            "https://www.ewisurrogacy.com"
        )
    })
})
