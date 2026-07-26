import { expectTypeOf } from 'vitest'

import type {
    ResendSettings,
    ResendSettingsUpdate,
} from './resend'

expectTypeOf<ResendSettings['rate_limit_group_configured']>()
    .toEqualTypeOf<boolean>()

// @ts-expect-error Settings responses must never expose the write-only token.
expectTypeOf<ResendSettings['rate_limit_group_token']>()
// @ts-expect-error Settings responses must never expose the stored fingerprint.
expectTypeOf<ResendSettings['rate_limit_group_fingerprint']>()

expectTypeOf<ResendSettingsUpdate['rate_limit_group_token']>()
    .toEqualTypeOf<string | undefined>()
