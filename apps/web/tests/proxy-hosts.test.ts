import { describe, expect, it } from 'vitest'

import { isPlatformRootHost } from '../proxy'

describe('isPlatformRootHost', () => {
    it('treats the bare platform domain as a root host', () => {
        expect(isPlatformRootHost('surrogacyforce.com', 'surrogacyforce.com')).toBe(true)
    })

    it('treats the www platform domain as a root host', () => {
        expect(isPlatformRootHost('www.surrogacyforce.com', 'surrogacyforce.com')).toBe(true)
    })

    it('does not treat org or ops subdomains as root hosts', () => {
        expect(isPlatformRootHost('ewi.surrogacyforce.com', 'surrogacyforce.com')).toBe(false)
        expect(isPlatformRootHost('ops.surrogacyforce.com', 'surrogacyforce.com')).toBe(false)
    })
})
