import DOMPurify from 'dompurify'

/**
 * Sanitize HTML for safe rendering in rich-text previews.
 * Consistent config across all components.
 */
export function sanitizeHtml(html: string): string {
    return DOMPurify.sanitize(html, {
        ALLOWED_TAGS: [
            'p',
            'br',
            'strong',
            'b',
            'em',
            'u',
            's',
            'a',
            'ul',
            'ol',
            'li',
            'span',
            'mark',
            'blockquote',
            'code',
            'pre',
            'hr',
            'h1',
            'h2',
            'h3',
            'h4',
            'h5',
            'h6',
        ],
        ALLOWED_ATTR: ['href', 'target', 'rel', 'class', 'data-comment-id', 'data-note-id'],
    })
}
