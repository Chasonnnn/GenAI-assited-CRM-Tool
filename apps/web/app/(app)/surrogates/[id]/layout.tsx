import type { ReactNode } from "react"
import { SurrogateDetailLayout } from "@/components/surrogates/detail/SurrogateDetailLayout"

type SurrogateDetailLayoutProps = {
    children: ReactNode
}

export default function SurrogateLayout({ children }: SurrogateDetailLayoutProps) {
    return <SurrogateDetailLayout>{children}</SurrogateDetailLayout>
}
