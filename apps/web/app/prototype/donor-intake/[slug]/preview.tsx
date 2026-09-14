"use client"

import { Suspense, useRef } from "react"
import PublicIntakeFormClient from "@/app/intake/[slug]/page.client"
import { useEmbedFormResizeReporting } from "@/lib/hooks/use-embed-form-resize-reporting"
import styles from "./preview.module.css"

export default function DonorIntakePreview({ slug }: { slug: string }) {
    const containerRef = useRef<HTMLDivElement>(null)
    useEmbedFormResizeReporting(containerRef, "http://127.0.0.1:3027")
    return (
        <div ref={containerRef} className={styles.preview}>
            <Suspense fallback={<p>Loading form…</p>}>
                <PublicIntakeFormClient slug={slug} />
            </Suspense>
            <a href="http://127.0.0.1:3027/prototype/privacy/" target="_blank" rel="noreferrer"
                className={styles.notice}>Privacy notice</a>
        </div>
    )
}
