const FORWARDED_HEADER_NAMES = ['x-forwarded-for', 'x-forwarded-host', 'x-forwarded-proto'];

type HeaderSource = Pick<Headers, 'get'> | null | undefined;

export function buildServerApiHeaders(
    source: HeaderSource,
    init: HeadersInit = {},
): Headers {
    const headers = new Headers(init);

    if (!source) {
        return headers;
    }

    for (const headerName of FORWARDED_HEADER_NAMES) {
        const value = source.get(headerName);
        if (value) {
            headers.set(headerName, value);
        }
    }

    return headers;
}
