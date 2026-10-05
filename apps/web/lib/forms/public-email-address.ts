// Mirrors the API's rule for email answers: email-validator 2.3.0 with no deliverability check,
// called from `_validate_field_value` in apps/api/app/services/form_submission_service.py.
// Update this file when that rule or package version changes. Both test suites check the
// addresses in apps/api/tests/fixtures/public_email_rule_cases.json against their side.
//
// The API decides alone in two cases:
// - an internationalized domain name, because a browser has no IDNA tables: a domain with
//   non-ASCII characters, or a Punycode (`xn--`) label that does not decode;
// - a code point with no Unicode assignment, because browsers and Python differ in Unicode version.

const ATEXT = "A-Za-z0-9_!#$%&'*+\\-/=?^`{|}~"
const NON_ASCII = "\\u0080-\\u{10FFFF}"
const LOCAL_PART = new RegExp(`^[${ATEXT}${NON_ASCII}]+(?:\\.[${ATEXT}${NON_ASCII}]+)*$`, "u")

const HOSTNAME_LABEL = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/
const NON_ASCII_CHARACTER = new RegExp(`[${NON_ASCII}]`, "u")
const NON_ASCII_DOMAIN = new RegExp(`^[A-Za-z0-9.\\-${NON_ASCII}]+\\.[A-Za-z0-9.\\-${NON_ASCII}]+$`, "u")

// Separators, controls, format characters such as a zero-width space, and private-use characters.
const UNSAFE_CHARACTER = /[\p{Z}\p{Cc}\p{Cf}\p{Co}\p{Cs}]/u
const LEADING_COMBINING_MARK = /^\p{M}/u

// Python's `str.strip()` set. Unlike `String.prototype.trim()`, it strips U+001C to U+001F and
// U+0085, and it keeps U+FEFF.
const PYTHON_WHITESPACE = "\\t-\\r\\x1c-\\x20\\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000"
const SURROUNDING_WHITESPACE = new RegExp(`^[${PYTHON_WHITESPACE}]+|[${PYTHON_WHITESPACE}]+$`, "g")

// IANA special-use names that email-validator rejects as a domain or as a parent domain.
const SPECIAL_USE_TOP_LEVEL_DOMAINS = new Set(["arpa", "invalid", "local", "localhost", "onion", "test"])

const MAX_ADDRESS_BYTES = 254
const MAX_DOMAIN_LENGTH = 253
const MAX_LABEL_LENGTH = 63

function isAcceptedAsciiDomain(domain: string): boolean {
    const name = domain.toLowerCase()
    if (name.length > MAX_DOMAIN_LENGTH) return false
    const labels = name.split(".")
    const topLevelDomain = labels[labels.length - 1] ?? ""
    if (labels.length < 2 || !/[a-z]$/.test(topLevelDomain)) return false
    if (SPECIAL_USE_TOP_LEVEL_DOMAINS.has(topLevelDomain)) return false
    return labels.every(
        (label) =>
            label.length <= MAX_LABEL_LENGTH &&
            HOSTNAME_LABEL.test(label) &&
            // Two hyphens in the third and fourth positions are reserved for Punycode labels.
            (label.slice(2, 4) !== "--" || label.startsWith("xn")),
    )
}

function isWithinAddressLimit(local: string, domain: string): boolean {
    return new TextEncoder().encode(`${local}@${domain}`).length <= MAX_ADDRESS_BYTES
}

/**
 * Returns false for every email address the API rejects, except the two cases in the file header.
 */
export function isAcceptedPublicEmailAddress(value: string): boolean {
    const address = value.replace(SURROUNDING_WHITESPACE, "")
    if (UNSAFE_CHARACTER.test(address)) return false

    const atIndex = address.indexOf("@")
    if (atIndex === -1) return false
    const local = address.slice(0, atIndex)
    const domain = address.slice(atIndex + 1)
    if (LEADING_COMBINING_MARK.test(local) || LEADING_COMBINING_MARK.test(domain)) return false

    // The API checks the local part again after Unicode normalization.
    const normalizedLocal = local.normalize("NFC")
    if (!LOCAL_PART.test(local) || !LOCAL_PART.test(normalizedLocal)) return false
    if (!isWithinAddressLimit(local, domain) || !isWithinAddressLimit(normalizedLocal, domain)) return false

    return NON_ASCII_CHARACTER.test(domain) ? NON_ASCII_DOMAIN.test(domain) : isAcceptedAsciiDomain(domain)
}
