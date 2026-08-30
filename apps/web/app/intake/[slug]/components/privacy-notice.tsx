import { LockIcon } from "lucide-react"

export function PrivacyNotice({ text }: { text?: string | null }) {
    const notice = text && text.trim().length > 0 ? text : "Your information is encrypted and secure"
    const trimmed = notice.trim()
    const isUrl = /^https?:\/\//i.test(trimmed) || /^mailto:/i.test(trimmed)

    return (
        <div className="flex items-center gap-2 text-xs text-stone-500 mt-6">
            <LockIcon className="size-4" />
            {isUrl ? (
                <a
                    href={trimmed}
                    target="_blank"
                    rel="noreferrer"
                    className="underline decoration-dotted underline-offset-2 hover:text-primary"
                >
                    View privacy policy
                </a>
            ) : (
                <span className="whitespace-pre-line">{notice}</span>
            )}
        </div>
    )
}
