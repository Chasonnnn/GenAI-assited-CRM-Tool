import EmbedFormPageClient from "./page.client"

export const dynamic = "force-dynamic"
export const revalidate = 0
export const fetchCache = "force-no-store"

type PageProps = {
    params: Promise<{ slug: string }>
}

export default async function EmbedFormPage({ params }: PageProps) {
    const { slug } = await params
    return <EmbedFormPageClient slug={slug} />
}
