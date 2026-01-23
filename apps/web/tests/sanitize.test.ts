import { describe, it, expect } from 'vitest'
import { sanitizeHtml } from '@/lib/utils/sanitize'

describe('sanitizeHtml', () => {
    it('preserves basic formatting and removes scripts', () => {
        const input = '<p>Hello <b>World</b><script>alert(1)</script></p>'
        const output = sanitizeHtml(input)
        expect(output).toContain('<p>')
        expect(output).toContain('<b>World</b>')
        expect(output).not.toContain('script')
    })
})
