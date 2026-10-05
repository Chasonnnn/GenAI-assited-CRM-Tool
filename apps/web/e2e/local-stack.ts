// Addresses and the dev-endpoint secret of the disposable stack that `e2e/stack.mjs` starts.
// The secret only guards `/dev/*` on an API bound to 127.0.0.1 with a database that is
// dropped on every start, so it is a fixed test value, not a credential.
export const WEB_PORT = 3100
export const API_PORT = 8100
export const WEB_URL = `http://localhost:${WEB_PORT}`
export const API_URL = `http://localhost:${API_PORT}`
export const DEV_SECRET = "e2e-local-dev-secret"
