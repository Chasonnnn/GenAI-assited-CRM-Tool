/* global process, console, fetch, setTimeout */
// Starts the disposable stack that local e2e runs drive: a fresh `crm_e2e` database,
// the API, and the Next.js dev server. `e2e.config.ts` runs this as the target's
// `app.command` and stops it when the run ends.
//
// The API starts in a directory without a `.env` and receives only the variables built
// here. It therefore holds no provider credentials, and no test can send email or SMS.
import { spawn, spawnSync } from "node:child_process"
import { randomBytes } from "node:crypto"
import { existsSync, mkdirSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const apiDir = path.resolve(webDir, "../api")
const python = path.join(apiDir, ".venv/bin/python")
const stackDir = path.join(webDir, ".e2e/stack")

const webPort = requireEnv("E2E_WEB_PORT")
const apiPort = requireEnv("E2E_API_PORT")
const devSecret = requireEnv("E2E_DEV_SECRET")
const pgPort = process.env.E2E_PG_PORT ?? "5432"
const database = "crm_e2e"

function requireEnv(name) {
    const value = process.env[name]
    if (!value) {
        console.error(`${name} is not set; start the stack through \`e2e run\`.`)
        process.exit(2)
    }
    return value
}

if (!existsSync(python)) {
    console.error(`${python} is missing; run \`uv sync\` in apps/api first.`)
    process.exit(2)
}
mkdirSync(stackDir, { recursive: true })

// Fernet keys are generated per start: the database they encrypt is dropped with them.
const fernetKey = randomBytes(32).toString("base64url") + "="
const apiEnv = {
    PATH: process.env.PATH ?? "",
    HOME: process.env.HOME ?? "",
    PYTHONPATH: apiDir,
    ENV: "test",
    TESTING: "1",
    DATABASE_URL: `postgresql+psycopg://postgres:postgres@127.0.0.1:${pgPort}/${database}`,
    JWT_SECRET: randomBytes(32).toString("hex"),
    FERNET_KEY: fernetKey,
    META_ENCRYPTION_KEY: fernetKey,
    VERSION_ENCRYPTION_KEY: fernetKey,
    DATA_ENCRYPTION_KEY: fernetKey,
    PII_HASH_KEY: randomBytes(32).toString("hex"),
    DEV_SECRET: devSecret,
    API_BASE_URL: `http://localhost:${apiPort}`,
    FRONTEND_URL: `http://localhost:${webPort}`,
    CORS_ORIGINS: `http://localhost:${webPort}`,
}

function runOrExit(label, args) {
    const result = spawnSync(python, args, { cwd: stackDir, env: apiEnv, stdio: "inherit" })
    if (result.status !== 0) {
        console.error(`${label} failed.`)
        process.exit(1)
    }
}

const resetDatabase = `
import psycopg
with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:${pgPort}/postgres", autocommit=True) as connection:
    connection.execute("DROP DATABASE IF EXISTS ${database} WITH (FORCE)")
    connection.execute("CREATE DATABASE ${database}")
`
runOrExit("Database reset (is `docker compose up -d db` running?)", ["-c", resetDatabase])
runOrExit("Migration", ["-m", "alembic", "-c", path.join(apiDir, "alembic.ini"), "upgrade", "head"])

const children = []
let stopping = false

function start(label, command, args, options) {
    const child = spawn(command, args, { stdio: "inherit", ...options })
    children.push(child)
    child.on("exit", (code) => {
        if (stopping) return
        console.error(`${label} exited with code ${code}.`)
        stop(1)
    })
    return child
}

function stop(exitCode) {
    if (stopping) return
    stopping = true
    for (const child of children) child.kill("SIGTERM")
    // The runner allows 10 s for shutdown; leave it room to report.
    setTimeout(() => {
        for (const child of children) child.kill("SIGKILL")
        process.exit(exitCode)
    }, 8_000).unref()
    Promise.all(children.map((child) => new Promise((resolve) => child.once("exit", resolve)))).then(
        () => process.exit(exitCode),
    )
}

process.on("SIGTERM", () => stop(0))
process.on("SIGINT", () => stop(0))

start(
    "API",
    python,
    ["-m", "uvicorn", "app.main:app", "--app-dir", apiDir, "--host", "127.0.0.1", "--port", apiPort],
    { cwd: stackDir, env: apiEnv },
)

async function waitForApi() {
    const deadline = Date.now() + 60_000
    while (Date.now() < deadline) {
        try {
            const response = await fetch(`http://127.0.0.1:${apiPort}/health`)
            if (response.ok) return
        } catch {
            // Not listening yet.
        }
        await new Promise((resolve) => setTimeout(resolve, 500))
    }
    console.error("API did not become healthy within 60 s.")
    stop(1)
}

await waitForApi()

// The web server starts only after the API is healthy, so a ready web URL means a ready stack.
if (!stopping) {
    start("Web", path.join(webDir, "node_modules/.bin/next"), ["dev", "--port", webPort], {
        cwd: webDir,
        env: {
            PATH: process.env.PATH ?? "",
            HOME: process.env.HOME ?? "",
            NEXT_PUBLIC_API_BASE_URL: `http://localhost:${apiPort}`,
            NEXT_TELEMETRY_DISABLED: "1",
        },
    })
}
