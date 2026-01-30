import type { ReactNode } from "react"
import { SurrogateDetailLayoutClient } from "@/components/surrogates/detail/SurrogateDetailLayoutClient"

type SurrogateDetailLayoutProps = {
    children: ReactNode
}

export default function SurrogateDetailLayout({ children }: SurrogateDetailLayoutProps) {
    return <SurrogateDetailLayoutClient>{children}</SurrogateDetailLayoutClient>
}
