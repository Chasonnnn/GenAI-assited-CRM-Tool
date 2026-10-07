import { spawnSync } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"

// Reads the run's disposable `crm_e2e` database for values the app only sends by email,
// such as self-service appointment tokens. It uses the API virtualenv's psycopg, as
// `e2e/stack.mjs` does, so the web app needs no Postgres client.
const python = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../api/.venv/bin/python")
const databaseUrl = `postgresql://postgres:postgres@127.0.0.1:${process.env.E2E_PG_PORT ?? "5432"}/crm_e2e`

const QUERY_SCRIPT = `
import json, sys, psycopg
with psycopg.connect(sys.argv[1]) as connection:
    rows = connection.execute(sys.argv[2], sys.argv[3:]).fetchall()
print(json.dumps([[None if value is None else str(value) for value in row] for row in rows]))
`

/** Runs one read-only query with `%s` placeholders and returns every row as strings. */
export function queryDatabase(sql: string, params: string[] = []): Array<Array<string | null>> {
    const result = spawnSync(python, ["-c", QUERY_SCRIPT, databaseUrl, sql, ...params], {
        encoding: "utf8",
        timeout: 10_000,
    })
    if (result.status !== 0) throw new Error(`Database query failed: ${result.stderr || result.error}`)
    return JSON.parse(result.stdout) as Array<Array<string | null>>
}
