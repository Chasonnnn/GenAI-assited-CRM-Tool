import EmbedFormPageClient from "./page.client"

type PageProps = {
    params: Promise<{ slug: string }>
}

export default async function EmbedFormPage({ params }: PageProps) {
    const { slug } = await params
    return <EmbedFormPageClient slug={slug} />
}
