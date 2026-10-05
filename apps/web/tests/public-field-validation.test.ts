import { describe, expect, it } from "vitest"

import type { FormField } from "@/lib/api/forms"
import { getPublicFieldValidationError } from "@/lib/forms/public-field-validation"

const EMAIL_FIELD: FormField = { key: "email", label: "Email", type: "email", required: true }
const INVALID_EMAIL = "Email must be a valid email address."

const getEmailError = (address: string) => getPublicFieldValidationError(EMAIL_FIELD, address)

// Each verdict below matches the API's rule for email answers (pydantic EmailStr, email-validator 2.3.0).
describe("public email field validation", () => {
    it.each([
        ["a plain address", "erin.example@example.com"],
        ["surrounding spaces", "  erin@example.com  "],
        ["a trailing next-line character", "erin@example.com\u0085"],
        ["an uppercase address", "ERIN@EXAMPLE.COM"],
        ["a plus tag", "erin+tag@example.com"],
        ["an apostrophe", "o'brien@example.com"],
        ["a reserved name that is not the top-level domain", "erin@test.com"],
        ["the example top-level domain", "erin@example.example"],
        ["a Punycode domain", "erin@xn--bcher-kva.com"],
        ["a non-ASCII local part", "josé@example.com"],
        ["a non-ASCII domain", "erin@bücher.com"],
        ["a local part over 64 characters", `${"a".repeat(65)}@example.com`],
        ["a 63-character domain label", `erin@${"b".repeat(63)}.com`],
        ["a 254-character address", `${"a".repeat(64)}@${Array(3).fill("b".repeat(61)).join(".")}.com`],
    ])("accepts %s", (_name, address) => {
        expect(getEmailError(address)).toBeNull()
    })

    it.each([
        ["the test top-level domain", "erin.example@example.test"],
        ["a subdomain under test", "erin@sub.example.test"],
        ["an uppercase test domain", "erin@EXAMPLE.TEST"],
        ["the invalid top-level domain", "erin@example.invalid"],
        ["the local top-level domain", "erin@example.local"],
        ["the localhost top-level domain", "erin@example.localhost"],
        ["the onion top-level domain", "erin@example.onion"],
        ["the arpa top-level domain", "erin@1.0.0.127.in-addr.arpa"],
        ["a reserved domain after a non-ASCII local part", "josé@example.test"],
        ["a domain with no period", "erin@localhost"],
        ["a top-level domain that ends with a digit", "erin@example.c0"],
        ["a numeric top-level domain", "erin@example.123"],
        ["a bracketed IP address", "erin@[127.0.0.1]"],
        ["a domain label that starts with a hyphen", "erin@-example.com"],
        ["a domain label that ends with a hyphen", "erin@example-.com"],
        ["an underscore in the domain", "erin@exa_mple.com"],
        ["two periods in a row in the domain", "erin@example..com"],
        ["a domain that starts with a period", "erin@.example.com"],
        ["a domain that ends with a period", "erin@example.com."],
        ["two hyphens after two letters in a domain label", "erin@ab--cd.com"],
        ["a 64-character domain label", `erin@${"b".repeat(64)}.com`],
        ["a 255-character address", `${"a".repeat(65)}@${Array(3).fill("b".repeat(61)).join(".")}.com`],
        ["a local part that starts with a period", ".erin@example.com"],
        ["a local part that ends with a period", "erin.@example.com"],
        ["two periods in a row in the local part", "erin..example@example.com"],
        ["parentheses in the local part", "erin(x)@example.com"],
        ["a quoted local part", '"erin"@example.com'],
        ["a space in the local part", "erin example@example.com"],
        ["a no-break space in the local part", "erin\u00a0x@example.com"],
        ["a space in the domain", "erin@exam ple.com"],
        ["a leading byte order mark", "\ufefferin@example.com"],
        ["a trailing zero-width space", "erin@example.com\u200b"],
        ["a character that normalizes to a semicolon", "erin\u037e@example.com"],
        ["an underscore in a non-ASCII domain", "erin@ex_ample.bücher.com"],
        ["two at-signs in a row", "erin@@example.com"],
        ["two at-signs", "erin@a@example.com"],
        ["no local part", "@example.com"],
        ["no domain", "erin@"],
        ["no at-sign", "erin"],
    ])("rejects %s", (_name, address) => {
        expect(getEmailError(address)).toBe(INVALID_EMAIL)
    })

    // The API accepts these through pydantic's "Name <address>" form and stores them unchanged.
    it.each(["<erin@example.com>", "Erin<erin@example.com>", "Erin Example <erin@example.com>"])(
        "rejects the display-name form %s",
        (address) => {
            expect(getEmailError(address)).toBe(INVALID_EMAIL)
        },
    )

    // A browser has no IDNA tables, so the API alone rejects a Punycode label that does not decode.
    it("leaves the validity of a Punycode label to the API", () => {
        expect(getEmailError("erin@xn--a.com")).toBeNull()
    })
})
