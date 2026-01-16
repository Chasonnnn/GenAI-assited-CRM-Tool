import DOMPurify from 'dompurify'

/**
 * Sanitize HTML for safe rendering in rich-text previews.
 * Consistent config across all components.
 */
export function sanitizeHtml(html: string): string {
    return DOMPurify.sanitize(html, {
        ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li', 'span'],
        ALLOWED_ATTR: ['href', 'target', 'rel', 'class'],
    })
}
